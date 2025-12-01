# handlers/conversation_handler.py

import asyncio
import logging
from telethon import TelegramClient, Button
from core.database_manager import db_manager
from core.location_parser import parse_input
from core.weather_api import resolve_location_name, get_weather, get_coords_from_city
from core.validators import validate_and_fix_time
from core.timezone_helper import get_timezone_from_coords

ACTIVE_CONVERSATIONS = set()

async def add_city_wizard(event, client: TelegramClient):
    user_id = event.sender_id
    if user_id in ACTIVE_CONVERSATIONS:
        return
    ACTIVE_CONVERSATIONS.add(user_id)
    
    try:
        async with client.conversation(user_id, timeout=300) as conv:
            msg = await conv.send_message(
                "📍 **Send Location or City Name:**\n(I will auto-detect your timezone)",
                buttons=[Button.inline("❌ Cancel", b"cancel_conv")]
            )
            
            parsed_data = None
            final_city_name = None
            lat = 0.0
            lon = 0.0
            
            # --- Step 1: Get Location ---
            while not parsed_data:
                response = await conv.get_response()
                if response.text == "/cancel": return
                
                user_input = response.geo if response.geo else response.text
                if not user_input: continue
                
                parsed = await parse_input(user_input)
                if not parsed and isinstance(user_input, str) and "http" not in user_input:
                    parsed = {'type': 'city', 'name': user_input.strip()}
                
                if parsed and "⛔️" not in await get_weather(parsed):
                    parsed_data = parsed
                else:
                    await conv.send_message("⛔️ Location not found. Please try again.")

            # --- Step 2: Resolve Precise Data ---
            if parsed_data['type'] == 'coords':
                lat = parsed_data['lat']
                lon = parsed_data['lon']
                final_city_name = await resolve_location_name(lat, lon)
            elif parsed_data['type'] == 'city':
                final_city_name = parsed_data['name'].title()
                found_lat, found_lon = await get_coords_from_city(parsed_data['name'])
                if found_lat:
                    lat, lon = found_lat, found_lon

            detected_timezone = get_timezone_from_coords(lat, lon)
            
            await conv.send_message(
                f"✅ Location: **{final_city_name}**\n"
                f"🌍 Timezone: **{detected_timezone}**\n\n"
                f"⏰ **Enter time in YOUR local time (HH:MM):**"
            )
            
            # --- Step 3: Get Time ---
            valid_time = None
            while not valid_time:
                response = await conv.get_response()
                if response.text == "/cancel": return
                valid_time = validate_and_fix_time(response.text)
                if not valid_time: 
                    await conv.send_message("⛔️ Invalid format. Use HH:MM (e.g. 08:30).")

            # --- Step 4: Save & Schedule ---
            sub_id = await db_manager.add_subscription(
                user_id, final_city_name, lat, lon, valid_time, detected_timezone
            )
            
            if hasattr(client, 'weather_scheduler'):
                await client.weather_scheduler.add_new_subscription(
                    sub_id, user_id, final_city_name, lat, lon, valid_time, detected_timezone
                )
                logging.info(f"✅ Job {sub_id} injected into active scheduler.")
            else:
                logging.error("❌ Scheduler not found attached to client!")
            
            await conv.send_message(
                f"✅ **Scheduled!**\n"
                f"I will message you daily at **{valid_time}** ({detected_timezone} time)."
            )

    except Exception as e:
        logging.error(f"Wizard Error: {e}")
        await client.send_message(user_id, "❌ An error occurred.")
    finally:
        ACTIVE_CONVERSATIONS.discard(user_id)