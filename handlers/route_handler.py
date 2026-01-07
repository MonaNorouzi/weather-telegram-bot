# handlers/route_handler.py
"""Route Finder with Nominatim geocoding - reliable 400+ places"""

from telethon import events, TelegramClient
from core.osrm_service import osrm_service
from core.overpass_service import overpass_service
from core.openmeteo_service import openmeteo_service
from core.route_data_saver import save_route_json, get_coldest_warmest
from datetime import datetime, timedelta
import logging
import re
import math

route_sessions = {}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

async def start_route_wizard(client: TelegramClient, user_id: int):
    route_sessions[user_id] = {"state": "ASK_ORIGIN"}
    await client.send_message(user_id, "🚗 **Route Finder**\n📍 Send **starting city**:")

async def handle_route_input(event, client: TelegramClient):
    user_id, text = event.sender_id, event.message.text.strip()
    session = route_sessions.get(user_id)
    if not session:
        return False

    state = session["state"]

    if state == "ASK_ORIGIN":
        coords = await osrm_service.get_coordinates(text)
        if not coords:
            await client.send_message(user_id, "❌ City not found.")
            return True
        session.update({"origin": coords, "origin_name": text, "state": "ASK_DEST"})
        await client.send_message(user_id, f"✅ Start: **{text}**\n🎯 Send **destination**:")
        return True

    elif state == "ASK_DEST":
        coords = await osrm_service.get_coordinates(text)
        if not coords:
            await client.send_message(user_id, "❌ City not found.")
            return True
        session.update({"dest": coords, "dest_name": text, "state": "ASK_TIME"})
        await client.send_message(user_id, f"✅ Dest: **{text}**\n⏰ Departure time (HH:MM):")
        return True
    elif state == "ASK_TIME":
        match = re.match(r"^([01]?[0-9]|2[0-3]):([0-5]?[0-9])$", text)
        if not match:
            await client.send_message(user_id, "❌ Invalid time format. Use HH:MM.")
            return True
        session.update({"hour": int(match.group(1)), "minute": int(match.group(2)), "state": "ASK_TRAFFIC"})
        await client.send_message(user_id, "✅ Time: **{}**\n🚗 Fast route (1) or with traffic (2)?".format(text))
        return True

    elif state == "ASK_TRAFFIC":
        if text not in ["1", "2"]:
            await client.send_message(user_id, "❌ Reply 1 or 2")
            return True
        await process_route_fast(client, user_id, session, text == "2")
        return True

    return False

async def process_route_fast(client, user_id, session, with_traffic: bool):
    del route_sessions[user_id]
    msg = await client.send_message(user_id, "🗺️ Getting route...")

    # Get route WITH duration annotations for accurate timing
    route = await osrm_service.get_route_with_annotations(session["origin"], session["dest"])
    if not route:
        return await msg.edit("❌ No route found.")

    coords = route["coordinates"]
    durations = route.get("durations", [])
    total_dist = route["distance"] / 1000
    total_dur = route["duration"]
    if with_traffic:
        total_dur *= 1.3

    logging.info(f"Route: {len(coords)} coordinates, {total_dist:.1f}km, {total_dur/3600:.1f}h")
    
    # Performance tracking
    import time
    start_time = time.time()
    
    # Use Overpass batch strategy to get ALL places
    await msg.edit(f"🗺️ Finding places along route...")
    logging.info(f"Starting Overpass batch processing with 5km radius")
    
    places = await overpass_service.get_places_along_route(coords)
    overpass_time = time.time() - start_time
    logging.info(f"Overpass returned {len(places)} unique places in {overpass_time:.1f}s")
    
    if not places:
        return await msg.edit("❌ No places found.")

    await msg.edit(f"🌤️ Getting weather for {len(places)} places...")

    now = datetime.now()
    depart = now.replace(hour=session["hour"], minute=session["minute"], second=0)
    if depart < now:
        depart += timedelta(days=1)

    start_lat, start_lon = session["origin"]
    
    # Calculate accumulated time from duration annotations
    from core.route_sampler import calculate_accumulated_durations
    
    if durations:
        accumulated_time = calculate_accumulated_durations(durations)
    else:
        # Fallback: linear estimation if annotations not available
        accumulated_time = [0.0] * len(coords)
    
    # Create sparse route for faster nearest-point lookup
    route_sparse = coords[::10]  # Every 10th point
    times_sparse = accumulated_time[::10] if len(accumulated_time) > 10 else accumulated_time
    
    # Map each place to nearest route point for accurate arrival time
    logging.info(f"Mapping {len(places)} places to route timeline...")
    
    places_with_times = []
    for p in places:
        # Find nearest point on route
        min_dist_sq = float('inf')
        closest_idx = 0
        
        for i, (r_lon, r_lat) in enumerate(route_sparse):
            # Squared distance (faster, no sqrt needed for comparison)
            dist_sq = (r_lat - p["lat"])**2 + (r_lon - p["lon"])**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_idx = i
        
        # Get arrival time from route timeline
        arrival_secs = times_sparse[closest_idx] if closest_idx < len(times_sparse) else times_sparse[-1]
        if with_traffic:
            arrival_secs *= 1.3
        
        arrival_dt = depart + timedelta(seconds=arrival_secs)
        places_with_times.append((p["lat"], p["lon"], arrival_dt, arrival_secs, p))
    
    # Sort by arrival time
    places_with_times.sort(key=lambda x: x[3])
    
    # Batch weather fetch
    locations_for_weather = [(lat, lon, dt) for lat, lon, dt, _, _ in places_with_times]
    
    weather_start = time.time()
    weather_results = await openmeteo_service.get_batch_forecasts(locations_for_weather)
    weather_time = time.time() - weather_start
    logging.info(f"Weather fetching completed in {weather_time:.1f}s for {len(places_with_times)} places")

    # Build schedule with weather data
    schedule = []
    for lat, lon, arrival_dt, arrival_sec, p in places_with_times:
        weather = weather_results.get((lat, lon))
        
        schedule.append({
            "place": p["name"],
            "type": p["type"],
            "coords": {"lat": p["lat"], "lon": p["lon"]},
            "arrival_seconds": arrival_sec,
            "temperature_celsius": weather.get("temp") if weather else None,
            "arrival_time": arrival_dt.strftime("%H:%M")
        })

    total_time = time.time() - start_time
    logging.info(f"Total processing time: {total_time:.1f}s (Overpass: {overpass_time:.1f}s, Weather: {weather_time:.1f}s)")



    start_str = f"{session['hour']:02d}:{session['minute']:02d}"
    json_path = save_route_json(user_id, session["origin_name"], session["dest_name"],
                                 start_str, schedule, with_traffic)
    logging.info(f"📁 Saved: {json_path} ({len(schedule)} places)")

    coldest, warmest = get_coldest_warmest(schedule)

    major = [s for s in schedule if s["type"] in ["city", "town"]][:8] or schedule[:8]

    lines = [
        f"🛣️ **{session['origin_name']} ➝ {session['dest_name']}**",
        f"📏 `{total_dist:.0f}km` ⏱️ `~{total_dur/3600:.1f}h`",
        f"{'🚦 +30% traffic' if with_traffic else '⚡ Ideal time'}",
        "", "**📍 Cities:**"
    ]

    for i, s in enumerate(major):
        icon = "🏁" if i == len(major)-1 else ("🚩" if i == 0 else "🔹")
        temp = f"{s['temperature_celsius']}°C" if s['temperature_celsius'] else ""
        lines.append(f"{i+1}. {icon} **{s['place']}** ({s['arrival_time']}) {temp}")

    lines.append("")
    if coldest and coldest.get("temperature_celsius") is not None:
        lines.append(f"❄️ Coldest: {coldest['place']} ({coldest['temperature_celsius']}°C)")
    if warmest and warmest.get("temperature_celsius") is not None:
        lines.append(f"🔥 Warmest: {warmest['place']} ({warmest['temperature_celsius']}°C)")
    lines.append(f"\n_📁 {len(schedule)} places saved_")

    await msg.edit("\n".join(lines))

def register_route_handlers(client: TelegramClient):
    @client.on(events.NewMessage(pattern='/route'))
    async def _(event):
        await start_route_wizard(client, event.sender_id)

    @client.on(events.NewMessage)
    async def _(event):
        if event.sender_id in route_sessions:
            if event.message.text and not event.message.text.startswith('/'):
                if await handle_route_input(event, client):
                    raise events.StopPropagation

    logging.info("✅ Route handlers registered (Nominatim)")
