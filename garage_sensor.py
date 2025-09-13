# SPDX-License-Identifier: MIT
import os
import time
import board
import digitalio
import wifi
from adafruit_debouncer import Debouncer
import adafruit_minimqtt.adafruit_minimqtt
from adafruit_minimqtt.adafruit_minimqtt import MMQTTException
import adafruit_connection_manager
import adafruit_logging

# Logging
logger = adafruit_logging.getLogger('garage_sensor')

# Switch to not publish if in test mode
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
        ssid = wifi.radio.ap_info.ssid
        logger.info(f"Connected to WiFi {ssid}!")
        connected = True
    except ConnectionError:
        logger.error("Failed to connect to WiFi")

# --- MQTT --- #
# Config
radio = wifi.radio
pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)

# MQTT specific helpers
def on_connect(mqtt_client, userdata, flags, rc):
    # This function will be called when the mqtt_client is connected
    # successfully to the broker.
    logger.info(f"Connected to MQTT Broker {mqtt_client.broker}!")
    logger.debug(f"Flags: {flags}\n RC: {rc}")

def on_disconnect(mqtt_client, userdata, rc):
    # This method is called when the mqtt_client disconnects
    # from the broker.
    logger.info(f"{mqtt_client} Disconnected from MQTT Broker!")
    counter = 0
    while counter <= 10:
        try:
            mqtt_client.reconnect()
            counter = 11
        except MMQTTException:
            counter += 1
            time.sleep(1)
            pass

def on_subscribe(mqtt_client, userdata, topic, granted_qos):
    # This method is called when the mqtt_client subscribes to a new feed.
    logger.info(f"Subscribed to {topic} with QOS level {granted_qos}")

def on_unsubscribe(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client unsubscribes from a feed.
    logger.info(f"Unsubscribed from {topic} with PID {pid}")

def on_publish(mqtt_client, userdata, topic, pid):
    # This method is called when the mqtt_client publishes data to a feed.
    logger.info(f"Published to {topic} with PID {pid}")

def on_message(client, topic, message):
    logger.info(f"New message on topic {topic}: {message}")

# Set up clients
# Remote
mqtt_remote_broker = os.getenv("mqtt_remote_server")
mqtt_remote_username = os.getenv("mqtt_remote_username")
mqtt_remote_key = os.getenv("mqtt_remote_key")
remote_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=mqtt_remote_broker
    , username=mqtt_remote_username
    , password=mqtt_remote_key
    , socket_pool=pool
    , ssl_context=ssl_context
    , is_ssl=True
)
# Connect callback handlers for remote mqtt_client
remote_mqtt.on_connect = on_connect
remote_mqtt.on_publish = on_publish
remote_mqtt.on_disconnect = on_disconnect
remote_mqtt.on_subscribe = on_subscribe

# Local
mqtt_local_broker = os.getenv("mqtt_local_server")
mqtt_local_port = os.getenv("mqtt_local_port")
mqtt_local_username = os.getenv("mqtt_local_username_motion")
mqtt_local_key = os.getenv("mqtt_local_key_motion")
local_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=mqtt_local_broker
    , port = mqtt_local_port
    , username=mqtt_local_username
    , password=mqtt_local_key
    , socket_pool=pool
    , ssl_context=ssl_context
    , is_ssl=False
)
# Connect callback handlers for local mqtt_client
local_mqtt.on_connect = on_connect
local_mqtt.on_publish = on_publish
local_mqtt.on_disconnect = on_disconnect
local_mqtt.on_subscribe = on_subscribe

# Feed for garage door sensor
garage_door_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_remote_feed")
garage_door_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_icon_remote_feed")
garage_door_local_feed = os.getenv("garage_sensor_local_feed")

# Garage Door Sensor
garage_door_sensor=digitalio.DigitalInOut(board.A3)
garage_door_sensor.direction = digitalio.Direction.INPUT
garage_door_sensor.pull = digitalio.Pull.UP
garage_door_switch = Debouncer(garage_door_sensor)
door_check_wait = 20 # 1800

# Format message for publish
def get_publish_message(garage_status):
    if garage_status:
        msg = "Garage door is open"
        msg_icon = "frown-o"
    else:
        msg = "Garage door is closed"
        msg_icon = "smile-o"
    return msg, msg_icon

# Publish messages to MQTT broker(s) or debug log if testing
def do_publish(feed, msg):
    if not testing:
        # Remote
        try:
            remote_mqtt.publish(feed, msg)
        except MMQTTException as e:
            logger.error(f"unable to connect to remote MQTT broker {e}. Nothing published")
            pass
        # Local
        try:
            if "ntynen" not in feed:
                logger.info("publishing to local mqtt feed")
                local_mqtt.publish(feed, msg)
        except MMQTTException as e:
            logger.error(f"unable to connect to local MQTT broker {e}. Nothing published")
            pass
    else:
        logger.debug(f"TESTING: Would publish {msg} to {feed} at remote broker")

# Pre-launch start up
last_known_state = False
startup = True
remote_mqtt.connect()
local_mqtt.connect()
logger.info("Garage door sensor online")

# Main
while True:
    status = garage_door_sensor.value
    try:
        remote_mqtt.loop(timeout=5)
    except MMQTTException:
        logger.error("Remote MMQT unavailable, will reconnect")
        remote_mqtt.disconnect()
        pass
    try:
        local_mqtt.loop(timeout=5)
    except MMQTTException:
        logger.error("Local MMQT unavailable, will reconnect")
        local_mqtt.disconnect()

    if startup:
        logger.info("System has started, publishing to MQTT")
        pub_msg, icon = get_publish_message(status)
        do_publish(garage_door_icon_feed, icon)
        do_publish(garage_door_feed, pub_msg)
        do_publish(garage_door_local_feed, pub_msg)
        startup = False
        last_known_state = status
    elif last_known_state is not status and startup is False:
        logger.info("Garage door state has changed, publishing to MQTT")
        pub_msg, icon = get_publish_message(status)
        do_publish(garage_door_icon_feed, icon)
        do_publish(garage_door_feed, pub_msg)
        last_known_state = status
    else:
        logger.debug("Nothing has changed, not publishing to MQTT")

    time.sleep(door_check_wait)


