from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import random
from datetime import datetime, timedelta
from dateutil.parser import parse
import re
import json


class Weather(Action):
    def name(self) -> Text:
        return "action_get_weather"
    
    # function to parse the weather_time slot into a number of days for the API call
    def parse_date(self, date_string):
        if date_string is None:
            return 0
        elif date_string == "today":
            return 0
        elif date_string == "tomorrow":
            return 1
        # for relative answers like "in 5 days"
        elif "in" in date_string and "days" in date_string:
            return int(re.search(r'\d+', date_string).group())
        # datetime parse for different date formats turned into a timedelta from today
        else:
            try:
                return (parse(date_string).date() - datetime.now().date()).days
            except ValueError:
                return 0

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # get location and request type from slot
        city = tracker.get_slot('location')
        request_type = tracker.get_slot('request_type')
        
        # parse_date weather_time slot to get the time difference to today in days
        time_diff = self.parse_date(tracker.get_slot('weather_time'))
        
        # fail elegantly if location is not provided
        if not city:
                dispatcher.utter_message("Could you please give me a location for the weather request.")
                return []
        
        # compose api url from key and location and time requested
        api_key = "16228074ed6a7ed6219527d88f4a0bd4"
        #skeleton = "http://api.openweathermap.org/data/2.5/weather?q={}&appid={}" # optional current weather api call
        skeleton = "http://api.openweathermap.org/data/2.5/forecast?q={}&appid={}" # api call for the forecast of the next 5 days in 3 hour intervals
        complete_url = skeleton.format(city, api_key)
        
        # get weather data from api and convert to json dictionary
        response = requests.get(complete_url)
        weather_data = response.json()
        
        # filter list for 12 o'clock to exclude unnecessary data for daily forecast
        filtered_list = [item for item in weather_data['list'] if item['dt_txt'].endswith("12:00:00")]
        # Create a new dictionary with the filtered list
        filtered_dict = {key: value for key, value in weather_data.items() if key != 'list'}
        filtered_dict['list'] = filtered_list
        filtered_dict['cnt'] = len(filtered_list)

        # time_element for use in call
        if time_diff == 0:
            time_element = weather_data['list'][0]
        elif time_diff <=4:
            time_element = filtered_dict['list'][int(time_diff)]
        else:
            weather_response = "I can only provide weather information for the next 4 days."
        
        # extract temperature and weather description, as well as the specific request
        temperature = round(time_element['main']['temp'] - 273.15, 1)
        description = time_element['weather'][0]['description']
        main_description = time_element['weather'][0]['main']
        cloudiness = time_element['clouds']
        feels_like = round(time_element['main']['feels_like'] - 273.15, 1)
        humidity = time_element['main']['humidity']
        wind_speed = time_element['wind']['speed']
        # additional conditions for snowfall and rainfall, as they are not always present in the json
        if 'rain' in time_element:
            rainfall = round(time_element['rain']["3h"] / 3, 0)
        else:
            rainfall = 0
        if 'snow' in time_element:
            snowfall = round(time_element['snow']['3h'] / 3, 0)
        else:
            snowfall = 0
       
        
        
        # compose responses depending on the request type when time_diff is 0, so today
        if time_diff == 0:
            # current general or temperature request answer
            if request_type == None or request_type == "temperature":
                weather_response = "The temperature in {} is {} degrees with {}.".format(city, temperature, description)
            
            # current cloudiness request answer formatted for percentage bins
            elif request_type == "cloudiness":
                if description == "clear sky":
                    weather_response = "The sky is clear in {}, so there are no clouds.".format(city)
                elif cloudiness < 25:
                    weather_response = "The sky in {} is mostly clear with only a {}.".format(city, description)
                else:
                    weather_response = "It is currently {} in {}, so yes the sky is cloudy.".format(description, city)
            
            # current apparent temperature request answer   
            elif request_type == "feels_like":
                weather_response = "It feels like {} degrees in {}, with an actual temperature of {}.".format(feels_like, city, temperature)

            # current humidity request answer
            elif request_type == "humidity":
                weather_response = "The humidity in {} is currently at {}%.".format(city, humidity)
            
            # current rainfall request answer
            elif request_type == "rainfall":
                if rainfall == None or rainfall == 0:
                    weather_response = "There is currently no rainfall in {}.".format(city)
                else:
                    weather_response = "The rainfall in {} in the last hour is currently at {} mm.".format(city, rainfall)
             
            # current rainy request answer
            elif request_type == "rainy":
                if main_description in ["rain", "shower rain", "thunderstorm", "drizzle"]:
                    weather_response = "There is currently {} in {}.".format(description, city)
                else:
                    weather_response = "There is currently no rain in {}.".format(city)

            # current snowfall request answer
            elif request_type == "snowfall":
                if "snow" in main_description:
                    weather_response = "It is currently snowing in {}.".format(city)
                else:
                    weather_response = "It is currently not snowing in {}.".format(city)
            
            # current snowy request answer
            elif request_type == "snowy":
                if "snow" in main_description:
                    weather_response = "There is currently {} mm snowfall per hour in {}.".format(snowfall, city)
                else:
                    weather_response = "There is currently no snowfall in {}.".format(city)

            # current sunshine request answer depending on description
            elif request_type == "sunshine":
                if description == "clear sky":
                    weather_response = "The sky is clear in {}, so there is a lot of sunshine.".format(city)
                elif description == "few clouds":
                    weather_response = "There are a few clouds in the sky in {}, but there is still a decent amount of sunshine.".format(city)
                elif description == "scattered clouds":
                    weather_response = "There are scattered clouds in the sky in {}, but the sun might poke through here and there.".format(city)
                else:
                    weather_response = "The is currently {} in {}, so it is not sunny.".format(description, city)
            
            # current wind speed request answer
            elif request_type == "wind_speed":
                weather_response = "The wind speed in {} currently is {} m/s.".format(city, wind_speed)
        
        # compose responses depending on the request type when the time call is between tomorrow and in 4 days
        elif time_diff > 0 and time_diff <= 4:
            # future general or temperature request answer
            if request_type == None or request_type == "temperature":
                weather_response = "It looks like the temperature in {} will be {} degrees with {}.".format(city, temperature, description)
            
            # future cloudiness request answer formatted for percentage bins
            elif request_type == "cloudiness":
                if description == "clear sky":
                    weather_response = "The sky will be clear in {}, so there probably won't be any clouds.".format(city)
                elif cloudiness < 25:
                    weather_response = "It looks liek the sky in {} will mostly be clear with only a {}.".format(city, description)
                else:
                    weather_response = "It looks like {} in {}, so yes the sky will be cloudy.".format(description, city)
            
            # future apparent temperature request answer    
            elif request_type == "feels_like":
                weather_response = "It is going to feel like {} degrees in {}, with an actual temperature of {}.".format(feels_like, city, temperature)

            # future humidity request answer
            elif request_type == "humidity":
                weather_response = "It looks like the humidity in {} will be at {}%.".format(city, humidity)
            
            # future rainfall request answer
            elif request_type == "rainfall":
                if rainfall == None or rainfall == 0:
                    weather_response = "There will propably be no rainfall in {}.".format(city)
                else:
                    weather_response = "The hourly rainfall in {} will be at {} mm.".format(city, rainfall)
            
            # future rainy request answer    
            elif request_type == "rainy":
                if main_description in ["rain", "shower rain", "thunderstorm", "drizzle"]:
                    weather_response = "There is going to be {} in {}.".format(description, city)
                else:
                    weather_response = "It looks like there will be no rain in {}.".format(city)

            # future snowfall request answer
            elif request_type == "snowfall":
                if "snow" in main_description:
                    weather_response = "It looks like it will be snowing in {}.".format(city)
                else:
                    weather_response = "It looks like it won't be snowing in {}.".format(city)
            
            # future snowy request answer    
            elif request_type == "snowy":
                if "snow" in main_description:
                    weather_response = "There is going to be {} mm snowfall per hour in {}.".format(snowfall, city)
                else:
                    weather_response = "There won't be any snowfall in {}.".format(city)

            # future sunshine request answer depending on description
            elif request_type == "sunshine":
                if description == "clear sky":
                    weather_response = "The sky will be clear in {}, so it looks like there will be a lot of sunshine.".format(city)
                elif description == "few clouds":
                    weather_response = "There might be few clouds in the sky in {}, but there will still be a decent amount of sunshine.".format(city)
                elif description == "scattered clouds":
                    weather_response = "There will be scattered clouds in the sky in {}, but the sun might poke through here and there.".format(city)
                else:
                    weather_response = "The will be {} in {}, so no sunrays will show themselves.".format(description, city)
            
            # future wind speed request answer
            elif request_type == "wind_speed":
                weather_response = "The wind speed in {} will be {} m/s.".format(city, wind_speed)
        
        # fail elegantly if the time_diff is outside the bot's prediction range
        else:
            weather_response = "This is outside of my prediction range. I can only provide weather information for the next 4 days."
            
        # send response back
        dispatcher.utter_message(weather_response)

        return [SlotSet("location", city)]
