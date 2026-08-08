"""Production entrypoint (gunicorn target): web API + in-process MQTT subscriber.

The subscriber rides inside the web process until spec-008 moves it to its own
VM worker (app/mqtt_worker.py) and this file drops the build_and_start call.
"""

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import create_app  # noqa: E402
from app.mqtt.subscriber import build_and_start  # noqa: E402

app = create_app()
mqtt_subscriber = build_and_start(app)
