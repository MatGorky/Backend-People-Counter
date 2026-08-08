"""Characterization of MQTT message handling — handlers called directly, no broker."""
from types import SimpleNamespace

from sqlalchemy import select

from tests import payload_fixtures as fx


def make_subscriber(app):
    from app.mqtt.subscriber import MQTTSubscriber

    return MQTTSubscriber(app, topic=["unit-json", "unit-test"], test_topic="unit-test")


def msg(topic: str, payload) -> SimpleNamespace:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return SimpleNamespace(topic=topic, payload=payload)


def all_rows(app, database, model):
    with app.app_context():
        return database.session.execute(select(model)).scalars().all()


class TestDefaultHandler:
    def test_json_payload_stored_raw(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-json", fx.PAYLOAD_2026))

        rows = all_rows(app, database, DataTracker)
        assert len(rows) == 1
        assert rows[0].topic == "unit-json"
        assert '"access_count": 14007' in rows[0].payload

    def test_2024_era_payload_stored(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-json", fx.PAYLOAD_2024))
        assert len(all_rows(app, database, DataTracker)) == 1

    def test_newlines_stripped(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-json", fx.PAYLOAD_MULTILINE))

        rows = all_rows(app, database, DataTracker)
        assert "\n" not in rows[0].payload

    def test_non_json_text_still_stored(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-config", fx.GARBAGE_TEXT))

        rows = all_rows(app, database, DataTracker)
        assert rows[0].payload == fx.GARBAGE_TEXT

    def test_undecodable_bytes_dropped_without_raising(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-json", fx.GARBAGE_BYTES))
        assert all_rows(app, database, DataTracker) == []

    def test_oversize_payload_dropped_without_raising(self, app, database):
        from app.models.data_tracker import DataTracker

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-json", fx.OVERSIZE_TEXT))
        assert all_rows(app, database, DataTracker) == []


class TestTestTopicHandler:
    def test_test_topic_goes_to_test_data(self, app, database):
        from app.models.testdata import TestData

        sub = make_subscriber(app)
        sub.on_message(None, None, msg("unit-test", "hello"))

        rows = all_rows(app, database, TestData)
        assert len(rows) == 1
        assert rows[0].value == "hello"
