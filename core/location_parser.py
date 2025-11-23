# core/location_parser.py

import re
import aiohttp
from urllib.parse import unquote
from typing import Optional, Dict, Union

# --- Logic and Algorithms ---

# 1. Coordinate Patterns - Most accurate method
# These patterns search for numeric values
COORD_PATTERNS = [
    r'@(-?\d+\.\d+),(-?\d+\.\d+)',              # Standard: @35.7,51.4
    r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',          # New Google: !3d35.7!4d51.4
    r'q=(-?\d+\.\d+),(-?\d+\.\d+)',              # Query param
]

# 2. Place Name Patterns - Smart Method
# Logic: Anything following /place/ or /search/ is considered a location name.
# Group 1 captures the extracted city name.
NAME_PATTERNS = [
    r'/place/([^/]+)',   # Matches: .../place/Tehran/... -> Extracts "Tehran"
    r'/search/([^/]+)',  # Matches: .../search/Milad+Tower/... -> Extracts "Milad+Tower"
]

# Forbidden words (if these appear after 'place', they are not city names)
IGNORE_NAMES = ["data", "wms", "api", "preview"]

async def parse_input(input_data: Union[str, object]) -> Optional[Dict]:
    """
    Analyzes input and returns a dictionary:
    {'type': 'coords', 'lat': 35.1, 'lon': 51.2}
    OR
    {'type': 'city', 'name': 'Tehran'}
    OR
    None (if nothing valid found)
    """
    
    # --- PHASE 1: Telegram Location Object ---
    if hasattr(input_data, 'lat') and hasattr(input_data, 'long'):
        return {
            'type': 'coords', 
            'lat': float(input_data.lat), 
            'lon': float(input_data.long)
        }

    # --- PHASE 2: Text/URL Processing ---
    if isinstance(input_data, str):
        text = input_data.strip()
        
        # A) If it is a URL (Link)
        if any(x in text.lower() for x in ["http", "google", "goo.gl", "maps"]):
            final_url = await _expand_url(text)
            if not final_url: 
                return None
            
            # Step 1: Try to find Coordinates (Priority A)
            for pattern in COORD_PATTERNS:
                match = re.search(pattern, final_url)
                if match:
                    return {
                        'type': 'coords', 
                        'lat': float(match.group(1)), 
                        'lon': float(match.group(2))
                    }
            
            # Step 2: Try to find Place Name (Priority B)
            for pattern in NAME_PATTERNS:
                match = re.search(pattern, final_url)
                if match:
                    # Clean the extracted name (remove %20, +, etc.)
                    raw_name = match.group(1)
                    clean_name = unquote(raw_name).replace('+', ' ')
                    
                    # Safety Check: Ensure it's not a system word
                    if clean_name.lower() not in IGNORE_NAMES:
                        return {
                            'type': 'city', 
                            'name': clean_name
                        }

        # B) If it is Raw Coordinates (e.g., "35.7, 51.4")
        else:
            return _parse_raw_coords(text)

    return None

async def _expand_url(url: str) -> Optional[str]:
    """
    Helper to open short URLs and get the real long URL.
    Spoofs User-Agent to act like a real browser.
    """
    if not url.startswith("http"): url = "https://" + url
    
    # Headers are crucial to prevent Google from blocking the bot
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0"
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(headers=headers, trust_env=True, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                return str(response.url)
    except:
        return None

def _parse_raw_coords(text: str) -> Optional[Dict]:
    try:
        parts = text.replace(' ', ',').split(',')
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            lat = float(parts[0])
            lon = float(parts[1])
            if -90 <= lat <= 90:
                return {'type': 'coords', 'lat': lat, 'lon': lon}
    except:
        pass
    return None