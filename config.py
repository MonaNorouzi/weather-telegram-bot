# config.py

import os
from dotenv import load_dotenv

# Load environment variables from the .env file
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

# Telethon requires API_ID to be an integer
try:
    API_ID = int(_get_env_variable("API_ID"))
except (ValueError, TypeError):
    raise ValueError("API_ID in .env must be an integer.")

API_HASH = _get_env_variable("API_HASH")
BOT_TOKEN = _get_env_variable("BOT_TOKEN")
WEATHER_API_KEY = _get_env_variable("OPENWEATHER_API_KEY")

# Base URL for OpenWeatherMap (Good practice to keep URLs in config too)
WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"