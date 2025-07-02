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
old_weather_feed = mqtt_remote_username + "/integration/weather/2796/current"
weather_exclude_list="minutely,hourly,daily,alerts"
latitude=os.getenv("latitude")
longitude=os.getenv("longitude")
weather_feed = f"https://api.openweathermap.org/data/2.5/weather?lat=" + latitude +  "&lon=" + longitude + "&appid=" + os.getenv("openweather_api_key") + "&units=metric"
weather_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("weather_icon_remote_feed")
pub_weather_feed = mqtt_remote_username + "/feeds/" + os.getenv("weather_remote_feed")
air_quality_feed = f"http://api.openweathermap.org/data/2.5/air_pollution?lat=" + latitude + "&lon=" + longitude + "&appid=" + os.getenv("openweather_api_key")
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
# weather_report = weather_integration.receive_weather(2796)

# Wait times for different events
door_check_wait = 5         # We only send an event when things change, and we want to know when things change quickly
weather_report_wait = 600  # Weather doesn't change that fast, update once an hour, default 3600


# Query the Adafruit integration to get current date, update the calendar date on the dashboard once per day
stored_date = None
def get_date():
    global stored_date
    current_date = requests.get(date_url)
    if stored_date is None or stored_date != current_date.text:
        print("updating calendar date on dashboard")
        remote_mqtt.publish(date_feed, current_date.text)
        stored_date = current_date.text
        current_date.close()

# Query Adafruit integration to get current time, update clock on dashboard every minute
stored_time = None
def get_time():
    global stored_time
    current_time = requests.get(time_url)
    if stored_time is None or stored_time != current_time.text:
        print("updating time on dashboard")
        remote_mqtt.publish(time_feed, current_time.text)
        stored_time = current_time.text
        current_time.close()

# Given a Unix timestamp, convert that to local time
# Used for sunrise/sunset
def format_time(timestamp, tz_offset):
    time_to_convert = timestamp + tz_offset
    local_time = time.localtime(time_to_convert)
    return "{:02d}:{:02d}:{:02d}".format(local_time.tm_hour, local_time.tm_min, local_time.tm_sec)


# Gather all the weather and air quality data and format it into a report
# Using Openweathermap.org
last_report = None
def get_weather():
    global last_report
    degree_symbol = '\u00b0'
    daylight = False

    if last_report is None or time.monotonic() > last_report + weather_report_wait:
        weather_request = requests.get(weather_feed)
        weather = weather_request.json()
        condition = (weather["weather"][0]["description"])
        temperature = (weather["main"]["temp"])
        feels_like = (weather["main"]["feels_like"])
        wind_speed = (weather["wind"]["speed"])
        wind_direction = (weather["wind"]["deg"])
        direction = get_wind_direction(wind_direction)
        humidity = (weather["main"]["humidity"])
        query_time = (weather["dt"])
        tz_offset = (weather["timezone"])
        sunrise_unix = (weather["sys"]["sunrise"])
        sunset_unix = (weather["sys"]["sunset"])
        sunrise = format_time(sunrise_unix, tz_offset)
        sunset  = format_time(sunset_unix, tz_offset)
        air_quality, so2, so2_indicator = get_air_quality()
        if query_time < sunset_unix:
            daylight = True
        w_icon = get_weather_icon(condition,daylight)
        print("Publishing weather report")
        try:
            wind_gust = (weather["wind"]["gust"])
            weather_for_dash = f"""\
                {condition}
                {str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}C
                wind speed {str(wind_speed)} m/sec {direction}
                wind gust {str(wind_gust)} m/sec
                humidity {str(int(humidity))}%
                sunrise {sunrise} / sunset { sunset}
                air quality {air_quality}
                vog (so2) {so2} change {so2_indicator}
                """
        except KeyError:
            weather_for_dash = f"""\
            {condition}
            {str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}C
            wind speed {str(wind_speed)} m/sec {direction}
            humidity {str(int(humidity))}%
            sunrise {sunrise} / sunset {sunset}
            air quality {air_quality}
            vog (so2) {so2} change {so2_indicator}
            """
            pass

        print("updating weather report on dashboard")
        remote_mqtt.publish(weather_icon_feed, w_icon)
        remote_mqtt.publish(pub_weather_feed, weather_for_dash)
        last_report = time.monotonic()

# Get appropriate icon to display for weather. Using Adafruit IO icons from FontAwesome and Weather Icons Project
def get_weather_icon(condition, daylight):
    if daylight:
        if "cloud" in condition.lower():
            icon = "w:day-cloudy"
        elif "rain" in condition.lower():
            icon = "w:day-rain"
        elif "sun" in condition.lower():
            icon = "w:day-sunny"
        else:
            icon = "sun-o"
    else:
        if "cloud" in condition.lower():
            icon = "w:night-cloudy"
        elif "rain" in condition.lower():
            icon = "w:night-rain"
        else:
            icon = "moon-o"

    return icon

# Get the air quality and so2 levels
# Using Openweathermap.org
so2_level = None
def get_air_quality():
    global so2_level
    response = requests.get(air_quality_feed)
    air_quality =  response.json()
    aq = (air_quality["list"][0]["main"]["aqi"])
    so2 = (air_quality["list"][0]["components"]["so2"])
    if aq is 1:
        air_quality = "good"
    elif aq is 2:
        air_quality = "fair"
    elif aq is 3:
        air_quality = "moderate"
    elif aq is 4:
        air_quality = "poor"
    elif aq is 5:
        air_quality = "very poor"
    else:
        air_quality = "unable to retrieve air quality"

    if so2_level is None:
        so2_level = so2
        so2_indicator = "unknown"
    elif so2_level > so2:
        so2_level = so2
        so2_indicator = '\u2191'
    elif so2_level < so2:
        so2_level = so2
        so2_indicator = '\u2193'
    else:
        so2_indicator = '\u002d'

    return air_quality, so2, so2_indicator

# Return unicode character for direction based on degrees
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

# Garage door sensor
last_garage_door_check = None
def check_garage_door():
    global garage_door_state, last_garage_door_check
    status = garage_door_sensor.value
    # Publish message when state changes from open to closed and vice versa
    if last_garage_door_check is None or time.monotonic() > last_garage_door_check + door_check_wait:
        if garage_door_sensor.value:
            if garage_door_state is not status:
                print("Publishing garage door state change, now", garage_door_state)
                remote_mqtt.publish(garage_door_feed, "Garage Door is Open")
                remote_mqtt.publish(garage_door_icon_feed, "frown-o")
                garage_door_state = status
        elif not garage_door_sensor.value:
            if garage_door_state is not status:
                print("Publishing garage door state change, now", garage_door_state)
                remote_mqtt.publish(garage_door_feed, "Garage Door is Closed")
                remote_mqtt.publish(garage_door_icon_feed, "smile-o")
                garage_door_state = status

        last_garage_door_check = time.monotonic()


while True:

    get_date()
    get_time()
    get_weather()
    check_garage_door()

    # use door_check_wait since that is the shortest interval
    time.sleep(door_check_wait)