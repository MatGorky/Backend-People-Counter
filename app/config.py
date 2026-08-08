import os


class Config:
    """Env-driven configuration — identical mechanism in every environment
    (local .env, Cloud Run env vars, university env_file later)."""

    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # pool_pre_ping heals the stale-connection drops behind BUG-2.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    # MQTT broker: public HiveMQ in prod (until spec-008/appendix-C),
    # local Mosquitto from docker-compose in dev (spec-004).
    MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
    MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

    # Topic names are deliberately NOT committed (public repo + unauthenticated public
    # broker — names are the only gate, see SEC-3). Real values live in gitignored
    # .env / deploy/prod.env.yaml. See docs/secrets.md.
    MQTT_TOPICS = [t.strip() for t in os.getenv("MQTT_TOPICS", "").split(",") if t.strip()]
    MQTT_TOPIC_JSON = os.getenv("MQTT_TOPIC_JSON", "")  # the passage-event JSON topic
    MQTT_TEST_TOPIC = os.getenv("MQTT_TEST_TOPIC", "")  # legacy discovery topic (optional)

    # Comma-separated allowlist of CORS origins (SEC-6).
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,https://biblioteca-nce-front-838397174234.us-central1.run.app",
    ).split(",")
