# core/location_parser.py
"""Parse location from various input formats"""

import re
import aiohttp
from urllib.parse import unquote
from typing import Optional, Dict, Union

# Coordinate patterns
COORD_PATTERNS = [
    r'@(-?\d+\.\d+),(-?\d+\.\d+)',       # @35.7,51.4
    r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',   # Google: !3d35.7!4d51.4
    r'q=(-?\d+\.\d+),(-?\d+\.\d+)',      # Query param
]

# Name patterns
NAME_PATTERNS = [r'/place/([^/]+)', r'/search/([^/]+)']
IGNORE_NAMES = ["data", "wms", "api", "preview"]


async def parse_input(input_data: Union[str, object]) -> Optional[Dict]:
    """Parse location from various input formats"""
    
    # Telegram Location Object
    if hasattr(input_data, 'lat') and hasattr(input_data, 'long'):
        return {'type': 'coords', 'lat': float(input_data.lat), 'lon': float(input_data.long)}

    if isinstance(input_data, str):
        text = input_data.strip()
        
        # URL Processing
        if any(x in text.lower() for x in ["http", "google", "goo.gl", "maps"]):
            url = await _expand_url(text)
            if not url:
                return None
            
            # Try coordinates
            for pattern in COORD_PATTERNS:
                m = re.search(pattern, url)
                if m:
                    return {'type': 'coords', 'lat': float(m.group(1)), 'lon': float(m.group(2))}
            
            # Try place name
            for pattern in NAME_PATTERNS:
                m = re.search(pattern, url)
                if m:
                    name = unquote(m.group(1)).replace('+', ' ')
                    if name.lower() not in IGNORE_NAMES:
                        return {'type': 'city', 'name': name}
        else:
            return _parse_raw_coords(text)
    
    return None


async def _expand_url(url: str) -> Optional[str]:
    """Expand short URLs"""
    if not url.startswith("http"):
        url = "https://" + url
    
    headers = {"User-Agent": "Mozilla/5.0 Chrome/91.0"}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as s:
            async with s.get(url, allow_redirects=True) as r:
                return str(r.url)
    except:
        return None


def _parse_raw_coords(text: str) -> Optional[Dict]:
    """Parse raw coordinate text"""
    try:
        parts = [p for p in text.replace(' ', ',').split(',') if p]
        if len(parts) >= 2:
            lat, lon = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90:
                return {'type': 'coords', 'lat': lat, 'lon': lon}
    except:
        pass
    return None