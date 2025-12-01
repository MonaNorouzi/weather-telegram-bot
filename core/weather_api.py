# core/weather_api.py

import aiohttp
import config
import logging
from urllib.parse import quote
from typing import Tuple, Optional

async def get_coords_from_city(city_name: str) -> Tuple[Optional[float], Optional[float]]:
    safe_city = quote(city_name)
    url = f"https://api.openweathermap.org/geo/1.0/direct?q={safe_city}&limit=1&appid={config.WEATHER_API_KEY}"
    
    # Use proxy defined in config (or None)
    req_proxy = config.PROXY_URL

    try:
        async with aiohttp.ClientSession() as session:
            # Proxy is set dynamically here
            async with session.get(url, proxy=req_proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        return data[0]['lat'], data[0]['lon']
                else:
                    err = await response.text()
                    logging.error(f"Geo API Error {response.status}: {err}")
    except Exception as e:
        logging.error(f"Geocoding network error: {e}")
    
    return None, None

async def resolve_location_name(lat: float, lon: float) -> str:
    url = (
        f"https://api.openweathermap.org/geo/1.0/reverse?"
        f"lat={lat}&lon={lon}&"
        f"limit=1&appid={config.WEATHER_API_KEY}"
    )
    req_proxy = config.PROXY_URL

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, proxy=req_proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        return data[0]['name']
    except Exception as e:
        logging.error(f"Geo API Error: {e}")
    
    return f"Location ({lat:.2f}, {lon:.2f})"

async def get_weather(data: dict) -> str:
    timeout_settings = aiohttp.ClientTimeout(total=20)
    
    # Note: Changed 'lang=fa' to 'lang=en' for English descriptions
    if data['type'] == 'coords':
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={data['lat']}&lon={data['lon']}&appid={config.WEATHER_API_KEY}&lang=en"
    elif data['type'] == 'city':
        safe_city = quote(data['name'])
        url = f"https://api.openweathermap.org/data/2.5/weather?q={safe_city}&appid={config.WEATHER_API_KEY}&lang=en"
    else:
        return "⛔️ Internal Error: Bad Data Type"

    req_proxy = config.PROXY_URL

    try:
        # trust_env=True ensures it works if a system proxy is present
        async with aiohttp.ClientSession(timeout=timeout_settings, trust_env=True) as session:
            async with session.get(url, proxy=req_proxy) as response:
                
                if response.status != 200:
                    # Log exact error
                    error_text = await response.text()
                    logging.error(f"Weather API Failed: {response.status} - {error_text}")
                    
                    if response.status == 401:
                        return "⛔️ Error: Invalid API Key (check .env file)."
                    elif response.status == 404:
                        return "⛔️ Error: City not found."
                    else:
                        return f"⛔️ Server Error (Code {response.status})"

                result = await response.json()
                temp = result["main"]["temp"] - 273.15
                desc = result["weather"][0]["description"]
                humidity = result["main"]["humidity"]
                display_name = result.get("name", data.get('name', "Unknown"))

                return (
                    f"🌍 **Weather Report: {display_name}**\n"
                    f"-----------------------------------\n"
                    f"🌡 Temp: {temp:.1f}°C\n"
                    f"☁️ Status: {desc}\n"
                    f"💧 Humidity: {humidity}%\n"
                )
    except Exception as e:
        logging.error(f"Network Exception: {e}")
        return f"⛔️ Network Connection Error. (Need to configure PROXY_URL in .env)"