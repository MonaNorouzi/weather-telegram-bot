# handlers/message_handler.py

import re
from telethon import events, TelegramClient, Button
from core.location_parser import parse_input
from core.weather_api import get_weather, resolve_location_name


def register_handlers(client: TelegramClient):
    print("✅ [System] Loading Message Handlers...")

    @client.on(events.NewMessage)
    async def root_handler(event):
        """
        This simplified handler only responds to /start and normal requests.
        """
       
        from handlers.conversation_handler import ACTIVE_CONVERSATIONS
        
        
        user_id = event.sender_id
        text = event.text
        
        if text and text.lower() == '/start':
            # Buttons for all users
            buttons = [
                [Button.inline("⚙️ Manage Cities & Schedule", b"open_settings")],
                [Button.inline("🗑️ Clear All Caches", b"admin_clear_cache")]
            ]
            
            await event.reply(
                "👋 **Hello! Welcome to Weather Bot.**\n\n"
                "What would you like to do?",
                buttons=buttons
            )
            return

        
        if user_id in ACTIVE_CONVERSATIONS:
            return 

        await process_normal_request(event)


async def process_normal_request(event):
    """
    Standard logic: User sends input -> Bot sends weather.
    """
    user_input = event.message.geo if event.message.geo else event.message.text
    if not user_input or (isinstance(user_input, str) and user_input.startswith('/')):
        return 

    loading = await event.reply("⏳ Analyzing...")
    
    parsed = await parse_input(user_input)
  
    is_url_like = isinstance(user_input, str) and any(x in user_input.lower() for x in ["http", "google", "goo.gl", "maps"])

    if not parsed:
        if isinstance(user_input, str) and not is_url_like:
            parsed = {'type': 'city', 'name': user_input.strip()}
        else:
            pass
    
    if not parsed:
        await loading.edit("⛔️ Input not understood. Please send a location or city name.")
        return
        
    report = await get_weather(parsed)
    await loading.edit(report)