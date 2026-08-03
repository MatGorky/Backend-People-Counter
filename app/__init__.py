from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from flask_cors import CORS

app = Flask(__name__)

app.config.from_object('app.config.DevelopmentConfig')

CORS(app, origins=app.config['CORS_ORIGINS'])
api = Api(app)

db = SQLAlchemy(app,metadata=MetaData(naming_convention={
    'pk': 'pk_%(table_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'ix': 'ix_%(table_name)s_%(column_0_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
}))

print("service started")

#rest api
from app.apis.data_tracker import api as data_tracker_ns
api.add_namespace(data_tracker_ns)

#MQTT subscriber
from app.mqtt import subscriber
if not app.config['MQTT_TOPICS']:
    print("WARNING: MQTT_TOPICS is empty - the subscriber will receive nothing. "
          "Topic names are unlisted; set them in .env / deploy env (docs/secrets.md).")
mqtt_subscriber = subscriber.MQTTSubscriber(
    app,
    broker=app.config['MQTT_BROKER_HOST'],
    port=app.config['MQTT_BROKER_PORT'],
    topic=app.config['MQTT_TOPICS'],
    test_topic=app.config['MQTT_TEST_TOPIC'] or None,
)
try:
    mqtt_subscriber.start()
except Exception as e:
    # An unreachable broker must not take the REST API down with it.
    # Proper lifecycle management (separate worker entrypoint) comes with spec-001.
    print(f"WARNING: MQTT subscriber failed to start: {e}")
