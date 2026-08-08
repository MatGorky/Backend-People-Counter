"""Standalone MQTT worker — the spec-008 VM entrypoint. No web server.

python -m app.mqtt_worker
"""

import logging
import signal
import threading

from app import create_app
from app.mqtt.subscriber import build_and_start


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = create_app()
    build_and_start(app, required=True)

    stop = threading.Event()

    def _handle(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    stop.wait()


if __name__ == "__main__":
    main()
