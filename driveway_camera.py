# SPDX-License-Identifier: MIT
import base64
import time
import os
import paramiko
from scp import SCPClient
import uuid
from datetime import datetime
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
from libcamera import Transform
from picamera2.outputs import PyavOutput, FileOutput
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
import dropbox
from dropbox.exceptions import AuthError

# A RaspberryPi 4 based security camera
# Using the RaspberryPi camera module 3 with noir and infrared LED light board
# Will provide live stream and publish still images to MQTT
# Will upload image and video capture files to local and remote storage

# load .env
load_dotenv()

# Pi Camera Setup
tuning = Picamera2.load_tuning_file("imx219_noir.json")
picam = Picamera2(tuning=tuning)

# Video file name - use the same one and overwrite
tmp_video = "temp_video"
video_encoding = "mp4"
filename = tmp_video + "." + video_encoding
# Configuration for video
main = {'size': (1920, 1080), 'format': 'YUV420'}
lores = {'size': (1920, 1080), 'format': 'YUV420'}
capture = {'size': (1280, 720), 'format': 'YUV420'}
controls = ({'FrameRate': 30})
config = picam.create_video_configuration(main, controls=controls, lores=lores, display="lores", transform=Transform(hflip=False, vflip=True))
picam.configure(config)
# Video set up - stream and capture
encoder = H264Encoder()
output_live = PyavOutput("rtsp:192.168.68.70:8554/cam", format="rtsp")
output_capture = FileOutput()
encoder.output = [output_live, output_capture]
# Snap a picture on motion detect
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

# SSH Connection
ssh_username = os.getenv("FILE_SERVER_USERNAME")
ssh_password = os.getenv("FILE_SERVER_PASSWORD")
file_server_ip = os.getenv("FILE_SERVER_IP")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# MQTT data for connecting
mqtt_server = os.getenv('MQTT_LOCAL_SERVER')
ca_cert_file = os.getenv('MQTT_CA_CERT')
client_pem = os.getenv('MQTT_CLIENT_PEM')
client_username = os.getenv('MQTT_USERNAME')
client_password = os.getenv('MQTT_PASSWORD')

# MQTT Publish feeds
camera_feed = os.getenv('LOCAL_CAMERA_FEED')
recording_feed = os.getenv('LOCAL_RECORDING_ON_FEED')

# MQTT Subscribe feeds
feeds_list=[]
motion_feed = os.getenv('LOCAL_MOTION_FEED')
feeds_list.append(motion_feed)

# Where to publish stills and video clips - local, remote, both
# By default local
storage = "local"
logger.info(f"storage options is {storage}")

# Date and time, formatted. Used for upload filenaming
current_date, current_time = None, None

# --- MQTT methods for handling traffic --- #

# Set up MQTT client and connect to broker
def connect_mqtt(cname):
    client_id = f'{cname}-mqtt-client-{uuid.getnode()}'
    # Set Connecting Client ID
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.client_id = client_id
    client.tls_set(ca_certs=ca_cert_file, certfile=client_pem, keyfile=None, keyfile_password=None)
    client.username_pw_set(client_username, client_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    if "sub" in client.client_id:
        client.connect_async(mqtt_server, 8883, 60, clean_start=True)
    else:
        client.connect_async(mqtt_server, 8883, 60)

    return client

# Connect method ro MQTT
# What to do when the client connects
def on_connect(client, userdata, flags, reason_code, properties):
    global is_recording
    logger.info(f"Connected to {client.client_id} MQTT Broker!")
    if "sub" in client.client_id:
        # Subscribe to any feeds
        if feeds_list:
            for feed in feeds_list:
                client.subscribe(feed)
                logger.info(f"subscribed sub_mqtt to {feed}")
        else:
            logger.info("there are no feeds in the list")


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
    global storage, current_date, current_time
    received_msg = msg.payload.decode("utf-8")
    logger.info("message payload is %s for topic %s", received_msg, msg.topic)
    # Handle motion detection
    if "motion" in msg.topic:
        if "1" in received_msg:
            logger.info(f"{client.client_id} received message {received_msg} for topic {msg.topic}")
            current_date, current_time = get_date_time()
            start_recording()
        else:
            logger.info(f"{client.client_id} received message {received_msg} for topic {msg.topic}")
    # Handle storage assignment
    if "file" in msg.topic:
        storage = received_msg

# Publish to MQTT
# Since subsequent publishes are done we need to ensure the publishes happen at the time of call
# and that they are successful before proceeding
# to do this we use the wait_for_publish method
# If the testing flag is enabled, print what would normally be published to MQTT
def do_publish(feed, data):
    if testing:
        logger.info("Publishing to %s", feed)
        result = pub_mqtt.publish(feed, data)
        result.wait_for_publish()
        return result
    else:
        logger.debug("TESTING:")
        logger.debug("Would publish: Topic: %s. Payload: %s", str(feed), str(data))
        return "TESTING"

# --- Non MQTT specific helpers --- #

# Get the time from system clock and format it in human-readable formate
def get_date_time():
    now = datetime.now()
    cur_time = now.strftime("%H%M%S")
    cur_date = now.strftime("%d%m%Y")
    return cur_date, cur_time

# Let motion detectors know recording is in progress
is_recording = 0
def start_recording():
    global is_recording
    is_recording = 1
    logger.info("start recording has been called")
    result = do_publish(recording_feed, 1)
    if result:
        logger.info("start recording finished, calling next task")
        motion_detected()
    else:
        logger.info("start recording failed, not proceeding")

# When motion is detected, capture and image, base64 encode it, and send to MQTT
# Upon success, call capture_clip to grab a portion of the live feed and save it to a file
image = "image"
image_type = "jpg"
image_filename = f'{image}.{image_type}'
def motion_detected():
    logger.info("motion detected has been called")
    picam.capture_file(image_filename,  format='jpeg')
    with open(image_filename,  mode='rb') as file:
        base64_bytes = base64.b64encode(file.read())
        base64_message = base64_bytes.decode("utf-8")
    file.close()
    result = do_publish(camera_feed, base64_message)
    if result:
        logger.info("motion detected finished, calling next task")
        capture_clip()
    else:
        logger.info("motion detected failed, not proceeding")

# Capture a portion of the live feed to save to a file
# By default only send to local fileserver
# Use MQTT to publish whether that should be remote or both
# MQTT feed: monitoring.storage
capture_run_time = os.getenv("VIDEO_CAPTURE_TIME")
ffmpeg_filename = f"{filename}_encoded.{video_encoding}"
def capture_clip():
    global is_recording
    logger.info("capture clip has been called")
    record = True
    end_time = time.monotonic() + int(capture_run_time)
    output_capture.fileoutput = filename
    output_capture.start()
    while record:
        if time.monotonic() > end_time:
            output_capture.stop()
            record = False
    logger.info("capture clip finished, calling next task")
    if "local" in storage:
        copy_to_local_server()
    if "remote" in storage:
        copy_to_remote_server()
    if "both" in storage:
        copy_to_local_server()
        copy_to_remote_server()

# Just in case we get here without the current date and time being set
if current_date is None or current_time is None:
    current_date, current_time = get_date_time()

# Copy to local fileserver
video_storage_path = os.getenv("VIDEO_STORAGE_PATH")
local_file_storage_path = os.getenv("LOCAL_FILE_STORAGE_PATH")
local_video_file = local_file_storage_path + "/" + ffmpeg_filename
remote_video_file = video_storage_path + "/" + "video_capture_" + current_date + "-" + current_time + "." + video_encoding
local_image_file = local_file_storage_path + "/" + image_filename
remote_image_file = video_storage_path + "/" + "image_" + current_date + "-" + current_time + image_type
def copy_to_local_server():
    logger.info("copy video to local server has been called")
    try:
        ssh.connect(file_server_ip, username=ssh_username, password=ssh_password)
        scp = SCPClient(ssh.get_transport())
        scp.put(local_video_file, remote_video_file)
        scp.put(local_image_file, remote_image_file)
        logger.info("successfully copied video and still shot to local server!")
    except Exception as err:
        logger.error("failed to copy video to local server! %s", err)
    finally:
        ssh.close()

# Copy to Dropbox, the remote file service
proceed = False
access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
def copy_to_remote_server():
    global proceed
    logger.info("copy to remote server has been called")
    dbx = None
    # Try to connect with access and refresh tokens, report if failure but allow application to continue
    try:
        dbx = dropbox.Dropbox(access_token)
        dbx._oauth2_refresh_token = refresh_token
        proceed = True
    except AuthError as err:
        print("Error connecting to Dropbox with access token: {}".format(err))
        pass
    # If successfully connect, publish still and video to Dropbox
    if proceed:
        global remote_image_file, remote_video_file
        # Create valid image file for upload
        with open(local_image_file, 'rb') as still:
            image_upload_file = still.read()
        still.close()
        # Create valid video file for upload
        with open(local_video_file, 'rb') as video:
            video_upload_file = video.read()
        video.close()
        # Attempt to upload to Dropbox, report if failure but let application to continue
        try:
            dbx.files_upload(image_upload_file, f"/Driveway/image_capture_{current_date}-{current_time}.{image_type}")
            time.sleep(2)
            dbx.files_upload(video_upload_file, f"/Driveway/video_capture_{current_date}-{current_time}.{video_encoding}")
        except Exception as err:
            print("Error uploading still and video capture files: {}".format(err))
            pass
        finally:
            logger.info("uploaded still and video capture to remote server")
    # Let subscribers know recording is complete and any new motion can be detected
    result = do_publish(recording_feed, 0)
    if result:
        logger.info("All motion detected tasks complete")
    else:
        logger.info("All motion detected tasks did not complete")

# --- Prep for start of main --- #

# Connect to MQTT for publish and subscribe
logger.info("Connecting publish MQTT client")
pub_mqtt = connect_mqtt("pub")
logger.info("Connecting subscribe MQTT client")
sub_mqtt = connect_mqtt("sub")

# Start camera live feed
logger.info("Camera starting")
picam.start_encoder(encoder)
picam.start()
time.sleep(5)

try:
    while True:
        # Ensure the clients are active
        pub_mqtt.loop_start()
        sub_mqtt.loop_start()
        time.sleep(0.25)
except KeyboardInterrupt:
    # If receive keyboard interrupt, stop camera
    picam.stop()
    logger.info("Camera stopped")