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
import adafruit_requests
from adafruit_io.adafruit_io import IO_HTTP


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
weather_feed = mqtt_remote_username + "/integration/weather/2796/current"
time_feed = mqtt_remote_username + "/feeds/" + os.getenv("date_time_remote_feed")
tz = os.getenv("TIMEZONE")
datetime_url = f"https://io.adafruit.com/api/v2/" + mqtt_remote_username + "/integrations/time/strftime?x-aio-key=" + mqtt_remote_key + "&tz=" + tz
time_url = datetime_url + "&fmt=%25H%3A%25M"
date_url = datetime_url + "&fmt=%25d%20%25B%20%25Y"

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
    remote_mqtt.publish(remote_feed, "{0}".format(message))

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

# Get the weather for our dashboard
requests = adafruit_requests.Session(pool, ssl_context)
weather_integration = IO_HTTP(mqtt_remote_username, mqtt_remote_key, requests)
weather_report = weather_integration.receive_weather(2796)

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

    current_conditions = weather_report["current"]
    today_forecast=weather_report["forecast_minutes_5"]
    current_date = requests.get(date_url)
    print(current_date.text)
    current_date.close()
    current_time = requests.get(time_url)
    print(current_time.text)
    current_time.close()
    print("It is {1} and the current temperature is {2} C.".format(current_conditions["asOf"], current_conditions["conditionCode"], current_conditions["temperature"]))
    print("Humidity is {0}%".format(current_conditions["humidity"] * 100))
    precipitationChance=today_forecast["precipitationChance"]
    precipitationIntensity=today_forecast["precipitationIntensity"]
    print("Currently, the chance of rain is {0}%".format(precipitationChance))

    time.sleep(garage_door_check_wait)

