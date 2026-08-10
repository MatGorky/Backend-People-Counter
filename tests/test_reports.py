"""Report service + PDF endpoint tests (spec-005)."""

import io
import uuid
from datetime import UTC, datetime

import pytest
from pypdf import PdfReader

USER = str(uuid.uuid4())


@pytest.fixture()
def room(make_room):
    return make_room(name="Biblioteca NCE", slug="biblioteca-nce")


@pytest.fixture()
def admin_headers(make_token):
    return {"Authorization": f"Bearer {make_token(app_metadata={'role': 'admin'})}"}


@pytest.fixture()
def make_event(app, database):
    def _make(room, occurred_utc: datetime, access=None):
        from app.models.passage_event import PassageEvent

        with app.app_context():
            database.session.add(
                PassageEvent(
                    device_id="unit-sensor",
                    room_id=room.id,
                    occurred_at=occurred_utc.replace(tzinfo=UTC),
                    received_at=occurred_utc.replace(tzinfo=UTC),
                    access_count=access,
                )
            )
            database.session.commit()

    return _make


class TestRangeReportService:
    def test_kpis(self, app, room, make_event):
        from datetime import date

        from app.services.reports import range_report

        # June 9 SP: two passages at 09:00, one at 14:00; June 10: one passage
        make_event(room, datetime(2026, 6, 9, 12, 0), access=100)
        make_event(room, datetime(2026, 6, 9, 12, 30), access=101)
        make_event(room, datetime(2026, 6, 9, 17, 0), access=102)
        make_event(room, datetime(2026, 6, 10, 12, 0), access=103)

        with app.app_context():
            report = range_report(room, date(2026, 6, 8), date(2026, 6, 11))

        assert report["totals"] == {"passages": 4, "visits": 2}
        assert report["days"] == 4
        assert report["open_days"] == 2
        assert report["busiest_day"] == {"date": "2026-06-09", "count": 3}
        assert report["busiest_hour"]["hour"] == 9
        assert report["daily_average"] == 1.0
        assert report["data_quality"] == {"gap_jumps": 0, "estimated_missed": 0}

    def test_gap_stats_count_missed(self, app, room, make_event):
        from datetime import date

        from app.services.reports import range_report

        make_event(room, datetime(2026, 6, 9, 12, 0), access=100)
        make_event(room, datetime(2026, 6, 9, 13, 0), access=104)  # 101-103 lost

        with app.app_context():
            report = range_report(room, date(2026, 6, 9), date(2026, 6, 9))

        assert report["data_quality"] == {"gap_jumps": 1, "estimated_missed": 3}


class TestPdfEndpoint:
    URL = "/api/v2/rooms/{id}/reports/passages.pdf?start=2026-06-08&end=2026-06-11"

    def test_requires_auth_and_access(self, client, room, make_token):
        assert client.get(self.URL.format(id=room.id)).status_code == 401
        no_grant = {"Authorization": f"Bearer {make_token(sub=USER)}"}
        assert client.get(self.URL.format(id=room.id), headers=no_grant).status_code == 404

    def test_validates_range(self, client, room, admin_headers):
        bad = f"/api/v2/rooms/{room.id}/reports/passages.pdf?start=2026-06-11&end=2026-06-08"
        assert client.get(bad, headers=admin_headers).status_code == 400
        huge = f"/api/v2/rooms/{room.id}/reports/passages.pdf?start=2024-01-01&end=2026-01-01"
        assert client.get(huge, headers=admin_headers).status_code == 400

    def test_produces_valid_pdf_with_content(self, client, room, admin_headers, make_event):
        make_event(room, datetime(2026, 6, 9, 12, 0), access=100)
        make_event(room, datetime(2026, 6, 9, 12, 30), access=101)

        r = client.get(self.URL.format(id=room.id), headers=admin_headers)
        assert r.status_code == 200
        assert r.mimetype == "application/pdf"
        assert r.data.startswith(b"%PDF")
        assert (
            'filename="relatorio-biblioteca-nce-2026-06-08-2026-06-11.pdf"'
            in r.headers["Content-Disposition"]
        )

        text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(r.data)).pages)
        assert "Biblioteca NCE" in text
        assert "Passagens por dia" in text
        assert "Visitas estimadas" in text
        assert "09/06/2026" in text  # per-day table row

    def test_empty_range_still_renders(self, client, room, admin_headers):
        r = client.get(self.URL.format(id=room.id), headers=admin_headers)
        assert r.status_code == 200
        assert r.data.startswith(b"%PDF")
