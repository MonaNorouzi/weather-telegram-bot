# config.py

import os
import urllib.parse
from dotenv import load_dotenv
import python_socks 
from python_socks import ProxyType

# Load environment variables
load_dotenv()

def _get_env_variable(var_name: str, required: bool = True) -> str:
    """
    Internal helper to fetch env variables and handle missing errors.
    """
    value = os.getenv(var_name)
    if required and not value:
        raise ValueError(f"CRITICAL ERROR: Environment variable '{var_name}' is missing in .env file.")
    return value

# --- Configuration Constants ---

try:
    API_ID = int(_get_env_variable("API_ID"))
except (ValueError, TypeError):
    raise ValueError("API_ID in .env must be an integer.")

API_HASH = _get_env_variable("API_HASH")
BOT_TOKEN = _get_env_variable("BOT_TOKEN")
WEATHER_API_KEY = _get_env_variable("OPENWEATHER_API_KEY")

# Admin ID for system notifications (Startup alerts)
try:
    ADMIN_ID = int(_get_env_variable("ADMIN_ID"))
except (ValueError, TypeError):
    raise ValueError("ADMIN_ID in .env must be an integer.")

# Base URL for OpenWeatherMap
WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Proxy Configuration
PROXY_URL = os.getenv("PROXY_URL")

def get_telethon_proxy_params():
    """
    Parses the PROXY_URL and returns a dictionary compatible with Telethon.
    Returns None if no proxy is set.
    """
    if not PROXY_URL:
        return None

    try:
        parsed = urllib.parse.urlparse(PROXY_URL)
        
        if 'socks5' in parsed.scheme:
            scheme = ProxyType.SOCKS5
        elif 'socks4' in parsed.scheme:
            scheme = ProxyType.SOCKS4
        else:
            scheme = ProxyType.HTTP
        
        return {
            'proxy_type': scheme,
            'addr': parsed.hostname,
            'port': parsed.port,
            'username': parsed.username,
            'password': parsed.password,
            'rdns': True 
        }
    except Exception as e:
        print(f"Warning: Failed to parse PROXY_URL: {e}")
        return None