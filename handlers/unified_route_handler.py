# handlers/unified_route_handler.py
"""Unified Smart Route Handler - Automatically uses Graph DB or OSRM fallback.

This handler intelligently:
1. Checks graph database first (fast cache hit)
2. Falls back to OSRM if route not in graph
3. Shows only major cities (city, town) with temperatures
4. Displays hottest and coldest points
5. Logs performance metrics
"""

from telethon import events, TelegramClient
from core.graph_route_service import graph_route_service
from core.osrm_service import osrm_service
from core.overpass_service import overpass_service
from core.openmeteo_service import openmeteo_service
from core.route_data_saver import save_route_json, get_coldest_warmest
from core.redis_route_cache import redis_route_cache  # Redis cache (50-200x faster!)
from core.redis_weather_cache import redis_weather_cache  # Redis weather (100x faster + singleflight!)
from core.places_manager import places_manager
from core.graph_builder import graph_builder
from core.city_normalizer import city_normalizer
from datetime import datetime, timedelta
import logging
import re
import math
import time

route_sessions = {}

async def link_intermediate_places(places: list, route_nodes: list):
    """Link intermediate places found by Overpass to nearest route nodes.
    
    This creates hubs for cities like Semnan, Damghan, etc. that are along
    the route, enabling graph reuse for future queries.
    
    Args:
        places: List of place dicts from Overpass  
        route_nodes: List of node IDs on this route
    """
    if not places or not route_nodes:
        return
    
    linked_count = 0
    
    for place in places:
        try:
            # Get or create place in database
            place_id = await places_manager.get_or_create_place(
                name=place['name'],
                place_type=place.get('type', 'town'),
                coords=(place['lat'], place['lon'])
            )
            
            # Link to nearest node
            linked_node = await graph_builder.link_place_to_nearest_node(
                place_id=place_id,
                place_coords=(place['lat'], place['lon']),
                candidate_nodes=route_nodes,
                max_distance_km=5.0
            )
            
            if linked_node:
                linked_count += 1
                
        except Exception as e:
            logging.error(f"Error linking place {place.get('name')}: {e}")
    
    if linked_count > 0:
        logging.info(f"✅ Created {linked_count} new hubs from intermediate places")


async def start_smart_route_wizard(client: TelegramClient, user_id: int):
    """Start the smart route finder wizard."""
    route_sessions[user_id] = {"state": "ASK_ORIGIN"}
    await client.send_message(
        user_id,
        "🚗 **Smart Route Finder**\n"
        "🔍 Automatically checks cache for faster results\n"
        "📍 Enter **origin city**:"
    )

async def handle_smart_route_input(event, client: TelegramClient):
    """Handle user input for smart route finder."""
    user_id, text = event.sender_id, event.message.text.strip()
    session = route_sessions.get(user_id)
    if not session:
        return False

    state = session["state"]

    if state == "ASK_ORIGIN":
        coords = await osrm_service.get_coordinates(text)
        if not coords:
            await client.send_message(user_id, "❌ City not found. Try again.")
            return True
        # Store both original and normalized names
        normalized = city_normalizer.normalize(text)
        session.update({
            "origin": coords,
            "origin_name": text,  # Original for display
            "origin_normalized": normalized,  # English for cache
            "state": "ASK_DEST"
        })
        await client.send_message(user_id, f"✅ Origin: **{text}**\n🎯 Enter **destination city**:")
        return True

    elif state == "ASK_DEST":
        coords = await osrm_service.get_coordinates(text)
        if not coords:
            await client.send_message(user_id, "❌ City not found. Try again.")
            return True
        # Store both original and normalized names
        normalized = city_normalizer.normalize(text)
        session.update({
            "dest": coords,
            "dest_name": text,  # Original for display  
            "dest_normalized": normalized,  # English for cache
            "state": "ASK_TIME"
        })
        await client.send_message(user_id, f"✅ Destination: **{text}**\n⏰ Departure time (HH:MM):")
        return True
    
    elif state == "ASK_TIME":
        match = re.match(r"^([01]?[0-9]|2[0-3]):([0-5]?[0-9])$", text)
        if not match:
            await client.send_message(user_id, "❌ Invalid time format. Use HH:MM (e.g., 08:30)")
            return True
        session.update({"hour": int(match.group(1)), "minute": int(match.group(2)), "state": "ASK_TRAFFIC"})
        await client.send_message(user_id, "✅ Time: **{}**\n🚗 Ideal conditions (1) or With traffic (2)?".format(text))
        return True

    elif state == "ASK_TRAFFIC":
        if text not in ["1", "2"]:
            await client.send_message(user_id, "❌ Please reply with 1 or 2")
            return True
        await process_smart_route(client, user_id, session, text == "2")
        return True

    return False

async def process_smart_route(client, user_id, session, with_traffic: bool):
    """Process route using smart graph-first approach with detailed metrics."""
    del route_sessions[user_id]
    
    # Start total timer
    total_start = time.time()
    
    msg = await client.send_message(user_id, "🔍 Finding best route...")

    # Prepare start time
    now = datetime.now()
    depart = now.replace(hour=session["hour"], minute=session["minute"], second=0)
    if depart < now:
        depart += timedelta(days=1)

    try:
        # === PHASE 1: Graph Routing ===
        routing_start = time.time()
        await msg.edit("🗺️ Checking route database...")
        
        route_result = await graph_route_service.get_route(
            origin_name=session["origin_name"],
            origin_coords=session["origin"],
            dest_name=session["dest_name"],
            dest_coords=session["dest"],
            start_time=depart,
            with_traffic=with_traffic
        )
        
        # Note: get_route includes weather overlay, so this is total routing + weather for nodes
        total_routing_time = time.time() - routing_start
        logging.info(f"⏱️ Graph routing + node weather: {total_routing_time:.2f}s")
        
        if not route_result:
            return await msg.edit("❌ Route not found. Please try different cities.")
        
        # Cache status
        cache_status = "💎 Cached Route" if route_result.cache_hit else "🌍 New Route"
        
        # === PHASE 2: Places Discovery ===
        places_start = time.time()
        await msg.edit(f"{cache_status}\n🔍 Finding major cities...")
        
        # Get place IDs
        source_place_id = await graph_builder.get_or_create_place(
            session["origin_name"], 'city', session["origin"]
        )
        target_place_id = await graph_builder.get_or_create_place(
            session["dest_name"], 'city', session["dest"]
        )
        
        # Check Redis cache (50-200x faster than PostgreSQL!)
        cached_places = await redis_route_cache.get_cached_places(
            source_place_id, target_place_id
        )
        
        if cached_places:
            places = cached_places
            logging.info(f"✅ Used {len(places)} places from cache")
        else:
            # Fetch from Overpass
            coordinates = [[lon, lat] for lat, lon in route_result.geometries]
            places = await overpass_service.get_places_along_route(coordinates)
            
            if places:
                # Store in database
                await places_manager.bulk_ensure_places(places)
                
                # Link places to route nodes (create hubs!)
                if hasattr(route_result, 'nodes') and route_result.nodes:
                    await link_intermediate_places(places, route_result.nodes)
                
                # Cache in Redis for next time (with PostgreSQL fallback)
                await redis_route_cache.cache_places(
                    source_place_id, target_place_id, places
                )
        
        places_time = time.time() - places_start
        logging.info(f"⏱️ Places discovery: {places_time:.2f}s")

        
        # === PHASE 3: Extract Weather from H3 Segments (OPTIMIZED!) ===
        weather_start = time.time()
        await msg.edit(f"{cache_status}\n🌤️ Processing weather data...")
        
        # Import h3 for hexagon operations
        import h3
        
        # Create H3 weather lookup map from route segments
        h3_weather_map = {}
        for segment in route_result.weather_segments:
            if 'h3_index' in segment and 'weather' in segment:
                h3_weather_map[segment['h3_index']] = segment['weather']
        
        logging.info(f"💎 H3 weather map: {len(h3_weather_map)} cells available")
        
        # Calculate total duration for arrival time estimation
        total_duration = route_result.duration_hours * 3600
        
        # Match places to H3 cells (OPTIMIZED with wider search!)
        all_places_with_weather = []
        
        for p in places:
            # Find closest point on route for timing
            min_dist_sq = float('inf')
            closest_idx = 0
            
            for i, (lat, lon) in enumerate(route_result.geometries):
                dist_sq = (lat - p["lat"])**2 + (lon - p["lon"])**2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    closest_idx = i
            
            # Estimate arrival time (linear interpolation)
            progress_ratio = closest_idx / len(route_result.geometries) if route_result.geometries else 0
            arrival_secs = progress_ratio * total_duration
            arrival_dt = depart + timedelta(seconds=arrival_secs)
            
            # Get H3 cell for this place (Resolution 7)
            place_h3 = h3.latlng_to_cell(p["lat"], p["lon"], 7)
            
            # Look up weather in H3 map (instant lookup!)
            weather_data = h3_weather_map.get(place_h3)
            
            # If not found in exact cell, check neighbors (expanded to 2 rings for better coverage!)
            if not weather_data:
                for ring in range(1, 3):  # Check rings 1 and 2
                    neighbors = h3.grid_ring(place_h3, ring)
                    for neighbor in neighbors:
                        if neighbor in h3_weather_map:
                            weather_data = h3_weather_map[neighbor]
                            break
                    if weather_data:
                        break
            
            # Extract temperature and icon from H3 weather data
            temp = None
            icon = ''
            if weather_data:
                temp = weather_data.get('temperature')
                
                # Map weather code to emoji icon
                weather_code = weather_data.get('weathercode', 0)  # Fixed: was 'weather_code'
                if weather_code == 0:
                    icon = '☀️'
                elif weather_code in [1, 2, 3]:
                    icon = '☁️'
                elif weather_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                    icon = '🌧️'
                elif weather_code in [71, 73, 75, 77, 85, 86]:
                    icon = '❄️'
                elif weather_code in [95, 96, 99]:
                    icon = '⛈️'
                elif weather_code in [45, 48]:
                    icon = '🌫️'
                else:
                    icon = '🌤️'
            
            all_places_with_weather.append({
                'place': p,
                'arrival_time': arrival_dt,
                'arrival_secs': arrival_secs,
                'is_major': p.get('type') in ['city', 'town'],
                'temp': temp,
                'icon': icon
            })
        
        # === PHASE 3.5: Batch API Fallback for Major Cities (OPTIMIZED!) ===
        # Only fetch weather for major cities (type='city') that still have no temperature
        major_cities_missing = [p for p in all_places_with_weather 
                               if p['place'].get('type') == 'city' and p['temp'] is None]
        
        if major_cities_missing:
            logging.info(f"🌐 Batch fetching weather for {len(major_cities_missing)} major cities...")
            
            # Prepare locations for batch fetch (MUCH FASTER than individual calls!)
            locations_with_times = [
                (p['place']['lat'], p['place']['lon'], p['arrival_time'])
                for p in major_cities_missing
            ]
            
            # Use batch API - fetches all in one call!
            weather_results = await openmeteo_service.get_batch_forecasts(locations_with_times)
            
            # Map results back to places
            successful = 0
            for p in major_cities_missing:
                key = (p['place']['lat'], p['place']['lon'])
                weather = weather_results.get(key)
                if weather:
                    p['temp'] = weather.get('temp')
                    # Get icon from weathercode
                    code = weather.get('weathercode', 0)
                    if code == 0:
                        p['icon'] = '☀️'
                    elif code in [1, 2, 3]:
                        p['icon'] = '☁️'
                    elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                        p['icon'] = '🌧️'
                    elif code in [71, 73, 75, 77, 85, 86]:
                        p['icon'] = '❄️'
                    elif code in [95, 96, 99]:
                        p['icon'] = '⛈️'
                    elif code in [45, 48]:
                        p['icon'] = '🌫️'
                    else:
                        p['icon'] = '🌤️'
                    successful += 1
            
            logging.info(f"✅ Batch API: {successful}/{len(major_cities_missing)} fetched successfully")
        
        # Count successful temperature lookups
        successful_temps = sum(1 for p in all_places_with_weather if p['temp'] is not None)
        
        weather_time = time.time() - weather_start
        logging.info(f"⏱️ H3 weather mapping: {weather_time:.2f}s ({successful_temps}/{len(all_places_with_weather)} locations got temp)")

        
        # === PHASE 4: Find Temperature Extremes (from ALL places) ===
        temps_with_names = [(p['temp'], p['place']['name'], p['place'].get('type', '')) 
                           for p in all_places_with_weather if p['temp'] is not None]
        
        if temps_with_names:
            coldest_temp, coldest_city, coldest_type = min(temps_with_names, key=lambda x: x[0])
            hottest_temp, hottest_city, hottest_type = max(temps_with_names, key=lambda x: x[0])
        else:
            coldest_temp = coldest_city = coldest_type = None
            hottest_temp = hottest_city = hottest_type = None
        
        # === PHASE 5: Filter ONLY Real Major Cities for Display ===
        # Only show type='city' (not town, not village, not suburb)
        real_major_cities = [p for p in all_places_with_weather if p['place'].get('type') == 'city']
        
        # Sort by arrival time (distance along route)
        real_major_cities.sort(key=lambda x: x['arrival_secs'])
        
        logging.info(f"📊 Displaying {len(real_major_cities)} major cities (type='city') from {len(places)} total places")
        
        # === PHASE 6: Build Response ===
        
        # Build message
        total_time = time.time() - total_start
        
        lines = [
            f"🛣️ **{session['origin_name']} ➝ {session['dest_name']}**",
            f"📏 Distance: `{route_result.distance_km:.0f} km` ⏱️ Duration: `~{route_result.duration_hours:.1f} h`",
            f"{'🚦 With traffic (+30%)' if with_traffic else '⚡ Ideal conditions'}",
            f"🔄 Status: {cache_status}",
            f"☁️ {route_result.weather_summary}",
            f"📍 **{len(places)} locations** found along route",
            "",
            "**🏙️ Major Cities:**"
        ]
        
        # Show major cities (limit to 10)
        cities_to_show = real_major_cities[:10]
        
        if not cities_to_show:
            lines.append("_No major cities on this route_")
        else:
            for i, p in enumerate(cities_to_show):
                icon = "🏁" if i == len(cities_to_show)-1 else ("🚩" if i == 0 else "🔹")
                # Always show temp if available
                if p['temp'] is not None:
                    temp_str = f"{p['temp']}°C {p['icon']}"
                else:
                    temp_str = "N/A"
                time_str = p['arrival_time'].strftime("%H:%M")
                lines.append(f"{i+1}. {icon} **{p['place']['name']}** (ETA: {time_str}) {temp_str}")
        
        lines.append("")
        
        # Temperature extremes (from ALL places)
        if coldest_temp is not None:
            lines.append(f"❄️ Coldest: **{coldest_city}** ({coldest_type}) - {coldest_temp}°C")
        if hottest_temp is not None:
            lines.append(f"🔥 Hottest: **{hottest_city}** ({hottest_type}) - {hottest_temp}°C")
        
        # Performance metrics - Complete breakdown of all phases
        lines.append("")
        h3_cache_info = ""
        if route_result.h3_stats:
            hits = route_result.h3_stats.get('cache_hits', 0)
            total = route_result.h3_stats.get('total_segments', 0)
            if total > 0:
                h3_cache_info = f" | H3: {hits}/{total} cached"
        
        # Calculate overhead (message building, filtering, temperature extremes, etc.)
        tracked_time = total_routing_time + places_time + weather_time
        overhead_time = total_time - tracked_time
        
        # Show complete breakdown with overhead
        lines.append(f"⏱️ **Performance Breakdown:**")
        lines.append(f"├─ Routing + H3 Weather: {total_routing_time:.1f}s")
        lines.append(f"├─ Places Discovery: {places_time:.1f}s")
        lines.append(f"├─ Weather Mapping: {weather_time:.1f}s")
        lines.append(f"├─ Processing & Display: {overhead_time:.1f}s")
        lines.append(f"└─ **Total: {total_time:.1f}s**{h3_cache_info}")
        
        await msg.edit("\n".join(lines))
        
        logging.info(f"✅ Route complete in {total_time:.2f}s")
        
    except Exception as e:
        logging.error(f"Error in smart route handler: {e}")
        import traceback
        traceback.print_exc()
        await msg.edit(f"❌ Error processing route: {str(e)}")

def register_smart_route_handlers(client: TelegramClient):
    """Register smart route handlers."""
    @client.on(events.NewMessage(pattern='/route'))
    async def _(event):
        await start_smart_route_wizard(client, event.sender_id)

    @client.on(events.NewMessage)
    async def _(event):
        if event.sender_id in route_sessions:
            if event.message.text and not event.message.text.startswith('/'):
                if await handle_smart_route_input(event, client):
                    raise events.StopPropagation

    logging.info("✅ Smart route handlers registered")
