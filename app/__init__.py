"""Application factory. Importing this package has no side effects; composition
roots (wsgi.py, app/mqtt_worker.py, scripts/run_api.py) decide what to start."""

from flask import Flask
from flask_cors import CORS
from flask_restx import Api

from app.extensions import db  # re-exported for convenience  # noqa: F401


def create_app(config_object: str = "app.config.Config") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    CORS(app, origins=app.config["CORS_ORIGINS"])
    db.init_app(app)

    api = Api(app, title="People Counter API", doc="/")
    from app.apis.data_tracker import api as data_tracker_ns

    api.add_namespace(data_tracker_ns)

    # Ensure all tables are registered on db.metadata. NB: must be a `from` import —
    # `import app.models` would rebind the local name `app` to the package.
    from app import models  # noqa: F401

    return app
