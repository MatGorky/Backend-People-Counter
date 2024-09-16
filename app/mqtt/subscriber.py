import paho.mqtt.client as mqtt
from app import db 
from app.models.testdata import TestData


class MQTTSubscriber:
    def __init__(self, app, broker='broker.hivemq.com', port=1883, topic="test45728"):
        self.app = app
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        print("Connected  with result code " + str(rc))
        client.subscribe(self.topic)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode("utf-8")
        print(f"Received message: {payload}")

        with self.app.app_context():
            new_data = TestData(value=payload)
            db.session.add(new_data)
            db.session.commit()

    def start(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

if __name__ == '__main__':
    from app import app

    subscriber = MQTTSubscriber(app)
    subscriber.start()