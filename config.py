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
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY") # Optional, but needed for /route

# Admin ID for system notifications (Startup alerts)
try:
    ADMIN_ID = int(_get_env_variable("ADMIN_ID"))
except (ValueError, TypeError):
    raise ValueError("ADMIN_ID in .env must be an integer.")

# Premium Users Configuration
PREMIUM_USER_IDS = set()
premium_ids_str = os.getenv("PREMIUM_USER_IDS", "")
if premium_ids_str:
    try:
        PREMIUM_USER_IDS = {int(uid.strip()) for uid in premium_ids_str.split(",") if uid.strip()}
    except ValueError:
        raise ValueError("PREMIUM_USER_IDS in .env must be comma-separated integers.")

# Base URL for OpenWeatherMap
WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# Proxy Configuration
PROXY_URL = os.getenv("PROXY_URL")

# PostgreSQL Configuration for Graph Routing
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "weather_bot_routing")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# Redis Configuration for Caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))

# OSRM Configuration for Routing
OSRM_URL = os.getenv("OSRM_URL", "http://localhost:5000")
OSRM_FALLBACK_PUBLIC = os.getenv("OSRM_FALLBACK_PUBLIC", "true").lower() == "true"

# H3 Geospatial Configuration
# Resolution 7 is the "Goldilocks zone" for weather routing:
# - Average hexagon edge: ~5.16 km
# - Area: ~25.18 km²
# - Excellent weather accuracy (weather uniform within 5km)
# - High cache reusability across routes
# - Memory efficient (~450K hexagons for Iran vs 15M for Resolution 8)
H3_RESOLUTION = int(os.getenv("H3_RESOLUTION", "7"))
H3_WEATHER_CACHE_TTL = int(os.getenv("H3_WEATHER_CACHE_TTL", "3600"))  # 60 minutes
PARALLEL_WEATHER_REQUESTS = int(os.getenv("PARALLEL_WEATHER_REQUESTS", "40"))  # Fixed connection pooling!

def get_redis_url():
    """Get Redis connection URL."""
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

def get_postgres_dsn():
    """Get PostgreSQL connection string."""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

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