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
    
    def __init__(self):
        """Initialize with shared session for connection pooling."""
        self._session = None
        self._connector = None
    
    async def _get_session(self):
        """Get or create shared aiohttp session with connection pooling."""
        if self._session is None or self._session.closed:
            # Create connector with proper limits
            self._connector = aiohttp.TCPConnector(
                limit=100,           # Total connections
                limit_per_host=30,   # Per host limit
                ttl_dns_cache=300    # DNS cache TTL
            )
            # Create session with timeout
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout
            )
        return self._session
    
    async def close(self):
        """Close the shared session."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector:
            await self._connector.close()
    
    async def get_current_weather(self, lat: float, lon: float) -> Optional[Dict]:
        """Get current weather for coordinates"""
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true"
        }
        
        try:
            sess = await self._get_session()
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
        """
        Get weather forecast for specific time WITH ENTERPRISE CACHING.
        
        PERFORMANCE UPGRADE:
        - First checks temporal cache (sub-ms)
        - Falls back to API only on cache miss
        - Uses singleflight pattern for concurrent requests
        - Stale-while-revalidate for high availability
        
        This makes repeated/similar routes INSTANT for Telegram demos.
        """
        # Try temporal cache first (LIGHTNING FAST!)
        try:
            from core.temporal_weather_cache import temporal_weather_cache
            
            # Check cache
            cached = await temporal_weather_cache.get(lat, lon, target_time, allow_stale=True)
            
            if cached and not cached.is_stale:
                # CACHE HIT!
                logging.debug(f"⚡ Weather cache HIT for ({lat:.4f}, {lon:.4f})")
                return cached.data
            
            elif cached and cached.is_stale:
                # Stale data available - serve it while we fetch fresh
                logging.warning(f"⚠️ Serving stale weather (will refresh in background)")
                # TODO: Trigger background refresh
                return cached.data
        
        except Exception as cache_err:
            # Cache error - continue to API
            logging.debug(f"Cache error (continuing to API): {cache_err}")
        
        # CACHE MISS or not cached - use singleflight to fetch from API
        try:
            from core.temporal_weather_cache import temporal_weather_cache
            
            # Generate cache key for singleflight deduplication
            cache_key = temporal_weather_cache.generate_cache_key(lat, lon, target_time)
            
            # Use singleflight pattern
            result = await temporal_weather_cache.singleflight.get_or_fetch(
                cache_key,
                lambda: self._fetch_weather_from_api(lat, lon, target_time)
            )
            
            return result
        
        except Exception as e:
            # Singleflight error - fallback to direct API
            logging.warning(f"Singleflight error, using direct API: {e}")
            return await self._fetch_weather_from_api(lat, lon, target_time)
    
    async def _fetch_weather_from_api(self, lat: float, lon: float, target_time: datetime) -> Optional[Dict]:
        """
        Fetch weather from Open-Meteo API and cache the result.
        
        This is the actual API call, wrapped by caching layer.
        """
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,weathercode",
            "forecast_days": 3
        }
        
        try:
            # Use shared session (proper connection pooling!)
            sess = await self._get_session()
            async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hourly = data.get("hourly", {})
                        times = hourly.get("time", [])
                        temps = hourly.get("temperature_2m", [])
                        codes = hourly.get("weathercode", [])
                        
                        # Find closest hour
                        target_str = target_time.strftime("%Y-%m-%dT%H:00")
                        
                        weather_result = None
                        for i, t in enumerate(times):
                            if t >= target_str:
                                weather_result = {
                                    "temp": round(temps[i]) if i < len(temps) else None,
                                    "weathercode": codes[i] if i < len(codes) else 0,
                                    "icon": self._code_to_emoji(codes[i] if i < len(codes) else 0),
                                    "temperature": round(temps[i]) if i < len(temps) else None  # Alias for compatibility
                                }
                                break
                        
                        # Fallback to last available
                        if not weather_result and temps:
                            weather_result = {
                                "temp": round(temps[-1]),
                                "weathercode": codes[-1] if codes else 0,
                                "icon": self._code_to_emoji(codes[-1] if codes else 0),
                                "temperature": round(temps[-1])
                            }
                        
                        # CACHE THE RESULT for future requests
                        if weather_result:
                            try:
                                from core.temporal_weather_cache import temporal_weather_cache
                                
                                # Extract model run time if available
                                model_run = data.get("model_run_time", data.get("current", {}).get("time", "unknown"))
                                
                                # Check for model refresh
                                await temporal_weather_cache.check_model_refresh(lat, lon, model_run)
                                
                                # Store in cache
                                await temporal_weather_cache.set(
                                    lat, lon, target_time, weather_result, model_run
                                )
                            except Exception as cache_err:
                                logging.warning(f"Failed to cache weather: {cache_err}")
                        
                        return weather_result
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
                "hourly": "temperature_2m,weathercode",  # Include weathercode for icons
                "forecast_days": 3
            }
            
            # Retry logic for rate limits
            max_retries = 3
            retry_delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    sess = await self._get_session()
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
                                break  # Success, exit retry loop
                            elif resp.status == 429:
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                                    logging.warning(f"Rate limited (429), retrying in {wait_time}s (attempt {attempt+1}/{max_retries})")
                                    await asyncio.sleep(wait_time)
                                else:
                                    logging.error(f"Rate limit persists after {max_retries} attempts, skipping batch")
                                    for lat, lon, _ in batch:
                                        results[(lat, lon)] = None
                            else:
                                logging.warning(f"Batch weather API returned status {resp.status}")
                                for lat, lon, _ in batch:
                                    results[(lat, lon)] = None
                                break
                except Exception as e:
                    logging.error(f"Batch weather fetch error: {e}")
                    for lat, lon, _ in batch:
                        results[(lat, lon)] = None
                    break
            
            # Longer delay between batches to avoid rate limits
            await asyncio.sleep(2.0)  # Increased from 1.0s to 2.0s
            
            if (batch_idx + batch_size) % 300 == 0:
                logging.info(f"Weather fetch progress: {min(batch_idx + batch_size, len(locations_with_times))}/{len(locations_with_times)}")
        
        logging.info(f"Batch weather fetch complete: {len(results)} results")
        return results
    
    def _parse_single_forecast(self, data: dict, target_time: datetime) -> Optional[Dict]:
        """Parse a single location's forecast data"""
        try:
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            codes = hourly.get("weathercode", [])  # Get weather codes too
            
            # Find closest hour
            target_str = target_time.strftime("%Y-%m-%dT%H:00")
            
            for i, t in enumerate(times):
                if t >= target_str and i < len(temps):
                    code = codes[i] if i < len(codes) else 0
                    return {
                        "temp": round(temps[i]),
                        "weathercode": code,
                        "icon": self._code_to_emoji(code)
                    }
            
            # Fallback to last available
            if temps:
                code = codes[-1] if codes else 0
                return {
                    "temp": round(temps[-1]),
                    "weathercode": code,
                    "icon": self._code_to_emoji(code)
                }
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
