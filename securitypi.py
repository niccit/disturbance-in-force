# SPDX-License-Identifier: MIT
import base64
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder
from picamera2.outputs import PyavOutput, FileOutput

# A RaspberryPi 4 based security camera
# Camera module 3 with noir and infrared LED light board module
# Will provide live stream and publish still images to MQTT

# load .env
load_dotenv()


# Pi Camera
picam = Picamera2()

# Video Feed
main = {'size': (1920, 1080), 'format': 'YUV420'}
lores = {'size': (1920, 1080), 'format': 'YUV420'}
capture = {'size': (1280, 720), 'format': 'YUV420'}
controls = {'FrameRate': 30}
config = picam.create_video_configuration(main, controls=controls, lores=lores, display="lores")
picam.configure(config)

encoder = MJPEGEncoder()
output_live = PyavOutput("rtsp:192.168.68.70:8554/cam", format="rtsp")
output_capture = FileOutput()
encoder.output = [output_live, output_capture]

still_config = picam.create_still_configuration(main)

# Set testing to True to turn off publish to MQTT
# Good for active development while code is running
testing = False

# Set the log level based on if we're testing or not
if testing:
    LOG_LEVEL = logging.DEBUG
    weather_wait = 60
else:
    LOG_LEVEL = logging.INFO
    weather_wait = 600  # Weather doesn't change that fast, update once every 10 minutes (600)

# Set up the logger
log_file = "/home/picam/sec_cam/picam.log"
logging.basicConfig(filename=log_file, level=LOG_LEVEL)
logger = logging.getLogger(__name__)

mqtt_server = os.getenv('MQTT_LOCAL_SERVER')
ca_cert_file = os.getenv('MQTT_CA_CERT')
client_pem = os.getenv('MQTT_CLIENT_PEM')
client_username = os.getenv('MQTT_USERNAME')
client_password = os.getenv('MQTT_PASSWORD')

# MQTT Publish feeds
camera_feed = os.getenv('LOCAL_CAMERA_FEED')
recording_feed = os.getenv('LOCAL_RECORDING_ON_FEED')

feeds_list=[]
# MQTT Subscribe feeds
motion_feed = os.getenv('LOCAL_MOTION_FEED')
feeds_list.append(motion_feed)


# --- MQTT methods for handling traffic --- #

def connect_mqtt():
    # Set Connecting Client ID
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set(ca_certs=ca_cert_file, certfile=client_pem, keyfile=None, keyfile_password=None)
    client.username_pw_set(client_username, client_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    client.connect(mqtt_server, 8883, 60)
    return client

def sub_feeds():
    for feed in feeds_list:
        subscribe(sub_mqtt, feed)
        logger.info(f"subscribed sub_mqtt to {feed}")

    sub_mqtt.loop_start()



# Connect method for MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"connect has been called with {rc}")
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
        logger.info("message payload is %s for topic %s", received_msg, msg.topic)
        motion_detected()

    client.on_message = on_message
    client.subscribe(topic)


# Publish to MQTT
def do_publish(feed, data):
    if not testing:
        logger.info("Publishing to %s", feed)
        pub_mqtt.publish(feed, data)
    else:
        logger.debug("TESTING:")
        logger.debug("Would publish: Topic: %s. Payload: %s", str(feed), str(data))


# --- Non MQTT specific helpers --- #


# Get the time from system clock
def get_date_time():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d/%m/%Y")
    return current_time, current_date

def motion_detected():
    logger.info("motion detected has been called")
    do_publish(recording_feed, 1)
    picam.capture_file("image.jpg", format='jpeg')
    with open("image.jpg", mode='rb') as file:
        image_content = file.read()
        base64_bytes = base64.b64encode(image_content)
        base64_message = base64_bytes.decode("ascii")
    file.close()
    do_publish(camera_feed, base64_message)
    capture_clip()

capture_run_time = os.getenv("VIDEO_CAPTURE_TIME")
def capture_clip():
    logger.info("capture clip has been called")
    record = True
    end_time = time.monotonic() + int(capture_run_time)
    output_capture.fileoutput = "test.mp4"
    output_capture.start()
    while record:
        if time.monotonic() > end_time:
            output_capture.stop()
            record = False
    logger.info("capture clip finished")
    do_publish(recording_feed, 0)



# --- Prep for start of main --- #

logger.info("Connecting publish MQTT client")
pub_mqtt = connect_mqtt()
pub_mqtt.loop_start()
logger.info("Connecting subscribe MQTT client")
sub_mqtt = connect_mqtt()

# If there are feeds to subscribe to, do so
if feeds_list:
    logger.info("I have feeds to subscribe to")
    sub_feeds()

logger.info("Camera starting")
picam.start_encoder(encoder)
picam.start()
time.sleep(5)

try:
    while True:
        time.sleep(0.25)
except KeyboardInterrupt:
    logger.info("Camera stopped")

