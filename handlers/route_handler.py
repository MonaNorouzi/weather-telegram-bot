# handlers/route_handler.py
"""Handler for the Route Finder feature"""

from telethon import events, TelegramClient, Button
from core.route_service import route_service
import logging

# User sessions: {user_id: {"state": "ASK_ORIGIN"|"ASK_DEST", "origin": (lat,lon), ...}}
route_sessions = {}

async def start_route_wizard(client: TelegramClient, user_id: int):
    """Start the route finder wizard - works from both command and button"""
    if not route_service.api_key:
        await client.send_message(user_id, "⚠️ Route feature not configured (Missing OPENROUTE_API_KEY).")
        return

    route_sessions[user_id] = {"state": "ASK_ORIGIN"}
    await client.send_message(
        user_id,
        "🚗 **Route Finder**\n\n📍 Send me your **starting city** (where are you now?):\n\n_Example: Tehran_"
    )
    logging.info(f"🚗 Route wizard started for user {user_id}")

async def handle_route_input(event, client: TelegramClient):
    """Handle text inputs during route wizard"""
    user_id = event.sender_id
    text = event.message.text.strip()
    
    session = route_sessions.get(user_id)
    if not session:
        return False  # Not in route session

    logging.info(f"🚗 Route input from {user_id}: {text}")

    if session["state"] == "ASK_ORIGIN":
        coords = await route_service.get_coordinates(text)
        if not coords:
            await client.send_message(user_id, "❌ Could not find that city. Please try again.")
            return True  # Handled
        
        session["origin"] = coords
        session["origin_name"] = text
        session["state"] = "ASK_DEST"
        
        await client.send_message(
            user_id,
            f"✅ Start: **{text}**\n\n🎯 Now send me your **destination city** (where do you want to go?):\n\n_Example: Shiraz_"
        )
        return True

    elif session["state"] == "ASK_DEST":
        dest_coords = await route_service.get_coordinates(text)
        if not dest_coords:
            await client.send_message(user_id, "❌ Could not find that city. Please try again.")
            return True
        
        origin_coords = session["origin"]
        origin_name = session["origin_name"]
        dest_name = text
        
        # Clear session before long operation
        del route_sessions[user_id]
        
        msg = await client.send_message(user_id, "🗺️ Calculating route... please wait.")
        
        # Get route from API
        route_data = await route_service.get_route(origin_coords, dest_coords)
        if not route_data:
            await msg.edit("❌ Could not find a driving route between these cities.")
            return True
        
        await msg.edit("🔍 Finding cities along your route...")
        
        cities = await route_service.get_cities_along_route(route_data)
        if not cities:
            await msg.edit("❌ Found the route, but couldn't identify cities along it.")
            return True
        
        # Get route summary
        try:
            summary = route_data["features"][0]["properties"]["summary"]
            dist_km = round(summary.get("distance", 0) / 1000, 1)
            dur_hr = round(summary.get("duration", 0) / 3600, 1)
        except:
            dist_km, dur_hr = "?", "?"
        
        # Format final message
        lines = [
            f"🛣️ **Route: {origin_name} ➝ {dest_name}**",
            f"📏 Distance: `{dist_km} km`",
            f"⏱️ Duration: `~{dur_hr} hours`",
            "",
            "**📍 Cities along your route:**"
        ]
        
        for i, city in enumerate(cities):
            icon = "🏁" if city['type'] == 'End' else ("🚩" if city['type'] == 'Start' else "🔹")
            lines.append(f"{i+1}. {icon} **{city['name']}**")
        
        await msg.edit("\n".join(lines))
        return True

    return False

def register_route_handlers(client: TelegramClient):
    """Register route handlers"""
    
    @client.on(events.NewMessage(pattern='/route'))
    async def route_command(event):
        await start_route_wizard(client, event.sender_id)
    
    @client.on(events.NewMessage)
    async def route_text_handler(event):
        if event.sender_id in route_sessions:
            if event.message.text and not event.message.text.startswith('/'):
                handled = await handle_route_input(event, client)
                if handled:
                    raise events.StopPropagation
    
    logging.info("✅ Route handlers registered")
