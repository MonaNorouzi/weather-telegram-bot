# core/osrm_service.py
"""OSRM (Open Source Routing Machine) - FREE & FAST routing"""

import aiohttp
import logging
import config
from typing import Optional, Dict, List, Tuple

class OSRMService:
    BASE_URL = "https://router.project-osrm.org"
    
    async def get_route(self, origin: Tuple[float, float], dest: Tuple[float, float]) -> Optional[Dict]:
        """Get driving route with full geometry"""
        coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        url = f"{self.BASE_URL}/route/v1/driving/{coords}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true"
        }
        
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == "Ok" and data.get("routes"):
                            route = data["routes"][0]
                            return {
                                "coordinates": route["geometry"]["coordinates"],
                                "distance": route["distance"],
                                "duration": route["duration"],
                                "steps": route.get("legs", [{}])[0].get("steps", [])
                            }
                    else:
                        logging.error(f"OSRM error: {resp.status}")
        except Exception as e:
            logging.error(f"OSRM error: {e}")
        return None
    
    async def get_route_with_annotations(self, origin: Tuple[float, float], dest: Tuple[float, float]) -> Optional[Dict]:
        """Get driving route WITH duration annotations for accurate timing
        
        Annotations provide segment-by-segment duration data, enabling precise
        arrival time calculations for places along the route.
        """
        coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        url = f"{self.BASE_URL}/route/v1/driving/{coords}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "annotations": "duration"  # Request duration for each segment
        }
        
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == "Ok" and data.get("routes"):
                            route = data["routes"][0]
                            leg = route.get("legs", [{}])[0]
                            annotation = leg.get("annotation", {})
                            
                            return {
                                "coordinates": route["geometry"]["coordinates"],
                                "distance": route["distance"],
                                "duration": route["duration"],
                                "durations": annotation.get("duration", []),  # Segment durations
                                "steps": leg.get("steps", [])
                            }
                    else:
                        logging.error(f"OSRM error: {resp.status}")
        except Exception as e:
            logging.error(f"OSRM error: {e}")
        return None
    
    async def get_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """Geocode city name to coordinates using Nominatim"""
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": city_name,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "WeatherBot/1.0"}
        
        try:
            async with aiohttp.ClientSession(headers=headers) as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return (float(data[0]["lat"]), float(data[0]["lon"]))
        except Exception as e:
            logging.error(f"Geocoding error: {e}")
        return None

osrm_service = OSRMService()
