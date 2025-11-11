# SPDX-License-Identifier: MIT
import os
import time
import requests
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pygments.lexers import q
import logging
from circuitpy_helpers.calendar_time_helpers import calendar_helper
from circuitpy_helpers.calendar_time_helpers import time_helper

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
logging.basicConfig(filename="hub.log", level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Configuration --- #
# load environment variables
load_dotenv()

# list of feeds to subscribe to
feeds_list = []

# --- MQTT Methods --- #

# What to do when the client connects
def on_connect(client, userdata, flags, reason_code, properties):
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

# Subscribe logic when subscribing to an MQTT feed
garage_door_state = 0
def subscribe(client, topic):
    def on_message(client, userdata, msg):
        global garage_door_state
        received_msg = msg.payload.decode("utf-8")
        logger.debug("message payload is %s for topic %s", received_msg, msg.topic)
        if "garage" in received_msg.lower():
            garage_door_state = received_msg
            logger.debug("garage door state is %s", garage_door_state)

    client.subscribe(topic)
    client.on_message = on_message

# --- MQTT Configuration --- #

mqtt_server = os.getenv("MQTT_SERVER")
mqtt_port = os.getenv("MQTT_PORT")
mqtt_username = os.getenv("MQTT_USERNAME")
mqtt_key = os.getenv("MQTT_PASSWORD")
mqtt_ca_cert = os.getenv("MQTT_CA_CERT")
mqtt_client_cert = os.getenv("MQTT_CLIENT_PEM")

# Connect to the specified MQTT server
def connect_mqtt():
    # Set Connecting Client ID
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set()
    client.username_pw_set(username=mqtt_username, password=mqtt_key)

    client.on_connect = on_connect
    client.disconnect = on_disconnect
    client.connect(mqtt_server, int(mqtt_port), 60)
    return client

# MQTT feeds - subs
garage_notice = os.getenv("GARAGE_ALERT")
garage_data_source = os.getenv("GARAGE_FEED")
feeds_list.append(garage_data_source)

# Connect to MQTT
pub_mqtt_client = connect_mqtt()
pub_mqtt_client.loop_start()
sub_mqtt_client = connect_mqtt()

# Subscribe to the feeds we need to take action
def sub_feeds():
    for feed in feeds_list:
        subscribe(sub_mqtt_client, feed)
        logger.info("subscribed to %s" % feed)

    sub_mqtt_client.loop_start()

# --- Date & Time for the dashboard clock --- #

# MQTT feeds for date and time - pub
date_feed = os.getenv("DATE_FEED")
time_feed = os.getenv("TIME_FEED")

# Get date from system clock
# Store the date (1-31) and if the new query is different update the date to MQTT
stored_date = None
def get_date():
    global stored_date
    current_date, publish_date = calendar_helper.get_date_from_system()
    if stored_date is None or stored_date != current_date:
        logger.debug("updating calendar date on dashboard")
        do_publish(date_feed, publish_date)
        stored_date = current_date

# Get the time from system clock
# Update time to MQTT every minute
stored_time = None
def get_time():
    global stored_time
    now_min, publish_time = time_helper.get_current_time()
    if stored_time is None or stored_time != now_min:
        logger.debug("updating time on dashboard")
        do_publish(time_feed, publish_time)
        stored_time = now_min

# --- Weather, Air Quality, so2 (vog indicator) --- #

# Per Openweathermap API query every 10 minutes for most accurate information
weather_report_wait = weather_wait

# URLs to Openweathermap API
weather_feed = f"https://api.openweathermap.org/data/2.5/weather?lat=" + os.getenv("LATITUDE") +  "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY") + "&units=metric"
air_quality_feed = f"https://api.openweathermap.org/data/2.5/air_pollution?lat=" + os.getenv("LATITUDE") + "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY")
# MQTT feeds for publishing data to dashboard - pub
pub_weather_feed = os.getenv("WEATHER_FEED")

# Gather all the weather and air quality data and format it into a report
last_report = None
info_spacer = '\u25AA'
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
        sunrise_unix = (weather["sys"]["sunrise"])
        sunset_unix = (weather["sys"]["sunset"])
        sunrise = time_helper.format_time(sunrise_unix)
        sunset  = time_helper.format_time(sunset_unix)
        air_quality, so2, so2_quality = get_air_quality()
        pressure = (weather["main"]["pressure"])
        pressure_indicator, publish_pressure, rain_indicator = get_pressure_info(pressure)
        try:
            wind_gust = (weather["wind"]["gust"])
            weather_for_dash = f"""\
                {condition}
                {str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}C
                wind speed {str(wind_speed)} m/sec {direction}
                wind gust {str(wind_gust)} m/sec
                humidity {str(int(humidity))}%
                sunrise {sunrise}
                sunset { sunset}
                air quality {air_quality}
                vog (so2) {so2} {info_spacer} {so2_quality}
                pressure {publish_pressure} mmHg {pressure_indicator} {rain_indicator}
                """
        except KeyError:
            weather_for_dash = f"""\
                {condition}
                {str(int(temperature))}{degree_symbol}C feels like {int(feels_like)}{degree_symbol}C
                wind speed {str(wind_speed)} m/sec {direction}
                humidity {str(int(humidity))}%
                sunrise {sunrise}
                sunset {sunset}
                air quality {air_quality}
                vog (so2) {so2} {info_spacer} {so2_quality}
                pressure {publish_pressure} mmHg {pressure_indicator} {rain_indicator}
                """
            pass

        logger.debug("updating weather report on dashboard")
        do_publish(pub_weather_feed, weather_for_dash)
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
def get_shared_calendar_events():
    global last_calendar_check
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
                now = time_helper.get_unix_time()
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

        if not events:
            pub_events = "No upcoming events found."
            do_publish(calendar_feed, pub_events)
        else:
            pub_array = []
            for event in events:
                publish_event = event["summary"]
                event_datetime = event["start"].get("dateTime")
                if event_datetime is not None:
                    event_date, event_time = event_datetime.split("T")
                    event_year, event_month, event_day = event_date.split("-")
                    full_month = calendar_helper.get_month_name(event_month)
                    event_start_time, event_end_time = event_time.split("-")
                    event_time_hr, event_time_min, event_time_sec = event_start_time.split(":")
                    publish_datetime = f"{event_day} {full_month} {event_year} at {event_time_hr}:{event_time_min}"
                    pub_array.append(publish_datetime + " " + info_spacer + " " + publish_event)
                else:
                    event_date = event["start"].get("date")
                    event_year, event_month, event_day = event_date.split("-")
                    full_month = calendar_helper.get_month_name(event_month)
                    publish_date = f"{event_day} {full_month} {event_year}"
                    pub_array.append(publish_date + " " + info_spacer + " " + publish_event)

            if len(pub_array) == 1:
                message = f"{pub_array[0]}"
            else:
                message = f"""\
                    {pub_array[0]}
                    {pub_array[1]}"""

            logger.debug("Publishing calendar events")
            do_publish(calendar_feed, message)

        last_calendar_check = time.monotonic()

# --- Supporting task handling methods --- #

# Publish to MQTT
def do_publish(feed, data):
    if not testing:
        logger.debug("I am publishing %s to %s", data, feed)
        pub_mqtt_client.publish(feed, data)
    else:
        logger.debug("TESTING:")
        logger.debug("Would publish: Topic: %s. Payload: %s", str(feed), str(data))

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


# If the time is after 8PM and the garage door is still in an open state
# Email me so that I know to close it, just in case I don't look at the home hub
notified = False
close_time = os.getenv("GARAGE_ALERT_TIME")
def monitor_garage_notification():
    global notified, close_time
    cur_min, now = time_helper.get_current_time()

    # Publish that the garage door is open after 20:00
    # This will send an email alerting the need to close the door
    if "open" in garage_door_state:
        if now > close_time and not notified:
            do_publish(garage_notice, 1)
            notified = True

    # If time is not within the hours door should be closed
    # Reset to notified to False
    if now < close_time and notified:
        logger.info("resetting close garage notification status")
        notified = False

# --- The magic begins here --- #

# Log a message indicating if we're in test mode
if testing:
    logger.debug("TESTING")
else:
    logger.info("LIVE")

# Subscribe to any feeds
if feeds_list:
    logger.info("I have feeds to subscribe to")
    sub_feeds()

logger.info("hello world, home hub is starting up!")
while True:
    get_date()
    get_time()
    get_weather()
    get_shared_calendar_events()
    monitor_garage_notification()

    time.sleep(0.5)
