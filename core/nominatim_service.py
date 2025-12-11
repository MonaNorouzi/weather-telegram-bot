# core/nominatim_service.py
"""Photon (OpenStreetMap) reverse geocoding - FREE & FAST (no rate limit)"""

import aiohttp
import logging
import config
from typing import Optional, Dict

class NominatimService:
    # Using Photon API instead of Nominatim - much faster, no rate limit
    BASE_URL = "https://photon.komoot.io"
    
    def __init__(self):
        self.headers = {"User-Agent": "WeatherBot/1.0"}
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict]:
        """Get place details from coordinates - FAST, no rate limit!"""
        url = f"{self.BASE_URL}/reverse"
        params = {"lat": lat, "lon": lon}
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as sess:
                async with sess.get(url, params=params, proxy=config.PROXY_URL) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        features = data.get("features", [])
                        if features:
                            return self._parse_response(features[0])
        except Exception as e:
            logging.error(f"Photon error: {e}")
        return None
    
    def _parse_response(self, feature: dict) -> Dict:
        """Parse Photon response into our format"""
        props = feature.get("properties", {})
        
        # Determine place name (priority order)
        name = (
            props.get("name") or
            props.get("city") or
            props.get("town") or
            props.get("village") or
            props.get("suburb") or
            props.get("district") or
            props.get("county") or
            "Unknown"
        )
        
        # Determine place type
        osm_key = props.get("osm_key", "")
        osm_value = props.get("osm_value", "")
        place_type = osm_value if osm_value else osm_key
        
        # Map to our types
        type_mapping = {
            "village": "village",
            "town": "town", 
            "city": "city",
            "suburb": "suburb",
            "hamlet": "hamlet",
            "neighbourhood": "suburb",
            "residential": "suburb",
            "administrative": "city"
        }
        
        final_type = type_mapping.get(place_type, place_type)
        
        return {
            "place": name,
            "type": final_type,
            "country": props.get("country", ""),
            "state": props.get("state", "")
        }

nominatim_service = NominatimService()
