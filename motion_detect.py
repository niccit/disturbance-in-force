# SPDX-License-Identifier: MIT
import os
import time
import board
import digitalio
import wifi
import adafruit_minimqtt.adafruit_minimqtt
from adafruit_minimqtt.adafruit_minimqtt import MMQTTException
import adafruit_connection_manager
import adafruit_logging

# --- Setup and Configuration --- #

is_recording = False

# Logging
logger = adafruit_logging.getLogger('motion_detect')

testing = False
if testing:
    logger.setLevel(adafruit_logging.DEBUG)
else:
    logger.setLevel(adafruit_logging.INFO)


# WiFi
connected = False
while not connected:
    try:
        wifi.radio.connect(os.getenv("CIRCUITPY_WIFI_SSID"), os.getenv("CIRCUITPY_WIFI_PASSWORD"))
        ipaddr = wifi.radio.ipv4_address
        logger.info(f"Connected to WiFi with IP {ipaddr}")
        connected = True
    except ConnectionError:
        logger.error("Failed to connect to WiFi")

# PIR Sensor
pir = digitalio.DigitalInOut(board.GP1)
pir.direction = digitalio.Direction.INPUT

# Set up socket
radio = wifi.radio
pool = adafruit_connection_manager.get_radio_socketpool(radio)

# MQTT set up
local_mqtt_broker = os.getenv("mqtt_local_server")
local_mqtt_port = os.getenv("mqtt_local_port")
local_mqtt_username = os.getenv("mqtt_local_username_motion")
local_mqtt_password = os.getenv("mqtt_local_key_motion")

motion_feed = os.getenv("motion_detect_local_feed")
recording_feed = os.getenv("local_recording_on_feed")

# MQTT specific helpers
def connect(mqtt_client, userdata, flags, rc):
    # This function will be called when the mqtt_client is connected
    # successfully to the broker.
    logger.info("Connected to MQTT Broker!")
    logger.debug(f"Flags: {flags}\n RC: {rc}")

def disconnect(mqtt_client, userdata, rc):
    # This method is called when the mqtt_client disconnects
    # from the broker.
    logger.info("Disconnected from MQTT Broker!")
    if rc == 1:
        my_mqtt.connect()
        my_mqtt.subscribe(recording_feed)

def subscribe(mqtt_client, userdata, topic, granted_qos):
    # This method is called when the mqtt_client subscribes to a new feed.
    logger.info(f"Subscribed to {topic} with QOS level {granted_qos}")

def unsubscribe(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client unsubscribes from a feed.
    logger.info(f"Unsubscribed from {topic} with PID {pid}")

def publish(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client publishes data to a feed.
    logger.info(f"Published to {topic} with PID {pid}")

def message(client, topic, message):
    global is_recording
    logger.debug(f"New message on topic {topic}: {message}")
    if "recording" in topic:
        if message is "1":
            is_recording = True
        else:
            is_recording = False

ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)

my_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=local_mqtt_broker
    , port=local_mqtt_port
    , username=local_mqtt_username
    , password=local_mqtt_password
    , ssl_context = ssl_context
    , socket_pool=pool
    , is_ssl=False
)

# Connect callback handlers to mqtt_client
my_mqtt.on_connect = connect
my_mqtt.on_disconnect = disconnect
my_mqtt.on_subscribe = subscribe
my_mqtt.on_unsubscribe = unsubscribe
my_mqtt.on_publish = publish
my_mqtt.on_message = message

# --- Non-MQTT Related Methods --- #

def do_publish(feed, msg):
    if testing:
        logger.info(f"Testing: would publish {msg} to {feed}")
    else:
        logger.info(f"preparing to publish {msg} to {feed}")
        try:
            my_mqtt.publish(feed, msg)
        except MMQTTException:
            print("unable to connect to remote MQTT broker")
            raise

# --- Pre start setup --- #
is_motion_detect = False

my_mqtt.connect()

my_mqtt.connect()
my_mqtt.subscribe(recording_feed)

# --- Startup --- #
logger.info("motion detector online")
while True:
    my_mqtt.loop(timeout=5)
    if pir.value is not is_motion_detect and not is_recording:
        if pir.value:
            do_publish(motion_feed, 1)
            logger.debug("motion detected")
            is_motion_detect = True
        else:
            is_motion_detect = False

    time.sleep(0.25)