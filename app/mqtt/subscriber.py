import paho.mqtt.client as mqtt
from app import db 
from app.models.testdata import TestData
from app.models.data_tracker import DataTracker
import uuid


class MQTTSubscriber:
    def __init__(self, app, broker='broker.hivemq.com', port=1883, topic=None, test_topic=None):
        self.app = app
        self.broker = broker
        self.port = port
        self.topic = topic or []
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id = f'nce-client-{uuid.uuid4()}')
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.topic_handlers = {}
        if test_topic:
            self.topic_handlers[test_topic] = self.handle_test_data

    def handle_test_data(self, payload):
        with self.app.app_context():
            new_data = TestData(value=payload)
            db.session.add(new_data)
            db.session.commit()

    def handle_default(self, topic, payload):
        payload = payload.replace("\n", "").replace("\r", "")
        with self.app.app_context():
            new_data = DataTracker(topic=topic, payload=payload)
            db.session.add(new_data)
            db.session.commit()

    def on_connect(self, client, userdata, flags, reason_code,properties):
        if reason_code == 0:
            print(f"Connected  with result code {reason_code}")
            for topic in self.topic:
                client.subscribe(topic)
        
        if reason_code > 0:
            print(f"Error: {reason_code}")

    def on_disconnect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Disconnected")
        if reason_code > 0:
            print(f"Disconnection Error: {reason_code}")

    def on_message(self, client, userdata, msg):
        try: 
            payload = msg.payload.decode("utf-8")
            
            print(f"Received message: {payload}")
            
            if msg.topic in self.topic_handlers:
                self.topic_handlers[msg.topic](payload)
            else:
                self.handle_default(msg.topic, payload)
        except Exception as e:
            print(f"Error handling mqtt message: {e}")


    def start(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()

if __name__ == '__main__':
    from app import app

    subscriber = MQTTSubscriber(app)
    subscriber.start()