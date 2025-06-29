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

# MQTT Feeds
garage_door_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_remote_feed")
garage_door_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("garage_door_icon_remote_feed")
weather_feed = mqtt_remote_username + "/integration/weather/2796/current"
weather_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("weather_icon_remote_feed")
pub_weather_feed = mqtt_remote_username + "/feeds/" + os.getenv("weather_remote_feed")
date_feed = mqtt_remote_username + "/feeds/" + os.getenv("date_remote_feed")
time_feed = mqtt_remote_username + "/feeds/" + os.getenv("time_remote_feed")

# Date Time IO integration
tz = os.getenv("TIMEZONE")
datetime_url = f"https://io.adafruit.com/api/v2/" + mqtt_remote_username + "/integrations/time/strftime?x-aio-key=" + mqtt_remote_key + "&tz=" + tz
time_url = datetime_url + "&fmt=%25H%3A%25M"
date_url = datetime_url + "&fmt=%25d%20%25B%20%25Y"

# (Future) Local

# MQTT Callback methods
def connected(client, userdata, flags, rc):
    # This function will be called when the client is connected
    # successfully to the broker.
    print("Connected to mqtt broker!")

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

# Get the weather for our dashboard
requests = adafruit_requests.Session(pool, ssl_context)
weather_integration = IO_HTTP(mqtt_remote_username, mqtt_remote_key, requests)
weather_report = weather_integration.receive_weather(2796)

# Wait times for different events
door_check_wait = 5         # We only send an event when things change, and we want to know when things change quickly
weather_report_wait = 3600  # Weather doesn't change that fast, update once an hour, default 3600


stored_date = None
def get_date():
    global stored_date
    current_date = requests.get(date_url)
    # We only want to publish the date once per day
    if stored_date is None or stored_date != current_date.text:
        print("the date has changed or we just started, publishing date")
        remote_mqtt.publish(date_feed, current_date.text)
        stored_date = current_date.text
        current_date.close()

stored_time = None
def get_time():
    global stored_time
    current_time = requests.get(time_url)
    if stored_time is None or stored_time != current_time.text:
        print("the time has changed or we just started, publishing time")
        remote_mqtt.publish(time_feed, current_time.text)
        stored_time = current_time.text
        current_time.close()



last_report = None
def get_weather():
    global last_report
    current_conditions = weather_report["current"]
    condition = current_conditions["conditionCode"]
    pub_condition = get_formatted_condition(condition)
    temperature = current_conditions["temperature"]
    wind_speed = current_conditions["windSpeed"]            # km/hr
    wind_direction = current_conditions["windDirection"]
    direction = get_wind_direction(wind_direction)
    humidity = (current_conditions["humidity"] * 100)
    daylight = current_conditions["daylight"]
    degree_symbol = '\u00b0'
    if last_report is None or time.monotonic() > last_report + weather_report_wait:
        print("Publishing weather report")
        weather_for_dash = f"""{pub_condition}
           {str(int(temperature))}{degree_symbol}C
           {str(wind_speed)} km/hr {direction}
           {str(int(humidity))}%
        """
        icon = get_weather_icon(condition,daylight)
        remote_mqtt.publish(weather_icon_feed, icon)
        remote_mqtt.publish(pub_weather_feed, weather_for_dash)
        last_report = time.monotonic()

def get_weather_icon(condition, daylight):
    icon = None
    if daylight:
        if "cloud" in condition.lower():
            icon = "w:day-cloudy"
        elif "rain" in condition.lower():
            icon = "w:day-rain"
        elif "sun" in condition.lower():
            icon = "w:day-sunny"
    else:
        if "cloud" in condition.lower():
            icon = "w:night-cloudy"
        elif "rain" in condition.lower():
            icon = "w:night-rain"

    return icon

def get_formatted_condition(condition):
    pub_condition = None
    if "mostly" in condition.lower():
        if "cloud" in condition.lower():
            pub_condition = "Mostly Cloudy"
        elif "sun" in condition.lower():
            pub_condition = "Mostly Sunny"
    else:
        pub_condition = condition

    return pub_condition

def get_wind_direction(wind_direction):
    if 0 <= wind_direction <= 44:
        direction = '\u2191'
    elif 45 <= wind_direction <= 89:
        direction = '\u2197'
    elif 90 <= wind_direction <= 134:
        direction = '\u2192'
    elif 135 <= wind_direction <= 179:
        direction = '\u2198'
    elif 180 <= wind_direction <= 224:
        direction = '\u2193'
    elif 225 <= wind_direction <= 269:
        direction = '\u2199'
    elif 270 <= wind_direction <= 314:
        direction = '\u2190'
    else:
        direction = '\u2196'

    return direction




while True:

    # Publish message when state changes from open to closed and vice versa
    if garage_door_sensor.value:
        if garage_door_state is not garage_door_sensor.value:
            print("Publishing garage door state change, now", garage_door_state)
            remote_mqtt.publish(garage_door_feed, "Garage Door is Open")
            remote_mqtt.publish(garage_door_icon_feed, "frown-o")
            garage_door_state = garage_door_sensor.value
    elif not garage_door_sensor.value:
        if garage_door_state is not garage_door_sensor.value:
            print("Publishing garage door state change, now", garage_door_state)
            remote_mqtt.publish(garage_door_feed, "Garage Door is Closed")
            remote_mqtt.publish(garage_door_icon_feed, "smile-o")
            garage_door_state = garage_door_sensor.value

    get_date()
    get_time()
    get_weather()

    time.sleep(door_check_wait)

