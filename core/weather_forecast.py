# core/weather_forecast.py
"""Weather forecast functions for route planning"""

import aiohttp
import config
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict

async def get_forecast_at_time(lat: float, lon: float, target_time: datetime) -> Optional[Dict]:
    """Get weather forecast for a location at a specific time"""
    url = (
        f"https://api.openweathermap.org/data/2.5/forecast?"
        f"lat={lat}&lon={lon}&appid={config.WEATHER_API_KEY}&units=metric"
    )
    
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, proxy=config.PROXY_URL) as resp:
                if resp.status != 200:
                    return None
                    
                data = await resp.json()
                forecasts = data.get("list", [])
                
                # Find closest forecast to target time
                closest = None
                min_diff = float('inf')
                
                for fc in forecasts:
                    fc_time = datetime.fromtimestamp(fc["dt"])
                    diff = abs((fc_time - target_time).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest = fc
                
                if closest:
                    return {
                        "temp": round(closest["main"]["temp"]),
                        "desc": closest["weather"][0]["description"],
                        "icon": get_weather_emoji(closest["weather"][0]["id"])
                    }
    except Exception as e:
        logging.error(f"Forecast error: {e}")
    
    return None

def get_weather_emoji(code: int) -> str:
    """Convert weather code to emoji"""
    if code >= 200 and code < 300:
        return "⛈️"  # Thunderstorm
    elif code >= 300 and code < 400:
        return "🌧️"  # Drizzle
    elif code >= 500 and code < 600:
        return "🌧️"  # Rain
    elif code >= 600 and code < 700:
        return "❄️"  # Snow
    elif code >= 700 and code < 800:
        return "🌫️"  # Fog
    elif code == 800:
        return "☀️"  # Clear
    elif code > 800:
        return "☁️"  # Cloudy
    return "🌡️"
