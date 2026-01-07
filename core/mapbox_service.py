"""Mapbox Directions API Service - Production-grade routing"""

import aiohttp
import logging
import polyline
from typing import Optional, Dict, Tuple
import asyncio

logger = logging.getLogger(__name__)


class MapboxService:
    """Mapbox Directions API wrapper with retry logic and fallback"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mapbox.com/directions/v5/mapbox/driving"
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def get_route(
        self, 
        origin: Tuple[float, float], 
        dest: Tuple[float, float]
    ) -> Optional[Dict]:
        """Get driving route with full geometry from Mapbox.
        
        Args:
            origin: (latitude, longitude) of starting point
            dest: (latitude, longitude) of destination
            
        Returns:
            Dict with coordinates, distance, duration, and polyline or None if failed
        """
        coordinates = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        url = f"{self.base_url}/{coordinates}"
        
        params = {
            "access_token": self.api_key,
            "geometries": "polyline6",
            "overview": "full",
            "steps": "false",
            "annotations": "duration"
        }
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            if data.get("code") == "Ok" and data.get("routes"):
                                route = data["routes"][0]
                                geometry = route["geometry"]
                                coordinates_decoded = polyline.decode(geometry, geojson=False, precision=6)
                                
                                return {
                                    "coordinates": coordinates_decoded,
                                    "distance": route["distance"],
                                    "duration": route["duration"],
                                    "polyline": geometry
                                }
                            else:
                                error_code = data.get("code", "Unknown")
                                logger.error(f"Mapbox error code: {error_code}")
                                
                        elif resp.status == 429:
                            logger.warning(f"Mapbox rate limit (attempt {attempt + 1}/{self.max_retries})")
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(self.retry_delay * (2 ** attempt))
                                continue
                            else:
                                logger.error("Mapbox quota exhausted")
                                return None
                        
                        elif resp.status == 401:
                            logger.error("Mapbox API key invalid")
                            return None
                        
                        else:
                            logger.error(f"Mapbox HTTP error: {resp.status}")
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(self.retry_delay)
                                continue
                
            except asyncio.TimeoutError:
                logger.warning(f"Mapbox timeout (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                    
            except Exception as e:
                logger.error(f"Mapbox error: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
        
        return None
