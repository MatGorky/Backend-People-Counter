from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
api = Api(app)

app.config.from_object('app.config.DevelopmentConfig')

db = SQLAlchemy(app)

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