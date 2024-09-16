from flask import Flask
from flask_restx import Api
from flask_sqlalchemy import SQLAlchemy
from app.mqtt import subscriber
import threading

app = Flask(__name__)
api = Api(app)

app.config.from_object('app.config.DevelopmentConfig')

db = SQLAlchemy(app)
        

from app.apis.testdata import api as test_ns
api.add_namespace(test_ns)


mqtt_thread = threading.Thread(target=subscriber.start_subscriber)
mqtt_thread.start()