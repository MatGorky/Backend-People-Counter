import paho.mqtt.client as mqtt
from app import db 
from app.models.testdata import TestData
from app.models.data_tracker import DataTracker


class MQTTSubscriber:
    def __init__(self, app, broker='broker.hivemq.com', port=1883, topic=["test-data-438",]):
        self.app = app
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.topic_handlers = {
            "test-data-438": self.handle_test_data,
        }

    def handle_test_data(self, payload):
        with self.app.app_context():
            new_data = TestData(value=payload)
            db.session.add(new_data)
            db.session.commit()

    def handle_default(self, topic, payload):
        with self.app.app_context():
            new_data = DataTracker(topic=topic, payload=payload)
            db.session.add(new_data)
            db.session.commit()

    def on_connect(self, client, userdata, flags, rc):
        print("Connected  with result code " + str(rc))
        for topic in self.topic:
            client.subscribe(topic)
        print("subscribed")

    def on_message(self, client, userdata, msg):
        print("a")
        payload = msg.payload.decode("utf-8")
        print(f"Received message: {payload}")
        
        if msg.topic in self.topic_handlers:
            self.topic_handlers[msg.topic](payload)
        else:
            self.handle_default(msg.topic, payload)


    def start(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

if __name__ == '__main__':
    from app import app

    subscriber = MQTTSubscriber(app)
    subscriber.start()