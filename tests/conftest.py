"""Shared fixtures: real local Postgres (honeycomb — no mocked DB), JWT factory.

Environment is configured BEFORE the app is imported. Uses a dedicated
`people_counter_test` database on the compose Postgres so dev seed data survives.
"""

import os
import time
import uuid
from datetime import datetime

import jwt as pyjwt
import psycopg2
import pytest
from sqlalchemy import text

TEST_DB_NAME = "people_counter_test"
TEST_DB_URI = f"postgresql://postgres:localdev@localhost:5432/{TEST_DB_NAME}"
TEST_JWT_SECRET = "test-secret"

os.environ["SQLALCHEMY_DATABASE_URI"] = TEST_DB_URI
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["MQTT_BROKER_HOST"] = "127.0.0.1"
os.environ["MQTT_BROKER_PORT"] = "18999"  # nothing listens here; boot guard tolerates it
os.environ["MQTT_TOPICS"] = "unit-json,unit-test"
os.environ["MQTT_TOPIC_JSON"] = "unit-json"
os.environ["MQTT_TEST_TOPIC"] = "unit-test"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"


def _ensure_test_db() -> None:
    conn = psycopg2.connect(
        host="localhost", user="postgres", password="localdev", dbname="postgres"
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        try:
            cur.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        except psycopg2.errors.DuplicateDatabase:
            pass
    conn.close()


_ensure_test_db()


@pytest.fixture(scope="session")
def app():
    try:  # post-refactor layout
        from app import create_app

        application = create_app()
    except ImportError:  # legacy import-time app
        from app import app as application

    from app import db

    with application.app_context():
        db.create_all()
    return application


@pytest.fixture()
def database(app):
    from app import db

    with app.app_context():
        db.session.execute(
            text(
                "TRUNCATE data_tracker, test_data, passage_event, user_room, device, room "
                "RESTART IDENTITY CASCADE"
            )
        )
        db.session.commit()
    yield db


@pytest.fixture()
def client(app, database):
    return app.test_client()


@pytest.fixture()
def make_token():
    def _make(exp_delta: int = 3600, secret: str = TEST_JWT_SECRET, **overrides):
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@local.test",
            "role": "authenticated",
            "aud": "authenticated",
            "iat": int(time.time()),
            "exp": int(time.time()) + exp_delta,
        }
        payload.update(overrides)
        return pyjwt.encode(payload, secret, algorithm="HS256")

    return _make


@pytest.fixture()
def auth_headers(make_token):
    return {"Authorization": f"Bearer {make_token()}"}


@pytest.fixture()
def make_room(app, database):
    def _make(name="Sala Teste", slug=None, tz="America/Sao_Paulo"):
        from app.models.room import Room

        with app.app_context():
            room = Room(name=name, slug=slug or f"room-{uuid.uuid4().hex[:8]}", timezone=tz)
            database.session.add(room)
            database.session.commit()
            database.session.refresh(room)
            database.session.expunge(room)
        return room

    return _make


@pytest.fixture()
def make_device(app, database, make_room):
    def _make(device_id="unit-sensor", room=None):
        from app.models.device import Device

        if room is None:
            room = make_room()
        with app.app_context():
            device = Device(id=device_id, room_id=room.id)
            database.session.add(device)
            database.session.commit()
            database.session.refresh(device)
            database.session.expunge(device)
        return device

    return _make


@pytest.fixture()
def grant_access(app, database):
    def _grant(user_id: str, room_id: int):
        from app.models.user_room import UserRoom

        with app.app_context():
            database.session.add(UserRoom(user_id=user_id, room_id=room_id))
            database.session.commit()

    return _grant


@pytest.fixture()
def insert_row(app, database):
    """Insert a data_tracker row with a chosen naive-UTC register_time."""

    def _insert(topic: str, payload: str, register_time: datetime):
        from app.models.data_tracker import DataTracker

        with app.app_context():
            database.session.add(
                DataTracker(topic=topic, payload=payload, register_time=register_time)
            )
            database.session.commit()

    return _insert
