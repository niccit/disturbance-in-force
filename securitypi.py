# SPDX-License-Identifier: MIT
import base64
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
from libcamera import Transform
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
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
config = picam.create_video_configuration(main, controls=controls, lores=lores, display="lores", transform=Transform(hflip=False, vflip=True))
picam.configure(config)

encoder = H264Encoder()
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
else:
    LOG_LEVEL = logging.INFO

# Set up the logger
log_file = "/home/picam/sec_cam/picam.log"
logging.basicConfig(filename=log_file, level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# MQTT data for connecting
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

client_type = "pub"

# Set up MQTT client and connect to broker
def connect_mqtt(client_id):
    global client_type
    # Set Connecting Client ID
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set(ca_certs=ca_cert_file, certfile=client_pem, keyfile=None, keyfile_password=None)
    client.username_pw_set(client_username, client_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(mqtt_server, 8883, 60)
    if client_id == "sub":
        client_type = client_id

    return client

# Connect method ro MQTT
# What to do when the client connects
def on_connect(client, userdata, flags, reason_code, properties):
    global client_type
    logger.info("Connected to MQTT Broker!")
    # Subscribe to any feeds
    if client_type == "sub":
        if feeds_list:
            for feed in feeds_list:
                client.subscribe(feed, qos=1)
                logger.info(f"subscribed sub_mqtt to {feed}")
        client_type = "publish_client"

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

# Subscribe method for MQTT
# What to do when the subscriber gets a message
def on_message(client, userdata, msg):
    received_msg = msg.payload.decode("utf-8")
    logger.info("message payload is %s for topic %s", received_msg, msg.topic)
    logger.info("received message is of type", type(received_msg))
    if "motion" in msg.topic:
        if "1" in received_msg:
            logger.info("motion detected")
            start_recording()

# Publish to MQTT
# Since subsequent publishes are done we need to ensure the publishes happen at the time of call
# and that they are successful before proceeding
# to do this we use the wait_for_publish method
def do_publish(feed, data):
    msg_info = None
    if not testing:
        logger.info("Publishing to %s", feed)
        msg_info = pub_mqtt.publish(feed, data, qos=1)
        msg_info.wait_for_publish(timeout=10)
    else:
        logger.debug("TESTING:")
        logger.debug("Would publish: Topic: %s. Payload: %s", str(feed), str(data))

    return msg_info

# --- Non MQTT specific helpers --- #

# Get the time from system clock
# Format it for use
def get_date_time():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    current_date = now.strftime("%d/%m/%Y")
    return current_time, current_date

def start_recording():
    logger.info("start recording has been called")
    publish_result = do_publish(recording_feed, 1)
    if publish_result.rc == 0:
        logger.info("publish successful, proceeding")
        motion_detected()
    else:
        logger.info("publish failed, not proceeding")
    logger.info("start recording finished")

# Behavior when motion is detected
# Capture and image, base64 encode it, and send to MQTT
# Call capture_clip to grab a portion of the live feed and save it to a file
def motion_detected():
    logger.info("motion detected has been called")
    picam.capture_file("image.jpg", format='jpeg')
    with open("image.jpg", mode='rb') as file:
        image_content = file.read()
        base64_bytes = base64.b64encode(image_content)
        base64_message = base64_bytes.decode("ascii")
    file.close()
    publish_result = do_publish(camera_feed, base64_message)
    if publish_result.rc == 0:
        logger.info("publish successful, proceeding")
        capture_clip()
    else:
        logger.info("publish failed, not proceeding")
    logger.info("motion detected finished")

# Capture a portion of the live feed to save to a file
# Store clips on local fileserver (**TO-DO**)
# If a flag is set upload clip to Google Drive (**To-DO**)
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
    # Let subscribers know recording is complete and any new motion can be detected
    do_publish(recording_feed, 0)
    logger.info("capture clip finished")

local_storage = 0
def copy_video_to_server():
    if local_storage:
        logger.info("will copy to local storage")
    else:
        logger.info("will copy to remote storage")


# --- Prep for start of main --- #

# Connect to MQTT and start loop
logger.info("Connecting publish MQTT client")
pub_mqtt = connect_mqtt(client_type)
sub_mqtt = connect_mqtt("sub")

# Start camera live feed
logger.info("Camera starting")
picam.start_encoder(encoder)
picam.start()
time.sleep(5)

try:
    while True:
        pub_mqtt.loop_start()
        sub_mqtt.loop_start()
        time.sleep(0.25)
except KeyboardInterrupt:
    # If receive keyboard interrupt, stop camera
    picam.stop()
    logger.info("Camera stopped")