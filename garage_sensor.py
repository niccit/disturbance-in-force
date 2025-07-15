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

# WiFi
connected = False
while not connected:
    try:
        wifi.radio.connect(os.getenv("CIRCUITPYTHON_WIFI_SSID"), os.getenv("CIRCUITPYTHON_WIFI_PASSWORD"))
        print("Connected to WiFi", str(wifi.radio.ap_info.ssid) + "!")
        connected = True
    except ConnectionError:
        print("Failed to connect to WiFi")

# MQTT
radio = wifi.radio
pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)

# Remote
mqtt_remote_server = os.getenv("mqtt_remote_server")
mqtt_remote_username = os.getenv("mqtt_remote_username")
mqtt_remote_key = os.getenv("mqtt_remote_key")

remote_mqtt = adafruit_minimqtt.adafruit_minimqtt.MQTT(
    broker=mqtt_remote_server
    , username=mqtt_remote_username
    , password=mqtt_remote_key
    , socket_pool=pool
    , ssl_context=ssl_context
)

# Feed for garage door sensor
garage_door_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_remote_feed")
garage_door_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_icon_remote_feed")


# Garage Door Sensor
garage_door_sensor=digitalio.DigitalInOut(board.A3)
garage_door_sensor.direction = digitalio.Direction.INPUT
garage_door_sensor.pull = digitalio.Pull.UP
garage_door_switch = Debouncer(garage_door_sensor)
door_check_wait = 20 # 1800


def get_publish_message(garage_status):
    if garage_status:
        msg = "Garage door is open"
        msg_icon = "frown-o"
    else:
        msg = "Garage door is closed"
        msg_icon = "smile-o"

    return msg, msg_icon

def do_publish(feed, msg):
    try:
        print("trying to connect to remote MQTT broker")
        remote_mqtt.connect()
        print("connected to remote MQTT broker")
    except MMQTTException:
        print("unable to connect to remote MQTT broker")
        raise

    remote_mqtt.publish(feed, msg)
    remote_mqtt.disconnect()


last_known_state = False
startup = True
print("hello world, garage door sensor coming online")
while True:
    status = garage_door_sensor.value

    if startup:
        print("System has started, publishing to MQTT")
        message, icon = get_publish_message(status)
        do_publish(garage_door_icon_feed, icon)
        do_publish(garage_door_feed, message)
        startup = False
        last_known_state = status
    elif last_known_state is not status and startup is False:
        print("Garage door state has changed, publishing to MQTT")
        message, icon = get_publish_message(status)
        do_publish(garage_door_icon_feed, icon)
        do_publish(garage_door_feed, message)
        last_known_state = status
    else:
        print("Nothing has changed, not publishing to MQTT")

    time.sleep(door_check_wait)


