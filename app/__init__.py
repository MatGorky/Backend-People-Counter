from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
api = Api(app)

app.config.from_object('app.config.DevelopmentConfig')

db = SQLAlchemy(app,metadata=MetaData(naming_convention={
    'pk': 'pk_%(table_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'ix': 'ix_%(table_name)s_%(column_0_name)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
}))

print("service started")

#rest api
from app.apis.testdata import api as test_ns
from app.apis.data_tracker import api as data_tracker_ns
api.add_namespace(test_ns)
api.add_namespace(data_tracker_ns)

#MQTT subscriber
from app.mqtt import subscriber
mqtt_subscriber = subscriber.MQTTSubscriber(app,topic = app.config['MQTT_TOPICS'])
mqtt_subscriber.start()