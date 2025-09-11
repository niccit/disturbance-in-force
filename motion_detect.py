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
import adafruit_ntp

# --- Setup and Configuration --- #

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
def on_connect(mqtt_client, userdata, flags, rc):
    # This function will be called when the mqtt_client is connected
    # successfully to the broker.
    logger.info("Connected to MQTT Broker!")
    logger.debug(f"Flags: {flags}\n RC: {rc}")
    my_mqtt.subscribe(recording_feed)
    logger.info(f"Subscribed to {recording_feed}")

def on_disconnect(mqtt_client, userdata, rc):
    # This method is called when the mqtt_client disconnects
    # from the broker.
    logger.info("Disconnected from MQTT Broker!")
    logger.info(f"Disconnected from MQTT Broker!")
    counter = 0
    while counter <= 10:
        try:
            my_mqtt.reconnect()
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

is_recording = False
def on_message(client, topic, message):
    global is_recording
    logger.info(f"New message on topic {topic}: {message}")
    if "recording" in topic:
        if message is "1":
            if not is_recording:
                is_recording = True
        if message is "0":
            if is_recording:
                is_recording = False

        logger.info(f"recording state={is_recording}")

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
my_mqtt.on_connect = on_connect
my_mqtt.on_disconnect = on_disconnect
my_mqtt.on_subscribe = on_subscribe
my_mqtt.on_unsubscribe = on_unsubscribe
my_mqtt.on_publish = on_publish
my_mqtt.on_message = on_message

# --- Non-MQTT Related Methods --- #

def do_publish(feed, msg):
    if testing:
        logger.info(f"Testing: would publish {msg} to {feed}")
    else:
        logger.info(f"preparing to publish {msg} to {feed}")
        try:
            my_mqtt.publish(feed, msg)
        except MMQTTException:
            print("unable to connect to remote MQTT broker, message not sent")
            pass
        except BrokenPipeError:
            my_mqtt.disconnect()
            my_mqtt.publish(feed, msg)

def get_time():
    try:
        ntp_datetime = adafruit_ntp.NTP(pool, tz_offset=-10)
        now = ntp_datetime.datetime
        now_date = "{:02}{:02}{:04}".format(now.tm_mday, now.tm_mon, now.tm_year)
        now_time = "{:02}:{:02}:{:02}".format(now.tm_hour, now.tm_min, now.tm_sec)
        my_timestamp = f"{now_date}-{now_time}"
    except OSError as e:
        my_timestamp = "00000000-00:00:00"
    except OverflowError as e:
        my_timestamp = "00000000-00:00:00"

    return my_timestamp

def motion_detected():
    if not is_recording:
        logger.info(f"motion detected and we are not currently recording")
        do_publish(motion_feed, 1)
        time.sleep(5)
        do_publish(motion_feed, 0)
    else:
        logger.info(f"we are recording, nothing more to do")

# --- Pre start setup --- #
my_mqtt.connect()

do_publish(motion_feed, 0)

# --- Startup --- #
logger.info("motion detector online")
while True:
    try:
        my_mqtt.loop(timeout=5)
    except MMQTTException:
        logger.error("MMQT unavailable, will reconnect")
        my_mqtt.disconnect()
        pass

    if pir.value:
        print("motion detected")
        motion_detected()

    time.sleep(0.25)