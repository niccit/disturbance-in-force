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

remote_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_remote_feed")

# (Future) Local

# MQTT Callback methods
def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print("Connected to mqtt broker {0}".format(client))

def disconnected(client, userdata, rc):
    # This method is called when the client is disconnected
    print("Disconnected from mqtt broker!")

def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new feed.
    print("Subscribed to {0}".format(topic))

def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a feed.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))

def on_message(client, topic, message):
    # Method called when a client's subscribed feed has a new value.
    print("New message on topic {0}: {1}".format(topic, message))

# All MQTT callback directives
remote_mqtt.on_connect = connected
remote_mqtt.on_disconnect = disconnected
remote_mqtt.on_subscribe = subscribe
remote_mqtt.on_unsubscribe = unsubscribe
remote_mqtt.on_message = on_message

try:
    print("trying to connect to remote MQTT broker")
    remote_mqtt.connect()
except MMQTTException:
    print("unable to connect to remote MQTT broker")
    raise

# Garage Door Sensor
garage_door_sensor=digitalio.DigitalInOut(board.A3)
garage_door_sensor.direction = digitalio.Direction.INPUT
garage_door_sensor.pull = digitalio.Pull.UP
garage_door_switch = Debouncer(garage_door_sensor)
garage_door_state = False
garage_door_check_wait = 10   # 3600 for normal operation, lower for testng



while True:

    # Publish message when state changes from open to closed and vice versa
    if garage_door_sensor.value:
        if garage_door_state is not garage_door_sensor.value:
            print("garage door open", garage_door_sensor.value)
            remote_mqtt.publish(remote_feed, 0)
            garage_door_state = garage_door_sensor.value
    elif not garage_door_sensor.value:
        if garage_door_state is not garage_door_sensor.value:
            print("garage door closed", str(garage_door_sensor.value))
            remote_mqtt.publish(remote_feed, 1)
            garage_door_state = garage_door_sensor.value

    time.sleep(garage_door_check_wait)

