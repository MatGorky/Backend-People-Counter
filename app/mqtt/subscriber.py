import paho.mqtt.client as mqtt
from app import db 
from app.models.testdata import TestData

broker = 'broker.hivemq.com'
port = 1883

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    
    client.subscribe("test45728")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"Received message: {payload}")

    new_data = TestData(value=payload)  
    db.session.add(new_data)
    db.session.commit()

def start_subscriber():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    client.connect(broker, port, 60)

    # Start the MQTT network loop to listen for messages
    client.loop_forever()

if __name__ == '__main__':
    start_subscriber()