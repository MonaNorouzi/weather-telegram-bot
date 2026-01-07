# handlers/graph_route_handler.py
"""Route Handler with Graph Database Integration.

This is an enhanced version of route_handler.py that uses the graph database
for intelligent caching and faster route lookups.
"""

from telethon import events, TelegramClient
from core.graph_route_service import graph_route_service
from core.graph_database import graph_db
from core.osrm_service import osrm_service
from core.overpass_service import overpass_service
from core.openmeteo_service import openmeteo_service
from core.route_data_saver import save_route_json, get_coldest_warmest
from datetime import datetime, timedelta
import logging
import re
import math

route_sessions = {}

async def start_route_wizard(client: TelegramClient, user_id: int):
    route_sessions[user_id] = {"state": "ASK_ORIGIN"}
    await client.send_message(user_id, "🚗 **Route Finder (Graph-Powered)**\n📍 Send **starting city**:")

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
        await process_route_graph(client, user_id, session, text == "2")
        return True

    return False

async def process_route_graph(client, user_id, session, with_traffic: bool):
    """Process route using graph database with fallback to OSRM."""
    del route_sessions[user_id]
    msg = await client.send_message(user_id, "🗺️ Checking graph database...")

    # Prepare start time
    now = datetime.now()
    depart = now.replace(hour=session["hour"], minute=session["minute"], second=0)
    if depart < now:
        depart += timedelta(days=1)

    try:
        # Use graph route service
        route_result = await graph_route_service.get_route(
            origin_name=session["origin_name"],
            origin_coords=session["origin"],
            dest_name=session["dest_name"],
            dest_coords=session["dest"],
            start_time=depart,
            with_traffic=with_traffic
        )
        
        if not route_result:
            return await msg.edit("❌ Failed to find route. Please try again.")
        
        # Update message based on cache hit/miss
        cache_status = "💎 Cache Hit" if route_result.cache_hit else "🌍 Cache Miss (External API)"
        await msg.edit(f"{cache_status}\n🔍 Finding places along route...")
        
        # Get coordinates from geometries
        coordinates = [[lon, lat] for lat, lon in route_result.geometries]
        
        # Try to get places from cache first
        from core.route_places_cache import route_places_cache
        
        # Extract place IDs from session
        source_place_id = None
        target_place_id = None
        
        # We need to get place IDs - let's fetch them
        from core.graph_builder import graph_builder
        source_place_id = await graph_builder.get_or_create_place(
            session["origin_name"], 'city', session["origin"]
        )
        target_place_id = await graph_builder.get_or_create_place(
            session["dest_name"], 'city', session["dest"]
        )
        
        # Check cache
        cached_places = await route_places_cache.get_cached_places(
            source_place_id, target_place_id
        )
        
        if cached_places:
            # Use cached places
            places = cached_places
            logging.info(f"✅ Used {len(places)} places from cache")
        else:
            # Find places using Overpass service
            logging.info(f"Finding places along route ({len(coordinates)} points)")
            places = await overpass_service.get_places_along_route(coordinates)
            
            if not places:
                logging.warning("No places found along route")
                places = []
            else:
                # Store all discovered places in the database
                from core.places_manager import places_manager
                await places_manager.bulk_ensure_places(places)
                
                # Cache the places for next time
                await route_places_cache.cache_places(
                    source_place_id, target_place_id, places
                )
        
        await msg.edit(f"{cache_status}\n🌤️ Getting weather for {len(places)} places...")
        
        # Calculate arrival times for places
        from core.route_sampler import calculate_accumulated_durations
        
        # Build sparse route for mapping
        route_sparse = coordinates[::10] if len(coordinates) > 10 else coordinates
        
        # For timing, use linear interpolation based on distance
        total_distance = route_result.distance_km * 1000
        total_duration = route_result.duration_hours * 3600
        
        accumulated_time = [0]
        curr_dist = 0
        
        for i in range(1, len(route_sparse)):
            lat1, lon1 = route_sparse[i-1][1], route_sparse[i-1][0]
            lat2, lon2 = route_sparse[i][1], route_sparse[i][0]
            
            # Haversine distance
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi, dlam = math.radians(lat2-lat1), math.radians(lon2-lon1)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
            dist = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            curr_dist += dist
            time_at_point = (curr_dist / total_distance) * total_duration if total_distance > 0 else 0
            accumulated_time.append(time_at_point)
        
        times_sparse = accumulated_time
        
        # Map places to route timeline
        places_with_times = []
        for p in places:
            min_dist_sq = float('inf')
            closest_idx = 0
            
            for i, coord in enumerate(route_sparse):
                r_lat, r_lon = coord[1], coord[0]
                dist_sq = (r_lat - p["lat"])**2 + (r_lon - p["lon"])**2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest_idx = i
            
            arrival_secs = times_sparse[closest_idx] if closest_idx < len(times_sparse) else times_sparse[-1]
            arrival_dt = depart + timedelta(seconds=arrival_secs)
            places_with_times.append((p["lat"], p["lon"], arrival_dt, arrival_secs, p))
        
        places_with_times.sort(key=lambda x: x[3])
        
        # Batch weather fetch
        locations_for_weather = [(lat, lon, dt) for lat, lon, dt, _, _ in places_with_times]
        weather_results = await openmeteo_service.get_batch_forecasts(locations_for_weather)
        
        # Build schedule
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
        
        # Save to JSON
        start_str = f"{session['hour']:02d}:{session['minute']:02d}"
        json_path = save_route_json(user_id, session["origin_name"], session["dest_name"],
                                     start_str, schedule, with_traffic)
        logging.info(f"📁 Saved: {json_path} ({len(schedule)} places)")
        
        # Get temperature extremes
        coldest, warmest = get_coldest_warmest(schedule)
        
        # Select major cities to display
        major = [s for s in schedule if s["type"] in ["city", "town"]][:8] or schedule[:8]
        
        # Build message
        lines = [
            f"🛣️ **{session['origin_name']} ➝ {session['dest_name']}**",
            f"📏 `{route_result.distance_km:.0f}km` ⏱️ `~{route_result.duration_hours:.1f}h`",
            f"{'🚦 +30% traffic' if with_traffic else '⚡ Ideal time'}",
            f"🔄 Graph: `{cache_status}`",
            f"☁️ {route_result.weather_summary}",
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
        
    except Exception as e:
        logging.error(f"Error in graph route handler: {e}")
        import traceback
        traceback.print_exc()
        await msg.edit(f"❌ Error processing route: {str(e)}")

def register_graph_route_handlers(client: TelegramClient):
    """Register graph-powered route handlers."""
    @client.on(events.NewMessage(pattern='/graph_route'))
    async def _(event):
        await start_route_wizard(client, event.sender_id)

    @client.on(events.NewMessage)
    async def _(event):
        if event.sender_id in route_sessions:
            if event.message.text and not event.message.text.startswith('/'):
                if await handle_route_input(event, client):
                    raise events.StopPropagation

    logging.info("✅ Graph route handlers registered")
