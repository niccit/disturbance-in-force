# SPDX-License-Identifier: MIT
import os
import time
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging

# load .env
load_dotenv()

# MQTT Publish feeds
camera_feed = os.getenv('LOCAL_CAMERA_FEED')

# Set testing to True to turn off publish to MQTT
# Good for active development while code is running
testing = True

# Set the log level based on if we're testing or not
if testing:
    LOG_LEVEL = logging.DEBUG
    weather_wait = 60
else:
    LOG_LEVEL = logging.INFO
    weather_wait = 600  # Weather doesn't change that fast, update once every 10 minutes (600)

# Set up the logger
# logging.basicConfig(filename="picam.log", level=LOG_LEVEL)
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

mqtt_server = os.getenv('MQTT_LOCAL_SERVER')
ca_cert_file = os.getenv('MQTT_CA_CERT')
client_username = os.getenv('MQTT_USERNAME')
client_password = os.getenv('MQTT_PASSWORD')

# Connect to the specified MQTT server
def connect_mqtt():
    # Set Connecting Client ID
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set(ca_certs=ca_cert_file)
    client.username_pw_set(username=client_username, password=client_password)

    client.on_connect = on_connect
    client.disconnect = on_disconnect
    client.connect(mqtt_server, 8883, 60)
    return client

# --- MQTT methods for handling traffic --- #

# Connect method for MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
    else:
        logger.error("Failed to connect, return code %d\n", rc)

# Disconnect method for MQTT
# Auto reconnect logic
FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60
def on_disconnect(client, userdata, rc):
    logger.info("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        logger.info("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)
        try:
            client.reconnect()
            logger.info("Reconnected successfully!")
            return
        except Exception as err:
            logger.error("%s. Reconnect failed. Retrying...", err)
        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    logger.error("Reconnect failed after %s attempts. Exiting...", reconnect_count)

# Subscribe logic when subscribing to an MQTT feed
def subscribe(client, topic):
    def on_message(client, userdata, msg):
        received_msg = msg.payload.decode("utf-8")
        logger.debug("message payload is %s for topic %s", received_msg, msg.topic)
    client.subscribe(topic)
    client.on_message = on_message

# Publish to MQTT
def do_publish(feed, data):
    if not testing:
        logger.debug("I am publishing %s to %s", data, feed)
        pub_mqtt.loop_start()
        pub_mqtt.publish(feed, data)
        pub_mqtt.loop_stop()
    else:
        logger.debug("TESTING:")
        logger.debug("Would publish: Topic: %s. Payload: %s", str(feed), str(data))

pub_mqtt = connect_mqtt()

