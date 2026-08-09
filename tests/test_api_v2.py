"""API v2 test matrix: aggregates, timezone bucketing, access control (spec-002/003)."""

import uuid
from datetime import UTC, datetime

import pytest

USER = str(uuid.uuid4())


@pytest.fixture()
def room(make_room):
    return make_room(name="Biblioteca NCE", slug="biblioteca-nce")


@pytest.fixture()
def user_headers(make_token):
    return {"Authorization": f"Bearer {make_token(sub=USER)}"}


@pytest.fixture()
def admin_headers(make_token):
    return {"Authorization": f"Bearer {make_token(app_metadata={'role': 'admin'})}"}


@pytest.fixture()
def make_event(app, database):
    def _make(room, occurred_utc: datetime, device_id="unit-sensor", access=None):
        from app.models.passage_event import PassageEvent

        with app.app_context():
            database.session.add(
                PassageEvent(
                    device_id=device_id,
                    room_id=room.id,
                    occurred_at=occurred_utc.replace(tzinfo=UTC),
                    received_at=occurred_utc.replace(tzinfo=UTC),
                    access_count=access,
                )
            )
            database.session.commit()

    return _make


class TestAccessControl:
    def test_no_grant_is_404(self, client, room, user_headers):
        r = client.get(
            f"/api/v2/rooms/{room.id}/passages/daily?date=2026-06-09", headers=user_headers
        )
        assert r.status_code == 404

    def test_nonexistent_room_is_404(self, client, user_headers):
        r = client.get("/api/v2/rooms/999/passages/daily?date=2026-06-09", headers=user_headers)
        assert r.status_code == 404

    def test_granted_user_is_200(self, client, room, user_headers, grant_access):
        grant_access(USER, room.id)
        r = client.get(
            f"/api/v2/rooms/{room.id}/passages/daily?date=2026-06-09", headers=user_headers
        )
        assert r.status_code == 200

    def test_admin_bypasses_grants(self, client, room, admin_headers):
        r = client.get(
            f"/api/v2/rooms/{room.id}/passages/daily?date=2026-06-09", headers=admin_headers
        )
        assert r.status_code == 200

    def test_unauthenticated_is_401(self, client, room):
        assert (
            client.get(f"/api/v2/rooms/{room.id}/passages/daily?date=2026-06-09").status_code == 401
        )


class TestMyRooms:
    def test_empty_without_grants(self, client, user_headers, room):
        assert client.get("/api/v2/me/rooms", headers=user_headers).get_json() == []

    def test_lists_granted_rooms(self, client, user_headers, room, grant_access):
        grant_access(USER, room.id)
        rooms = client.get("/api/v2/me/rooms", headers=user_headers).get_json()
        assert [r["slug"] for r in rooms] == ["biblioteca-nce"]
        assert rooms[0]["timezone"] == "America/Sao_Paulo"

    def test_admin_sees_all_rooms(self, client, admin_headers, make_room):
        make_room(slug="room-a")
        make_room(slug="room-b")
        rooms = client.get("/api/v2/me/rooms", headers=admin_headers).get_json()
        assert len(rooms) == 2


class TestDaily:
    def test_zero_filled_buckets_in_room_timezone(self, client, room, admin_headers, make_event):
        # 02:30 UTC June 10 == 23:30 June 9 São Paulo -> hour 23 of June 9
        make_event(room, datetime(2026, 6, 10, 2, 30))
        make_event(room, datetime(2026, 6, 9, 12, 0))  # 09:00 SP
        make_event(room, datetime(2026, 6, 9, 12, 30))  # 09:30 SP

        body = client.get(
            f"/api/v2/rooms/{room.id}/passages/daily?date=2026-06-09", headers=admin_headers
        ).get_json()
        assert len(body["data"]) == 24
        by_time = {item["time"]: item["count"] for item in body["data"]}
        assert by_time["2026-06-09T23:00:00"] == 1
        assert by_time["2026-06-09T09:00:00"] == 2
        assert by_time["2026-06-09T03:00:00"] == 0  # zero-filled
        assert body["totals"] == {"passages": 3, "visits": 2}  # ceil(3/2)

    def test_room_isolation(self, client, make_room, admin_headers, make_event):
        room_a, room_b = make_room(slug="a"), make_room(slug="b")
        make_event(room_a, datetime(2026, 6, 9, 12, 0))
        make_event(room_b, datetime(2026, 6, 9, 12, 0))

        body = client.get(
            f"/api/v2/rooms/{room_a.id}/passages/daily?date=2026-06-09", headers=admin_headers
        ).get_json()
        assert body["totals"]["passages"] == 1

    def test_missing_date_is_400(self, client, room, admin_headers):
        r = client.get(f"/api/v2/rooms/{room.id}/passages/daily", headers=admin_headers)
        assert r.status_code == 400


class TestMonthlyRangeYearly:
    def test_monthly_zero_fills_calendar(self, client, room, admin_headers, make_event):
        make_event(room, datetime(2026, 6, 1, 3, 30))  # 00:30 June 1 SP
        make_event(room, datetime(2026, 6, 1, 2, 30))  # 23:30 May 31 SP -> excluded

        body = client.get(
            f"/api/v2/rooms/{room.id}/passages/monthly?month=2026-06", headers=admin_headers
        ).get_json()
        assert len(body["data"]) == 30
        assert body["data"][0] == {"date": "2026-06-01", "count": 1}
        assert body["totals"]["passages"] == 1

    def test_range_inclusive_and_validated(self, client, room, admin_headers, make_event):
        make_event(room, datetime(2026, 6, 9, 12, 0))
        ok = client.get(
            f"/api/v2/rooms/{room.id}/passages/range?start=2026-06-09&end=2026-06-10",
            headers=admin_headers,
        ).get_json()
        assert [d["count"] for d in ok["data"]] == [1, 0]

        assert (
            client.get(
                f"/api/v2/rooms/{room.id}/passages/range?start=2026-06-10&end=2026-06-09",
                headers=admin_headers,
            ).status_code
            == 400
        )
        assert (
            client.get(
                f"/api/v2/rooms/{room.id}/passages/range?start=2024-01-01&end=2026-01-01",
                headers=admin_headers,
            ).status_code
            == 400
        )

    def test_yearly_monthly_buckets(self, client, room, admin_headers, make_event):
        make_event(room, datetime(2026, 6, 9, 12, 0))
        make_event(room, datetime(2026, 6, 10, 12, 0))
        make_event(room, datetime(2026, 11, 3, 12, 0))

        body = client.get(
            f"/api/v2/rooms/{room.id}/passages/yearly?year=2026", headers=admin_headers
        ).get_json()
        assert len(body["data"]) == 12
        by_month = {item["month"]: item["count"] for item in body["data"]}
        assert by_month["2026-06"] == 2
        assert by_month["2026-11"] == 1
        assert by_month["2026-01"] == 0


class TestAdminEndpoints:
    def test_non_admin_is_403(self, client, room, user_headers):
        assert (
            client.post(
                "/api/v2/rooms", json={"name": "X", "slug": "x"}, headers=user_headers
            ).status_code
            == 403
        )
        assert (
            client.put(f"/api/v2/rooms/{room.id}/users/{USER}", headers=user_headers).status_code
            == 403
        )

    def test_full_admin_flow(self, client, admin_headers, user_headers, make_token):
        created = client.post(
            "/api/v2/rooms", json={"name": "Sala Nova", "slug": "sala-nova"}, headers=admin_headers
        )
        assert created.status_code == 201
        room_id = created.get_json()["id"]

        registered = client.post(
            f"/api/v2/rooms/{room_id}/devices",
            json={"device_id": "unit-sensor-2", "description": "entrada"},
            headers=admin_headers,
        )
        assert registered.status_code == 201

        assert (
            client.put(f"/api/v2/rooms/{room_id}/users/{USER}", headers=admin_headers).status_code
            == 201
        )
        grants = client.get(f"/api/v2/rooms/{room_id}/users", headers=admin_headers).get_json()
        assert [g["user_id"] for g in grants] == [USER]

        # the granted user can now read the room
        assert (
            client.get(
                f"/api/v2/rooms/{room_id}/passages/daily?date=2026-06-09", headers=user_headers
            ).status_code
            == 200
        )

        assert (
            client.delete(
                f"/api/v2/rooms/{room_id}/users/{USER}", headers=admin_headers
            ).status_code
            == 204
        )
        assert (
            client.get(
                f"/api/v2/rooms/{room_id}/passages/daily?date=2026-06-09", headers=user_headers
            ).status_code
            == 404
        )

    def test_duplicate_slug_is_409(self, client, room, admin_headers):
        r = client.post(
            "/api/v2/rooms",
            json={"name": "Dup", "slug": "biblioteca-nce"},
            headers=admin_headers,
        )
        assert r.status_code == 409
