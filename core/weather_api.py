# core/weather_api.py

import aiohttp
import config

async def get_weather(data: dict) -> str:
    """
    Fetches weather data. 
    Uses Reverse Geocoding to find the REAL City Name (e.g., 'Tehran' instead of neighborhood names).
    """
    
    timeout_settings = aiohttp.ClientTimeout(total=10)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout_settings, trust_env=True) as session:
            
            # --- STEP 1: Determine the Display Name (City Name) ---
            display_name = "Unknown Location"
            
            # If user provided coordinates, let's find the real City Name using Geo API
            if data['type'] == 'coords':
                try:
                    # Geo API URL (Reverse Geocoding)
                    geo_url = (
                        f"http://api.openweathermap.org/geo/1.0/reverse?"
                        f"lat={data['lat']}&lon={data['lon']}&"
                        f"limit=1&appid={config.WEATHER_API_KEY}"
                    )
                    
                    async with session.get(geo_url) as geo_response:
                        if geo_response.status == 200:
                            geo_data = await geo_response.json()
                            if geo_data and len(geo_data) > 0:
                                # Try to get English name (default) or Local name
                                display_name = geo_data[0]['name'] 
                                # Optional: Uncomment below to prefer Persian name if available
                                # display_name = geo_data[0]['local_names'].get('fa', geo_data[0]['name'])
                except Exception as e:
                    print(f"⚠️ Geo API Warning: {e}")
                    # If Geo API fails, we will use the name from Weather API later
                    display_name = None

            elif data['type'] == 'city':
                display_name = data['name']

            # --- STEP 2: Fetch Weather Data ---
            if data['type'] == 'coords':
                url = f"{config.WEATHER_BASE_URL}?lat={data['lat']}&lon={data['lon']}&appid={config.WEATHER_API_KEY}&lang=fa"
            elif data['type'] == 'city':
                url = f"{config.WEATHER_BASE_URL}?q={data['name']}&appid={config.WEATHER_API_KEY}&lang=fa"
            
            async with session.get(url) as response:
                if response.status != 200:
                    return "⛔️ Error: Could not find weather for this location."

                result = await response.json()
                
                # 3. Process Data
                temp = result["main"]["temp"] - 273.15
                desc = result["weather"][0]["description"]
                humidity = result["main"]["humidity"]
                
                # Final Name Logic: 
                # If we found a name in Step 1, use it. Otherwise use what API returned.
                if not display_name:
                    display_name = result.get("name", "Unknown")

                return (
                    f"🌍 **Weather Report: {display_name}**\n"
                    f"-----------------------------------\n"
                    f"🌡 Temp: {temp:.1f}°C\n"
                    f"☁️ Condition: {desc}\n"
                    f"💧 Humidity: {humidity}%\n"
                )

    except Exception as e:
        print(f"❌ API Error: {e}")
        return "⛔️ Network Error: Unable to connect to weather service."