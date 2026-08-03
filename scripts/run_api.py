"""Run the API locally with .env loaded — shell-agnostic (works from any terminal).

    python scripts/run_api.py            # http://localhost:8080, Swagger UI at /

The reloader is disabled on purpose: reloading re-imports the app, which would start
a second MQTT subscriber (see BUG-8 / spec-001). Restart manually after changes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402

load_dotenv()

from app import app  # noqa: E402

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")), debug=True, use_reloader=False)
