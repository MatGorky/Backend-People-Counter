import logging
import uuid

import paho.mqtt.client as mqtt

from app.extensions import db
from app.models.data_tracker import DataTracker
from app.models.testdata import TestData

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(
        self,
        app,
        broker="broker.hivemq.com",
        port=1883,
        topic=None,
        test_topic=None,
        json_topic=None,
    ):
        self.app = app
        self.broker = broker
        self.port = port
        self.topic = topic or []
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"nce-client-{uuid.uuid4()}"
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

        self.topic_handlers = {}
        if test_topic:
            self.topic_handlers[test_topic] = self.handle_test_data
        if json_topic:
            self.topic_handlers[json_topic] = self.handle_json
        self._json_topic = json_topic

    def handle_test_data(self, payload):
        with self.app.app_context():
            db.session.add(TestData(value=payload))
            db.session.commit()

    def handle_default(self, topic, payload):
        payload = payload.replace("\n", "").replace("\r", "")
        with self.app.app_context():
            db.session.add(DataTracker(topic=topic, payload=payload))
            db.session.commit()

    def handle_json(self, payload):
        """Passage pipeline (spec-002): raw log + parsed passage_event, atomic.
        One retry on transient connection errors so a dropped pooled connection
        doesn't lose the message (BUG-2 family)."""
        from sqlalchemy.exc import OperationalError

        from app.services.ingestion import ingest_json_message

        with self.app.app_context():
            try:
                ingest_json_message(self._json_topic, payload)
            except OperationalError:
                logger.warning("DB connection error during ingest; retrying once")
                db.session.rollback()
                ingest_json_message(self._json_topic, payload)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("MQTT connected; subscribing to %d topic(s)", len(self.topic))
            for topic in self.topic:
                client.subscribe(topic)
        else:
            logger.error("MQTT connect failed: %s", reason_code)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("MQTT disconnected cleanly")
        else:
            logger.warning("MQTT unexpected disconnect (%s); paho will auto-reconnect", reason_code)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            # Payload contents are not logged (they land in the DB); topic+size suffice.
            logger.info("MQTT message on %s (%d bytes)", msg.topic, len(msg.payload))
            handler = self.topic_handlers.get(msg.topic)
            if handler:
                handler(payload)
            else:
                self.handle_default(msg.topic, payload)
        except Exception:
            logger.exception("Error handling MQTT message on topic %s", msg.topic)

    def start(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()


def build_subscriber(app) -> MQTTSubscriber:
    return MQTTSubscriber(
        app,
        broker=app.config["MQTT_BROKER_HOST"],
        port=app.config["MQTT_BROKER_PORT"],
        topic=app.config["MQTT_TOPICS"],
        test_topic=app.config["MQTT_TEST_TOPIC"] or None,
        json_topic=app.config["MQTT_TOPIC_JSON"] or None,
    )


def build_and_start(app, required=False):
    """Composition-root helper. `required=True` (the dedicated worker) propagates
    startup failures; the web entrypoint tolerates a dead broker (API must stay up)."""
    if not app.config["MQTT_TOPICS"]:
        logger.warning(
            "MQTT_TOPICS is empty - the subscriber will receive nothing. "
            "Topic names are unlisted; set them in .env / deploy env (docs/secrets.md)."
        )
    subscriber = build_subscriber(app)
    try:
        subscriber.start()
        return subscriber
    except Exception:
        logger.exception("MQTT subscriber failed to start")
        if required:
            raise
        return None
