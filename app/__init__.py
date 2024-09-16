from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
api = Api(app)

app.config.from_object('app.config.DevelopmentConfig')

db = SQLAlchemy(app)
        

from app.apis.testdata import api as test_ns
api.add_namespace(test_ns)

from app.mqtt import subscriber
mqtt_subscriber = subscriber.MQTTSubscriber(app) 
mqtt_subscriber.start()