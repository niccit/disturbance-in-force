# SPDX-License-Identifier: MIT
import os
import time
import requests
import uuid
import json
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pygments.lexers import q
import logging
from circuitpy_helpers.calendar_time_helpers import calendarHelper
from circuitpy_helpers.calendar_time_helpers import timeHelper
from circuitpy_helpers.network_helpers import wanChecker

# --- Logging Configuration --- #

# Allow logging level to be dictated by if in test mode or not
testing = False
if testing:
    LOG_LEVEL = logging.DEBUG
    weather_wait = 60
else:
    LOG_LEVEL = logging.INFO
    weather_wait = 600  # Weather doesn't change that fast, update once every 10 minutes (600)

# Set up the logger
logging.basicConfig(filename="home-hub.log", level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Configuration --- #
# load environment variables
load_dotenv()

# list of feeds to subscribe to
feeds_list = []

# --- MQTT Configuration --- #

mqtt_server = os.getenv('MQTT_SERVER')
mqtt_port = os.getenv('MQTT_PORT')
ca_cert_file = os.getenv('MQTT_CA_CERT')
client_pem = os.getenv('MQTT_CLIENT_PEM')
client_username = os.getenv('MQTT_USERNAME')
client_password = os.getenv('MQTT_PASSWORD')

# --- MQTT methods for handling traffic --- #
# Set up MQTT client and connect to broker
def connect_mqtt(cname):
    logger.info(f"Connecting to {cname} MQTT Broker!")
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
        client.connect_async(host=mqtt_server, port=int(mqtt_port), keepalive=60, clean_start=True)
    else:
        client.connect_async(mqtt_server, port=int(mqtt_port), keepalive=60)

    return client

# What to do when the client connects
def on_connect(client, userdata, flags, reason_code, properties):
    logger.debug(f"Connected to {client.client_id} MQTT Broker!")
    if "sub" in client.client_id:
        # Subscribe to any feeds
        if feeds_list:
            for feed in feeds_list:
                client.subscribe(feed)
                logger.info(f"subscribed sub_mqtt to {feed}")
        else:
            logger.info("there are no feeds in the list")

# Auto reconnect logic
FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60
def on_disconnect(client, userdata, rc):
    logger.error("Disconnected with result code: %s", rc)
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
    logger.debug("message payload is %s for topic %s", received_msg, msg.topic)

# MQTT feeds for date and time - pub
date_feed = os.getenv("DATE_FEED")
time_feed = os.getenv("TIME_FEED")
hour_feed = os.getenv("HOUR_FEED")

# Get date from system clock
# Store the date (1-31) and if the new query is different update the date to MQTT
stored_date = None
def get_date():
    global stored_date
    current_date, publish_date = calendarHelper.get_date_from_system()
    if stored_date is None or stored_date != current_date:
        logger.info(f"stored date is {stored_date}, current date is {current_date}")
        logger.debug("updating date on dashboard")
        logger.info(f"publishing to {date_feed} the date {publish_date}")
        do_publish(date_feed, publish_date, True)
        stored_date = current_date

# Get the time from system clock
# Update time to MQTT every minute
stored_time = None
stored_hour = None
def get_time():
    global stored_time, stored_hour
    now_min, now_hour, publish_time = timeHelper.get_current_time(get_hour=True)
    if stored_time is None or stored_time != now_min:
        logger.debug("updating time on dashboard")
        do_publish(time_feed, publish_time, True)
        stored_time = now_min

    if stored_hour is None or stored_hour != now_hour:
        do_publish(hour_feed, now_hour, True)
        stored_hour = now_hour

# --- Weather, Air Quality, so2 (vog indicator) --- #

# Per Openweathermap API query every 10 minutes for most accurate information
weather_report_wait = weather_wait

# URLs to Openweathermap API
weather_feed = f"https://api.openweathermap.org/data/2.5/weather?lat=" + os.getenv("LATITUDE") +  "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY") + "&units=metric"
air_quality_feed = f"https://api.openweathermap.org/data/2.5/air_pollution?lat=" + os.getenv("LATITUDE") + "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY")
# MQTT feeds for publishing data to dashboard - pub
pub_weather_feed = os.getenv("WEATHER_FEED")
sunset_feed = os.getenv("SUNSET_FEED")
sunrise_feed = os.getenv("SUNRISE_FEED")

# Gather all the weather and air quality data and format it into a report
last_report = None
info_spacer = '\u25AA'
def get_weather():
    global last_report
    degree_symbol = '\u00b0'
    if last_report is None or time.monotonic() > last_report + weather_report_wait:
        try:
            weather_request = requests.get(weather_feed)
            weather = weather_request.json()
            condition = (weather["weather"][0]["description"])
            high_temp = (weather["main"]["temp_max"])
            low_temp = (weather["main"]["temp_min"])
            temperature = (weather["main"]["temp"])
            feels_like = (weather["main"]["feels_like"])
            wind_speed = (weather["wind"]["speed"])
            wind_direction = (weather["wind"]["deg"])
            direction = get_wind_direction(wind_direction)
            humidity = (weather["main"]["humidity"])
            sunrise_unix = (weather["sys"]["sunrise"])
            sunset_unix = (weather["sys"]["sunset"])
            sunrise = timeHelper.format_time(sunrise_unix)
            sunset  = timeHelper.format_time(sunset_unix)
            air_quality, so2, so2_quality = get_air_quality()
            pressure = (weather["main"]["pressure"])
            pressure_indicator, publish_pressure, rain_indicator = get_pressure_info(pressure)
            try:
                wind_gust = (weather["wind"]["gust"])
                weather_for_dash = {"condition": f"{str(condition)}",
                        "high_low": f"{str(int(high_temp))}{degree_symbol}C / {str(int(low_temp))}{degree_symbol}C",
                        "temperature": f"{str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}",
                        "wind": f"{str(wind_speed)} m/sec {direction}",
                        "wind gust": f"{str(wind_gust)} m/sec",
                        "humidity": f"{str(int(humidity))}%",
                        "sunrise": f"{str(sunrise)}",
                        "sunset": f"{str(sunset)}",
                        "air quality": f"{str(air_quality)}",
                        "vog": f"{float(so2)} {str(so2_quality)}",
                        "pressure": f"{float(publish_pressure)} mmHg {pressure_indicator} {rain_indicator}",}
            except KeyError:
                weather_for_dash = {"condition": f"{str(condition)}",
                        "high_low": f"{str(int(high_temp))}{degree_symbol}C / {str(int(low_temp))}{degree_symbol}C",
                        "temperature": f"{str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}",
                        "wind": f"{str(wind_speed)} m/sec {direction}",
                        "humidity": f"{str(int(humidity))}%",
                        "sunrise": f"{str(sunrise)}",
                        "sunset": f"{str(sunset)}",
                        "air quality": f"{str(air_quality)}",
                        "vog": f"{float(so2)} {str(so2_quality)}",
                        "pressure": f"{float(publish_pressure)} mmHg {pressure_indicator} {rain_indicator}",}
                pass

            sunset_hr, sunset_minute, sunset_second = sunset.split(":")
            sunset_info = f"{sunset_hr}:{sunset_minute}"
            sunrise_hr, sunrise_minute, sunrise_second = sunrise.split(":")
            sunrise_info = f"{sunrise_hr}:{sunrise_minute}"

            logger.debug("updating weather report on dashboard")
            do_publish(pub_weather_feed, json.dumps(weather_for_dash), True)
            do_publish(sunset_feed, sunset_info, True)
            do_publish(sunrise_feed, sunrise_info, True)
        except ConnectionError:
            logger.error("Connection error trying to get the weather")
            pass

        last_report = time.monotonic()


# --- Calendar Events --- #

# MQTT feed for calendar - pub
calendar_feed = os.getenv("CALENDAR_FEED")
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
calendar_report_wait = 7200 # Calendar shouldn't change that much, so only check every two hours

# Query a shared Google calendar
# Grab the next two events to publish
# Note: if you change the number of events to grab, update the for loop that builds the publish string (until I figure out how to not need to do  this)
last_calendar_check = None
events_to_publish = None
def get_shared_calendar_events():
    global last_calendar_check, events_to_publish
    events = []
    if last_calendar_check is None or time.monotonic() > last_calendar_check + calendar_report_wait:
        logger.debug("It's time to check the calendar")
        creds = None
        wait_time = 120
        wait_multiplier = 1.2
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        for attempt in range(5):
            try:
                service = build("calendar", "v3", credentials=creds)
                now = timeHelper.get_unix_time()
                events_result = (
                    service.events().list(
                        calendarId="snipcrthka3m1mbm501fa486l4@group.calendar.google.com",
                        timeMin=now,
                        maxResults=2,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
                events = events_result.get("items", [])
                break
            except HttpError as error:
                logger.error(f"An error occurred: {error}, retrying")
                if attempt == 0:
                    time.sleep(wait_time)
                elif attempt <= 4:
                    time.sleep(wait_time*wait_multiplier)
                    wait_time = wait_time*wait_multiplier
                else:
                    logger.error("unable to retrieve events, abandoning")
            attempt += 1

        pub_array = []
        if not events:
            pub_events = "No upcoming events found."
            pub_array.append({"timestamp": "", "event": pub_events})
        else:
            for event in events:
                publish_event = event["summary"]
                event_datetime = event["start"].get("dateTime")
                if event_datetime is not None:
                    event_date, event_time = event_datetime.split("T")
                    event_year, event_month, event_day = event_date.split("-")
                    full_month = calendarHelper.get_month_name(event_month)
                    event_start_time, event_end_time = event_time.split("-")
                    event_time_hr, event_time_min, event_time_sec = event_start_time.split(":")
                    publish_datetime = f"{event_day} {full_month} {event_year} at {event_time_hr}:{event_time_min}"
                    pub_array.append({"timestamp": publish_datetime, "event": publish_event})
                else:
                    event_date = event["start"].get("date")
                    event_year, event_month, event_day = event_date.split("-")
                    full_month = calendarHelper.get_month_name(event_month)
                    publish_date = f"{event_day} {full_month} {event_year}"
                    pub_array.append({"timestamp": publish_date, "event": + publish_event})

        if len(pub_array) == 1:
            pub_array.append({"timestamp": "", "event": ""})

        message = json.dumps(pub_array)

        logger.debug("Publishing calendar events")
        do_publish(calendar_feed, message, True)

        last_calendar_check = time.monotonic()

# --- Supporting task handling methods --- #

# Publish to MQTT
def do_publish(feed, data, retain=False):
    if not testing:
        pub_mqtt_client.loop_start()
        logger.info("I am publishing %s to %s", data, feed)
        pub_mqtt_client.publish(feed, data, retain=retain)
        pub_mqtt_client.loop_stop()
    else:
        logger.debug("TESTING:")
        if "sunset" in feed or "time" in feed:
            logger.debug("Would publish: Topic: %s. Payload: %s. Retain: %s", str(feed), str(data), "true")
        else:
            logger.debug("Would publish: Topic: %s. Payload: %s. Retain: %s", str(feed), str(data), "false")

# Get the air quality and so2 levels
def get_air_quality():
    response = requests.get(air_quality_feed)
    air_quality =  response.json()
    aq = (air_quality["list"][0]["main"]["aqi"])
    so2 = (air_quality["list"][0]["components"]["so2"])

    # Using the basic 1-5 scale documented on Openweathermap API
    if aq == 1:
        air_quality = "good"
    elif aq == 2:
        air_quality = "fair"
    elif aq == 3:
        air_quality = "moderate"
    elif aq == 4:
        air_quality = "poor"
    elif aq == 5:
        air_quality = "very poor"
    else:
        air_quality = "unable to retrieve air quality"

    # Using table provided on Openweathermap API
    if 0 <= so2 < 20:
        so2_quality = "good"
    elif 20 <= so2 < 80:
        so2_quality = "fair"
    elif 80 <= so2 < 250:
        so2_quality = "moderate"
    elif 250 <= so2 < 350:
        so2_quality = "poor"
    elif so2 >= 350:
        so2_quality = "very poor"
    else:
        so2_quality = "unable to retrieve so2 quality"

    return air_quality, so2, so2_quality

# Return UNICODE character for direction based on degrees
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

# Get barometric pressure information for weather block
# If pressure drops below average pressure, indicate it might rain
indicator, stored_pressure_indicator, stored_pressure, rain = None, None, None, None
def get_pressure_info(pressure):
    global stored_pressure, stored_pressure_indicator, indicator, rain
    publish_pressure = round((pressure * 0.750061683), 2)

    if stored_pressure is None:
        indicator = '\u00A0'

    if stored_pressure is not None:
        if publish_pressure > stored_pressure:
            indicator = '\u2BAD'
        elif publish_pressure < stored_pressure:
            indicator = '\u2BAF'
        else:
            indicator = stored_pressure_indicator

    average_pressure = os.getenv("AVERAGE_PRESSURE")
    if publish_pressure < int(average_pressure):
        rain = '\u2602'
    else:
        rain = '\u00A0'

    stored_pressure = publish_pressure
    stored_pressure_indicator = indicator
    return indicator, publish_pressure, rain

# --- The magic begins here --- #

# Log a message indicating if we're in test mode
if testing:
    logger.debug("We are TESTING")
else:
    logger.info("We are LIVE")

# Connect to MQTT for publish and subscribe
logger.info("Connecting publish MQTT client")
pub_mqtt_client = connect_mqtt("pub")
logger.info("Connecting subscribe MQTT client")
sub_mqtt_client = connect_mqtt("sub")

# Subscribe to any feeds
if feeds_list:
    logger.debug("I have feeds to subscribe to")

# sub_mqtt_client.loop_start()

logger.info("hello world, home hub is starting up!")
wanCheck_counter = 0
wan_state = True
while True:

    if wanCheck_counter % 100 == 0:
        wan_state = wanChecker.py_wan_active()
        wanCheck_counter = 0
        logger.info(f"wan state is {wan_state}")

    mqtt_connected = pub_mqtt_client.is_connected()

    if wan_state:
        if not mqtt_connected:
            pub_mqtt_client.reconnect()
            sub_mqtt_client.reconnect()

        get_time()
        get_date()
        get_weather()
        get_shared_calendar_events()
        #    monitor_garage_notification()

    wanCheck_counter += 1
    time.sleep(0.5)

