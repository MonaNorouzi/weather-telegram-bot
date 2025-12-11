# core/fast_geocoder.py
"""Fast batched reverse geocoding using Nominatim - reliable and gets 400+ places"""

import aiohttp
import asyncio
import logging
import config
from typing import List, Dict, Optional, Tuple
import time

class FastGeocoder:
    """Batched reverse geocoding using Nominatim - respects 1 req/sec limit"""
    BASE_URL = "https://nominatim.openstreetmap.org/reverse"
    
    def __init__(self):
        self.headers = {"User-Agent": "WeatherBot/1.0 (Telegram Weather Bot)"}
        self.last_request = 0
    
    async def geocode_points_parallel(self, points: List[Tuple[float, float]], 
                                       max_concurrent: int = 1) -> List[Dict]:
        """Reverse geocode many points respecting rate limit"""
        
        results = []
        
        for i, (lat, lon) in enumerate(points):
            # Wait 1 second between requests
            await asyncio.sleep(1.0)
            
            result = await self._reverse_geocode(lat, lon)
            if result:
                result["idx"] = i
                results.append(result)
            
            # Progress every 50
            if (i + 1) % 50 == 0:
                logging.info(f"Geocoded {i+1}/{len(points)}, found {len(results)} unique")
        
        return self._deduplicate(results)
    
    async def _reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """Single reverse geocode call"""
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "zoom": 14  # City/village/suburb level
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=self.headers) as sess:
                async with sess.get(self.BASE_URL, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self._parse_nominatim(data, lat, lon)
        except Exception as e:
            logging.debug(f"Geocode error: {e}")
        return None
    
    def _parse_nominatim(self, data: dict, lat: float, lon: float) -> Dict:
        """Parse Nominatim response"""
        address = data.get("address", {})
        
        name = (
            address.get("village") or
            address.get("town") or
            address.get("city") or
            address.get("suburb") or
            address.get("neighbourhood") or
            address.get("hamlet") or
            address.get("county") or
            address.get("district") or
            data.get("name") or
            "Unknown"
        )
        
        place_type = data.get("type", "unknown")
        
        type_map = {
            "village": "village", "town": "town", "city": "city",
            "suburb": "suburb", "hamlet": "hamlet", "neighbourhood": "suburb",
            "residential": "suburb", "administrative": "city"
        }
        
        return {
            "name": name,
            "type": type_map.get(place_type, place_type),
            "lat": lat,
            "lon": lon
        }
    
    def _deduplicate(self, places: List[Dict]) -> List[Dict]:
        """Remove duplicates keeping order"""
        seen = set()
        unique = []
        for p in places:
            key = (p["name"], round(p["lat"], 4), round(p["lon"], 4))
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

fast_geocoder = FastGeocoder()
