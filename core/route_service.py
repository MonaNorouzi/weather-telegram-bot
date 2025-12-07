# core/route_service.py
"""Service for finding cities and routes between locations"""

import aiohttp
import config
import logging
from typing import List, Dict, Optional, Tuple

class RouteService:
    BASE_URL = "https://api.openrouteservice.org"
    
    def __init__(self):
        self.api_key = config.OPENROUTE_API_KEY
        if not self.api_key:
            logging.warning("⚠️ OPENROUTE_API_KEY is missing.")

    async def get_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """Search for a city and return (lat, lon)"""
        if not self.api_key: 
            logging.error("No API key for geocoding")
            return None
        try:
            url = f"{self.BASE_URL}/geocode/search"
            params = {"api_key": self.api_key, "text": city_name, "size": 1}
            logging.info(f"🔍 Geocoding: {city_name}")
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params) as resp:
                    logging.info(f"🔍 Geocode response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("features"):
                            c = data["features"][0]["geometry"]["coordinates"]
                            logging.info(f"✅ Found: {city_name} at {c[1]}, {c[0]}")
                            return (c[1], c[0])
                        else:
                            logging.warning(f"⚠️ No features for: {city_name}")
                    else:
                        text = await resp.text()
                        logging.error(f"❌ Geocode API error: {resp.status} - {text[:200]}")
        except Exception as e:
            logging.error(f"Geocoding error: {e}")
        return None

    async def get_city_name(self, lat: float, lon: float) -> Optional[str]:
        """Reverse geocode coordinates to get city/locality name"""
        if not self.api_key: return None
        try:
            url = f"{self.BASE_URL}/geocode/reverse"
            params = {
                "api_key": self.api_key, 
                "point.lat": lat, 
                "point.lon": lon, 
                "size": 1,
                "layers": "locality,county,region"  # Only get city-level, not POIs
            }
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("features"):
                            p = data["features"][0]["properties"]
                            # Prefer locality (city), then county, then region
                            return (p.get("locality") or 
                                    p.get("county") or 
                                    p.get("region") or 
                                    p.get("name") or 
                                    "Unknown")
        except Exception as e:
            logging.error(f"Reverse geocoding error: {e}")
        return None

    async def get_route(self, origin: Tuple[float, float], dest: Tuple[float, float]) -> Optional[Dict]:
        """Get driving route between two points"""
        if not self.api_key: return None
        try:
            url = f"{self.BASE_URL}/v2/directions/driving-car/geojson"
            headers = {"Authorization": self.api_key, "Content-Type": "application/json"}
            body = {"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]}
            async with aiohttp.ClientSession() as sess:
                async with sess.post(url, json=body, headers=headers) as resp:
                    if resp.status == 200: return await resp.json()
        except Exception as e:
            logging.error(f"Route error: {e}")
        return None

    async def get_cities_along_route(self, route_geojson: Dict, num_samples: int = 6) -> List[Dict]:
        """Extract city names along the route"""
        if not route_geojson or not route_geojson.get("features"): return []
        try:
            coords = route_geojson["features"][0]["geometry"]["coordinates"]
            total = len(coords)
            if total == 0: return []

            # Sample points: Start + End + Middle points
            step = max(1, total // (num_samples + 1))
            indices = sorted(list({0, total - 1} | set(range(step, total - 1, step))))
            
            cities = []
            seen = set()
            for idx in indices:
                pt = coords[idx]
                name = await self.get_city_name(pt[1], pt[0])
                if name and name not in seen:
                    seen.add(name)
                    cities.append({
                        "name": name, "lat": pt[1], "lon": pt[0],
                        "type": "Start" if idx == 0 else ("End" if idx == total - 1 else "Waypoint")
                    })
            return cities
        except Exception as e:
            logging.error(f"Error extracting cities: {e}")
            return []

route_service = RouteService()
