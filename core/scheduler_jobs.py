# core/scheduler_jobs.py
"""Scheduler job execution logic"""

import logging
from telethon import TelegramClient
from core.weather_api import get_weather


async def send_weather_job(client: TelegramClient, user_id: int, city_name: str, lat: float, lon: float):
    """Send weather message to user"""
    logging.info(f"🚀 EXECUTION: User {user_id} | City {city_name}")
    
    try:
        weather_data = {
            'type': 'city' if lat == 0 else 'coords',
            'name': city_name, 'lat': lat, 'lon': lon
        }
        report = await get_weather(weather_data)
        
        try:
            await client.send_message(user_id, f"🔔 **Daily Report:**\n\n{report}")
        except Exception:
            logging.warning(f"⚠️ Direct send failed for {user_id}, retrying...")
            try:
                user = await client.get_input_entity(user_id)
                await client.send_message(user, f"🔔 **Daily Report:**\n\n{report}")
            except Exception as e:
                logging.error(f"❌ Could not reach user {user_id}: {e}")
                return

        logging.info(f"✅ Message delivered to {user_id}")

    except Exception as e:
        logging.error(f"❌ JOB FAILED: {e}", exc_info=True)
