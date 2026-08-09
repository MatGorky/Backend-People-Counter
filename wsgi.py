"""Production entrypoint (gunicorn target): web API, optionally + in-process MQTT.

With the spec-008 VM worker running (app/mqtt_worker.py), set
MQTT_SUBSCRIBER_IN_WEB=false so the web process serves HTTP only and Cloud Run
can scale to zero. Default is "true" for backward compatibility.
"""

import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import create_app  # noqa: E402
from app.mqtt.subscriber import build_and_start  # noqa: E402

app = create_app()

mqtt_subscriber = None
if os.environ.get("MQTT_SUBSCRIBER_IN_WEB", "true").lower() != "false":
    mqtt_subscriber = build_and_start(app)
else:
    logging.getLogger(__name__).info(
        "MQTT subscriber disabled in web process (runs on the dedicated worker)"
    )
