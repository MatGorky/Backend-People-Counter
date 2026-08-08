"""Characterization of the current API behavior — the safety net for the refactor.

Pins today's semantics, including known quirks kept on purpose until spec-002:
counts include ALL topics (BUG-6), zero-count buckets are absent (BUG-10), and
times are bucketed in America/Sao_Paulo derived from naive-UTC register_time.
"""

from datetime import datetime


def utc(y, mo, d, h, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s)


class TestAuthMatrix:
    PROTECTED = [
        "/data-tracker/tracker",
        "/data-tracker/tracker/some-topic",
        "/data-tracker/daily/2026-06-09",
        "/data-tracker/monthly/2026-06",
    ]

    def test_no_header_is_401(self, client):
        for url in self.PROTECTED:
            assert client.get(url).status_code == 401, url

    def test_malformed_header_is_401(self, client):
        for url in self.PROTECTED:
            r = client.get(url, headers={"Authorization": "Token abc"})
            assert r.status_code == 401, url

    def test_bad_signature_is_401(self, client, make_token):
        headers = {"Authorization": f"Bearer {make_token(secret='wrong-secret')}"}
        for url in self.PROTECTED:
            assert client.get(url, headers=headers).status_code == 401, url

    def test_expired_token_is_401(self, client, make_token):
        headers = {"Authorization": f"Bearer {make_token(exp_delta=-60)}"}
        for url in self.PROTECTED:
            assert client.get(url, headers=headers).status_code == 401, url

    def test_valid_token_is_accepted(self, client, auth_headers):
        for url in self.PROTECTED:
            assert client.get(url, headers=auth_headers).status_code == 200, url

    def test_removed_testdata_namespace_is_404(self, client):
        assert client.get("/test-data/test").status_code == 404
        assert client.post("/test-data/test/2026-01-01T00:00:00").status_code == 404


class TestDailyEndpoint:
    def test_sao_paulo_day_boundary(self, client, auth_headers, insert_row):
        # 02:30 UTC on June 10 == 23:30 June 9 in São Paulo -> belongs to June 9, hour 23
        insert_row("unit-json", "{}", utc(2026, 6, 10, 2, 30))
        # 02:59 UTC on June 9 == 23:59 June 8 SP -> must NOT appear on June 9
        insert_row("unit-json", "{}", utc(2026, 6, 9, 2, 59))
        # 12:00 UTC June 9 == 09:00 SP -> hour 9
        insert_row("unit-json", "{}", utc(2026, 6, 9, 12, 0))

        r = client.get("/data-tracker/daily/2026-06-09", headers=auth_headers)
        assert r.status_code == 200
        buckets = {item["time"]: item["count"] for item in r.get_json()["data"]}
        assert buckets == {
            "2026-06-09T23:00:00": 1,
            "2026-06-09T09:00:00": 1,
        }

    def test_counts_include_all_topics(self, client, auth_headers, insert_row):
        # BUG-6, current behavior: non-passage topics are counted too
        insert_row("unit-json", "{}", utc(2026, 6, 9, 12, 0))
        insert_row("unit-config", "300", utc(2026, 6, 9, 12, 5))

        r = client.get("/data-tracker/daily/2026-06-09", headers=auth_headers)
        buckets = {item["time"]: item["count"] for item in r.get_json()["data"]}
        assert buckets == {"2026-06-09T09:00:00": 2}

    def test_empty_day_returns_empty_list(self, client, auth_headers):
        r = client.get("/data-tracker/daily/2026-06-09", headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()["data"] == []  # BUG-10: no zero-filled buckets

    def test_invalid_date_is_400(self, client, auth_headers):
        r = client.get("/data-tracker/daily/not-a-date", headers=auth_headers)
        assert r.status_code == 400


class TestMonthlyEndpoint:
    def test_sao_paulo_month_boundary(self, client, auth_headers, insert_row):
        # 02:30 UTC June 1 == 23:30 May 31 SP -> belongs to May
        insert_row("unit-json", "{}", utc(2026, 6, 1, 2, 30))
        # 03:30 UTC June 1 == 00:30 June 1 SP -> belongs to June
        insert_row("unit-json", "{}", utc(2026, 6, 1, 3, 30))

        june = client.get("/data-tracker/monthly/2026-06", headers=auth_headers).get_json()["data"]
        may = client.get("/data-tracker/monthly/2026-05", headers=auth_headers).get_json()["data"]
        assert june == [{"date": "2026-06-01", "count": 1}]
        assert may == [{"date": "2026-05-31", "count": 1}]

    def test_days_are_ordered(self, client, auth_headers, insert_row):
        insert_row("unit-json", "{}", utc(2026, 6, 20, 12, 0))
        insert_row("unit-json", "{}", utc(2026, 6, 5, 12, 0))
        insert_row("unit-json", "{}", utc(2026, 6, 5, 13, 0))

        data = client.get("/data-tracker/monthly/2026-06", headers=auth_headers).get_json()["data"]
        assert data == [
            {"date": "2026-06-05", "count": 2},
            {"date": "2026-06-20", "count": 1},
        ]

    def test_invalid_month_is_400(self, client, auth_headers):
        r = client.get("/data-tracker/monthly/2026-13-01", headers=auth_headers)
        assert r.status_code == 400


class TestRawTrackerEndpoints:
    def test_tracker_lists_rows(self, client, auth_headers, insert_row):
        insert_row("unit-json", '{"a": 1}', utc(2026, 6, 9, 12, 0))
        insert_row("unit-config", "300", utc(2026, 6, 9, 12, 1))

        rows = client.get("/data-tracker/tracker", headers=auth_headers).get_json()
        assert [(r["topic"], r["payload"]) for r in rows] == [
            ("unit-json", '{"a": 1}'),
            ("unit-config", "300"),
        ]

    def test_tracker_by_topic_filters(self, client, auth_headers, insert_row):
        insert_row("unit-json", "{}", utc(2026, 6, 9, 12, 0))
        insert_row("unit-config", "300", utc(2026, 6, 9, 12, 1))

        rows = client.get("/data-tracker/tracker/unit-config", headers=auth_headers).get_json()
        assert len(rows) == 1
        assert rows[0]["topic"] == "unit-config"
