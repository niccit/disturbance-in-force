# SPDX-License-Identifier: MIT
import os
from dotenv import load_dotenv
import time
from datetime import datetime
from datetime import timezone
import paho.mqtt.client as mqtt
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pygments.lexers import q

# Set testing to True to turn off publish to MQTT
# Good for active development while code is running on a different client
testing = False

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# load environment variables
load_dotenv()

# Remote MQTT connection data
mqtt_remote_server = os.getenv("MQTT_REMOTE_SERVER")
mqtt_remote_username = os.getenv("MQTT_REMOTE_USERNAME")
mqtt_remote_key = os.getenv("MQTT_REMOTE_KEY")

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.tls_set()
mqtt_client.username_pw_set(username=mqtt_remote_username, password=mqtt_remote_key)

print("Connecting to MQTT broker...")
mqtt_client.connect(mqtt_remote_server, 8883, 60)


# --- Date & Time for the dashboard clock --- #

# MQTT feeds for date and time
date_feed = mqtt_remote_username + "/feeds/" + os.getenv("DATE_REMOTE_FEED")
time_feed = mqtt_remote_username + "/feeds/" + os.getenv("TIME_REMOTE_FEED")

def do_publish(feed, data):
    if not testing:
        mqtt_client.publish(feed, data)
    else:
        print("TESTING:", data)


# Get date from system clock
# Store the date (1-31) and if the new query is different update the date to MQTT
stored_date = None
def get_date():
    global stored_date
    now = datetime.now()
    current_date = now.strftime("%d")
    publish_date = now.strftime("%A %d %B %Y")
    if stored_date is None or stored_date != current_date:
        print("updating calendar date on dashboard")
        do_publish(date_feed, publish_date)
        stored_date = current_date

# Get the time from system clock
# Update time to MQTT every minute
stored_time = None
def get_time():
    global stored_time
    now = datetime.now()
    current_min = now.minute
    publish_time = now.strftime("%H:%M")
    if stored_time is None or stored_time != current_min:
        print("updating time on dashboard")
        do_publish(time_feed, publish_time)
        stored_time = current_min

# --- Weather, Air Quality, so2 (vog indicator) --- #

# Per Openweathermap API query every 10 minutes for most accurate information
weather_report_wait = 600  # Weather doesn't change that fast, update once every 10 minutes (600)
calendar_report_wait = 21600 # Calendar shouldn't change that much, so only check every 6 hours

# URLs to Openweathermap API
weather_feed = f"https://api.openweathermap.org/data/2.5/weather?lat=" + os.getenv("LATITUDE") +  "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY") + "&units=metric"
air_quality_feed = f"http://api.openweathermap.org/data/2.5/air_pollution?lat=" + os.getenv("LATITUDE") + "&lon=" + os.getenv("LONGITUDE") + "&appid=" + os.getenv("OPENWEATHER_API_KEY")
# MQTT feeds for publishing data to dashboard
weather_icon_feed = mqtt_remote_username + "/feeds/" + os.getenv("WEATHER_ICON_REMOTE_FEED")
pub_weather_feed = mqtt_remote_username + "/feeds/" + os.getenv("WEATHER_REMOTE_FEED")

# Gather all the weather and air quality data and format it into a report
last_report = None
info_spacer = '\u25AA'
def get_weather():
    global last_report
    degree_symbol = '\u00b0'
    daylight = False
#
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
        sunrise_unix = (weather["sys"]["sunrise"])
        sunset_unix = (weather["sys"]["sunset"])
        sunrise = format_time(sunrise_unix)
        sunset  = format_time(sunset_unix)
        air_quality, so2, so2_quality = get_air_quality()
        pressure = (weather["main"]["pressure"])
        pressure_indicator, publish_pressure = get_pressure_info(pressure)
        if query_time < sunset_unix:
            daylight = True
        w_icon = get_weather_icon(condition,daylight)
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
                pressure {publish_pressure} mmHg {pressure_indicator} 
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
                pressure {publish_pressure} mmHg {pressure_indicator} 
                """
            pass

        print("updating weather report on dashboard")
        do_publish(weather_icon_feed, w_icon)
        do_publish(pub_weather_feed, weather_for_dash)
        last_report = time.monotonic()

# API call returns the timestamp in Unix time format
# This method will reformat it to local time
# Using for: local times for sunrise/sunset
def format_time(timestamp):
    local_time = time.localtime(timestamp)
    return "{:02d}:{:02d}:{:02d}".format(local_time.tm_hour, local_time.tm_min, local_time.tm_sec)

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

indicator, stored_pressure_indicator, stored_pressure = None, None, None
def get_pressure_info(pressure):
    global stored_pressure, stored_pressure_indicator, indicator
    publish_pressure = round((pressure * 0.750061683), 2)

    if stored_pressure is None:
        indicator = '\u00A0'

    if stored_pressure is not None:
        if pressure > stored_pressure:
            indicator = '\u2BAC'
        elif pressure < stored_pressure:
            indicator = '\u2BAD'
        else:
            indicator = stored_pressure_indicator

    stored_pressure = pressure
    stored_pressure_indicator = indicator
    return indicator, publish_pressure

# MQTT feed for calendar
calendar_feed = mqtt_remote_username + "/feeds/" + os.getenv("CALENDAR_REMOTE_FEED")

last_calendar_check = None
def get_shared_calendar_events():
    global last_calendar_check

    if last_calendar_check is None or time.monotonic() > last_calendar_check + calendar_report_wait:
        creds = None
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

        try:
            service = build("calendar", "v3", credentials=creds)

            now = datetime.now(tz=timezone.utc).isoformat()
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

            if not events:
                pub_events = "No upcoming events found."
                do_publish(calendar_feed, pub_events)
            else:
                pub_array = []
                for event in events:
                    event_datetime = event["start"].get("dateTime")
                    print(event_datetime)
                    event_date, event_time = event_datetime.split("T")
                    event_year, event_month, event_day = event_date.split("-")
                    full_month = get_month_name(event_month)
                    event_start_time, event_end_time = event_time.split("-")
                    event_time_hr, event_time_min, event_time_sec = event_start_time.split(":")
                    publish_datetime = f"{event_day} {full_month} {event_year} at {event_time_hr}:{event_time_min}"
                    publish_event = event["summary"]
                    pub_array.append(publish_datetime + " " + info_spacer + " " + publish_event)


                if len(pub_array) == 0:
                    message = "No upcoming events found."
                elif len(pub_array) == 1:
                    message = f"{pub_array[0]}"
                else:
                    message = f"""\
                        {pub_array[0]}
                        {pub_array[1]}"""

                print("Publishing calendar events")
                do_publish(calendar_feed, message)

        except HttpError as error:
            print(f"An error occurred: {error}")
            pass

        last_calendar_check = time.monotonic()

pub_month = None
def get_month_name(month):
    global pub_month
    if month == "12":
        pub_month = "December"
    if month == "11":
        pub_month = "November"
    if month == "10":
        pub_month = "October"
    if month == "09":
        pub_month = "September"
    if month == "08":
        pub_month = "August"
    if month == "07":
        pub_month = "July"
    if month == "06":
        pub_month = "June"
    if month == "05":
        pub_month = "May"
    if month == "04":
        pub_month = "April"
    if month == "03":
        pub_month = "March"
    if month == "02":
        pub_month = "February"
    if month == "01":
        pub_month = "January"

    return pub_month

print("hello world, home hub is starting up!")
while True:
    get_date()
    get_time()
    get_weather()
    get_shared_calendar_events()

    time.sleep(0.5)
