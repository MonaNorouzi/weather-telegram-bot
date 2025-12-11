# core/openmeteo_service.py
"""Open-Meteo weather API - FREE & unlimited"""

import aiohttp
import asyncio
import logging
import config
from datetime import datetime
from typing import Optional, Dict

class OpenMeteoService:
    BASE_URL = "https://api.open-meteo.com/v1"
    
    async def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """Get current weather for coordinates"""
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true"
        }
        
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        cw = data.get("current_weather", {})
                        return {
                            "temp": cw.get("temperature"),
                            "windspeed": cw.get("windspeed"),
                            "weathercode": cw.get("weathercode"),
                            "icon": self._code_to_emoji(cw.get("weathercode", 0))
                        }
        except Exception as e:
            logging.error(f"Open-Meteo error: {e}")
        return None
    
    async def get_forecast_at_time(self, lat: float, lon: float, target_time: datetime) -> Optional[Dict]:
        """Get weather forecast for specific time"""
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,weathercode",
            "forecast_days": 3
        }
        
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hourly = data.get("hourly", {})
                        times = hourly.get("time", [])
                        temps = hourly.get("temperature_2m", [])
                        codes = hourly.get("weathercode", [])
                        
                        # Find closest hour
                        target_str = target_time.strftime("%Y-%m-%dT%H:00")
                        
                        for i, t in enumerate(times):
                            if t >= target_str:
                                return {
                                    "temp": round(temps[i]) if i < len(temps) else None,
                                    "weathercode": codes[i] if i < len(codes) else 0,
                                    "icon": self._code_to_emoji(codes[i] if i < len(codes) else 0)
                                }
                        
                        # Fallback to last available
                        if temps:
                            return {
                                "temp": round(temps[-1]),
                                "weathercode": codes[-1] if codes else 0,
                                "icon": self._code_to_emoji(codes[-1] if codes else 0)
                            }
        except Exception as e:
            logging.error(f"Open-Meteo forecast error: {e}")
        return None
    
    async def get_batch_forecasts(self, locations_with_times):
        """Get weather for MANY locations in batches - FAST!
        
        Open-Meteo documentation says we can pass multiple lat/lon pairs.
        This reduces 747 API calls to just ~8 batch calls!
        """
        results = {}
        batch_size = 100  # Process 100 locations per API call
        
        logging.info(f"Fetching weather for {len(locations_with_times)} locations in batches of {batch_size}")
        
        for batch_idx in range(0, len(locations_with_times), batch_size):
            batch = locations_with_times[batch_idx:batch_idx+batch_size]
            
            # Build comma-separated lat/lon strings
            lats = ",".join(str(lat) for lat, lon, _ in batch)
            lons = ",".join(str(lon) for lat, lon, _ in batch)
            
            url = f"{self.BASE_URL}/forecast"
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": "temperature_2m",
                "forecast_days": 3
            }
            
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            # Check if response is a list (multiple locations)
                            if isinstance(data, list):
                                # Multiple locations returned
                                for j, (lat, lon, target_time) in enumerate(batch):
                                    if j < len(data):
                                        results[(lat, lon)] = self._parse_single_forecast(data[j], target_time)
                            else:
                                # Single location (batch size was 1)
                                lat, lon, target_time = batch[0]
                                results[(lat, lon)] = self._parse_single_forecast(data, target_time)
                        else:
                            logging.warning(f"Batch weather API returned status {resp.status}")
                            # Mark all as None
                            for lat, lon, _ in batch:
                                results[(lat, lon)] = None
            except Exception as e:
                logging.error(f"Batch weather fetch error: {e}")
                # Mark all as None
                for lat, lon, _ in batch:
                    results[(lat, lon)] = None
            
            # Delay between batches to respect rate limits
            await asyncio.sleep(1.0)  # 1 second between batches to avoid 429
            
            if (batch_idx +batch_size) % 300 == 0:
                logging.info(f"Weather fetch progress: {min(batch_idx + batch_size, len(locations_with_times))}/{len(locations_with_times)}")
        
        logging.info(f"Batch weather fetch complete: {len(results)} results")
        return results
    
    def _parse_single_forecast(self, data: dict, target_time: datetime) -> Optional[Dict]:
        """Parse a single location's forecast data"""
        try:
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            
            # Find closest hour
            target_str = target_time.strftime("%Y-%m-%dT%H:00")
            
            for i, t in enumerate(times):
                if t >= target_str and i < len(temps):
                    return {"temp": round(temps[i])}
            
            # Fallback to last available
            if temps:
                return {"temp": round(temps[-1])}
        except Exception as e:
            logging.debug(f"Parse forecast error: {e}")
        return None
    
    def _code_to_emoji(self, code: int) -> str:
        """Convert WMO weather code to emoji"""
        if code == 0:
            return "☀️"  # Clear
        elif code in [1, 2, 3]:
            return "🌤️"  # Partly cloudy
        elif code in [45, 48]:
            return "🌫️"  # Fog
        elif code in [51, 53, 55, 56, 57]:
            return "🌧️"  # Drizzle
        elif code in [61, 63, 65, 66, 67]:
            return "🌧️"  # Rain
        elif code in [71, 73, 75, 77]:
            return "❄️"  # Snow
        elif code in [80, 81, 82]:
            return "🌧️"  # Showers
        elif code in [85, 86]:
            return "🌨️"  # Snow showers
        elif code in [95, 96, 99]:
            return "⛈️"  # Thunderstorm
        return "🌡️"

openmeteo_service = OpenMeteoService()
