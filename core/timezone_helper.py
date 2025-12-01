# core/timezone_helper.py

import logging
from timezonefinder import TimezoneFinder

# Initialize once to save memory
tf = TimezoneFinder()

def get_timezone_from_coords(lat: float, lon: float) -> str:
    """
    Determines the timezone string (e.g., 'Asia/Tehran', 'America/New_York')
    based on latitude and longitude.
    """
    try:
        # Default for purely manual entry or testing 0,0
        if lat == 0.0 and lon == 0.0:
            return "UTC"

        timezone_str = tf.timezone_at(lng=lon, lat=lat)
        
        if timezone_str:
            return timezone_str
        
        # Fallback if coordinates are in the middle of the ocean
        return "UTC"
        
    except Exception as e:
        logging.error(f"⚠️ Timezone lookup failed for {lat}, {lon}: {e}")
        return "UTC"