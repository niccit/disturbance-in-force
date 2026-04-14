# SPDX-License-Identifier: MIT
import os
import time
import alarm.pin
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

# MQTT set up
mqtt_local_broker = os.getenv("mqtt_local_server")
mqtt_local_port = os.getenv("mqtt_local_port")
mqtt_local_username = os.getenv("mqtt_local_username_motion")
mqtt_local_key = os.getenv("mqtt_local_key_motion")

# Feeds for garage door sensor
garage_door_feed = os.getenv("garage_sensor_local_feed")

my_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=mqtt_local_broker
    , port = mqtt_local_port
    , username=mqtt_local_username
    , password=mqtt_local_key
    , socket_pool=pool
    , ssl_context=ssl_context
    , is_ssl=False
)
# Connect callback handlers for local mqtt_client
my_mqtt.on_connect = on_connect
my_mqtt.on_publish = on_publish
my_mqtt.on_disconnect = on_disconnect
my_mqtt.on_subscribe = on_subscribe

# --- Garage Door Sensor --- #
sensor_pin = board.A3

def set_up_sensor():
    garage_door_sensor = digitalio.DigitalInOut(sensor_pin)
    garage_door_sensor.direction = digitalio.Direction.INPUT
    garage_door_sensor.pull = digitalio.Pull.UP
    garage_door_switch = Debouncer(garage_door_sensor)

    return garage_door_sensor


# Publish messages to MQTT broker(s) or debug log if testing
def do_publish(feed, msg, retain=False):
    if not testing:
        try:
            my_mqtt.publish(feed, msg, retain)
        except MMQTTException as e:
            logger.error(f"unable to connect to local MQTT broker {e}. Nothing published")
            pass
    else:
        logger.debug(f"TESTING: Would publish {msg} to {feed} at remote broker")

# Pre-launch start up
last_known_state = False
startup = True
check_time = None
door_check_wait = 20 # 1800
garage_door_sensor = None
status = 2
my_mqtt.connect()
logger.info("Garage door sensor online")

# Main
while True:
    if garage_door_sensor is None:
        garage_door_sensor = set_up_sensor()
        status = garage_door_sensor.value

    try:
        my_mqtt.loop(timeout=5)
    except MMQTTException:
        logger.error("Local MMQT unavailable, will reconnect")
        my_mqtt.disconnect()
        pass

    if startup:
        logger.info("System has started, publishing to MQTT")
        do_publish(garage_door_feed, int(status), True)
        startup = False
        last_known_state = status
    elif last_known_state is not status and startup is False:
        logger.info("Garage door state has changed, publishing to MQTT")
        do_publish(garage_door_feed, int(status), True)
        last_known_state = status
    else:
        logger.debug("Nothing has changed, not publishing to MQTT")

    if garage_door_sensor is not None:
        garage_door_sensor.deinit()
        garage_door_sensor = None
    sleep_alarm = alarm.pin.PinAlarm(sensor_pin, value=False, edge=False)
    check_time = time.monotonic()
    logger.info(f"going into light sleep at {check_time}")
    alarm.light_sleep_until_alarms(sleep_alarm)



