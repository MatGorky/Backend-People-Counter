"""Run the API + MQTT subscriber locally with .env loaded — shell-agnostic.

    python scripts/run_api.py            # http://localhost:8080, Swagger UI at /

The reloader is disabled on purpose: reloading re-imports the app, which would start
a second MQTT subscriber. Restart manually after changes.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from app import create_app  # noqa: E402
from app.mqtt.subscriber import build_and_start  # noqa: E402

app = create_app()
build_and_start(app)

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8080")),
        debug=True,
        use_reloader=False,
    )
