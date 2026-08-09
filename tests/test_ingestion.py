"""Parser unit tests + ingestion pipeline integration tests (spec-002)."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.services.ingestion import ingest_json_message, parse_passage
from tests import payload_fixtures as fx

RECEIVED = datetime(2026, 7, 31, 19, 44, 30, tzinfo=UTC)


class TestParser:
    def test_normalizes_sp_mislabeled_z_to_utc(self):
        parsed = parse_passage(fx.PAYLOAD_2026, RECEIVED)
        # device says 16:44:10"Z" but that's São Paulo wall time == 19:44:10 UTC
        assert parsed.occurred_at == datetime(2026, 7, 31, 19, 44, 10, tzinfo=UTC)
        assert parsed.clock_skew_flagged is False

    def test_parses_all_fields(self):
        parsed = parse_passage(fx.PAYLOAD_2026, RECEIVED)
        assert parsed.device_id == "unit-sensor"
        assert parsed.access_count == 14007
        assert parsed.people_count == 7003
        assert parsed.status_sensor == "free"
        assert parsed.rssi == -76
        assert parsed.ip_address == "10.0.0.42"
        assert parsed.pulse_ton == 101

    def test_2024_era_payload_without_pulses(self):
        parsed = parse_passage(fx.PAYLOAD_2024, datetime(2024, 9, 23, 15, 42, tzinfo=UTC))
        assert parsed is not None
        assert parsed.pulse_ton is None
        assert parsed.pulse_toff is None
        assert parsed.access_count == 4200

    def test_non_zero_padded_date_as_seen_in_prod(self):
        received = datetime(2026, 8, 7, 11, 48, 20, tzinfo=UTC)
        payload = json.dumps({"device_id": "unit-sensor", "time_detected": "2026-08-7T08:48:17Z"})
        parsed = parse_passage(payload, received)
        assert parsed.occurred_at == datetime(2026, 8, 7, 11, 48, 17, tzinfo=UTC)

    def test_clock_skew_falls_back_to_server_time(self):
        received = RECEIVED + timedelta(hours=5)
        parsed = parse_passage(fx.PAYLOAD_2026, received)
        assert parsed.occurred_at == received
        assert parsed.clock_skew_flagged is True

    def test_missing_time_uses_received_at(self):
        parsed = parse_passage(json.dumps({"device_id": "unit-sensor"}), RECEIVED)
        assert parsed.occurred_at == RECEIVED

    def test_invalid_ip_becomes_none(self):
        payload = json.dumps({"device_id": "unit-sensor", "ip_address": "not-an-ip"})
        assert parse_passage(payload, RECEIVED).ip_address is None

    def test_garbage_is_none(self):
        assert parse_passage(fx.GARBAGE_TEXT, RECEIVED) is None
        assert parse_passage(json.dumps([1, 2]), RECEIVED) is None
        assert parse_passage(json.dumps({"no_device": True}), RECEIVED) is None


def events(app, database):
    from app.models.passage_event import PassageEvent

    with app.app_context():
        return (
            database.session.execute(select(PassageEvent).order_by(PassageEvent.id)).scalars().all()
        )


def raw_count(app, database):
    from sqlalchemy import func as sqlfunc

    from app.models.data_tracker import DataTracker

    with app.app_context():
        return database.session.execute(select(sqlfunc.count(DataTracker.id))).scalar()


def payload_with(access: int, device: str = "unit-sensor") -> str:
    # Live SP-wall-time timestamp, like the real firmware — keeps the skew guard quiet.
    device_ts = (datetime.now(UTC) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.dumps(
        {
            "device_id": device,
            "time_detected": device_ts,
            "access_count": access,
            "people_count": access // 2,
            "status_sensor": "free",
        }
    )


class TestIngestPipeline:
    def test_registered_device_creates_event(self, app, database, make_device):
        device = make_device("unit-sensor")
        with app.app_context():
            ingest_json_message("unit-json", payload_with(100))

        stored = events(app, database)
        assert len(stored) == 1
        assert stored[0].room_id == device.room_id
        assert stored[0].raw_id is not None
        # normalized to true UTC ≈ now (exact tz math is covered by parser unit tests)
        assert abs(stored[0].occurred_at.astimezone(UTC) - datetime.now(UTC)) < timedelta(
            seconds=90
        )

        from app.models.device import Device

        with app.app_context():
            refreshed = database.session.get(Device, "unit-sensor")
            assert refreshed.last_seen is not None
            assert refreshed.first_seen is not None

    def test_duplicate_delivery_stored_once(self, app, database, make_device):
        make_device("unit-sensor")
        with app.app_context():
            ingest_json_message("unit-json", payload_with(100))
            ingest_json_message("unit-json", payload_with(100))  # same counter = dup

        assert len(events(app, database)) == 1
        assert raw_count(app, database) == 2  # audit log keeps both

    def test_counter_reset_is_not_a_duplicate(self, app, database, make_device):
        make_device("unit-sensor")
        with app.app_context():
            ingest_json_message("unit-json", payload_with(6278))
            ingest_json_message("unit-json", payload_with(1))  # device reboot

        assert [e.access_count for e in events(app, database)] == [6278, 1]

    def test_unregistered_device_raw_only(self, app, database):
        with app.app_context():
            ingest_json_message("unit-json", payload_with(100, device="intruder"))

        assert events(app, database) == []
        assert raw_count(app, database) == 1

    def test_unparsable_payload_raw_only(self, app, database, make_device):
        make_device("unit-sensor")
        with app.app_context():
            ingest_json_message("unit-json", fx.GARBAGE_TEXT)

        assert events(app, database) == []
        assert raw_count(app, database) == 1

    def test_subscriber_routes_json_topic_to_pipeline(self, app, database, make_device):
        from app.mqtt.subscriber import MQTTSubscriber

        make_device("unit-sensor")
        sub = MQTTSubscriber(
            app, topic=["unit-json"], test_topic="unit-test", json_topic="unit-json"
        )
        msg = SimpleNamespace(topic="unit-json", payload=payload_with(42).encode())
        sub.on_message(None, None, msg)

        assert len(events(app, database)) == 1
        assert events(app, database)[0].access_count == 42
