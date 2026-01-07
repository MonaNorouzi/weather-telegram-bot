# 🔌 Integration Guide: Using H3 WeatherRouter in Your Bot

This guide shows you how to integrate the new H3 WeatherRouter into your Telegram bot handlers.

---

## Quick Integration

### Step 1: Import the Router

```python
from core.h3_weather_router import weather_router
```

### Step 2: Replace Your Existing Route Logic

**Before (Old Code):**
```python
# Old route + weather fetching logic
from core.osrm_service import osrm_service
from core.overpass_service import overpass_service
from core.openmeteo_service import openmeteo_service

# Get route
route = await osrm_service.get_route(origin, dest)

# Sample points along route
sampled_points = sample_route_points(route['coordinates'])

# Fetch places (slow!)
places = await overpass_service.get_places_along_route(sampled_points)

# Fetch weather for each place (many API calls!)
for place in places:
    weather = await openmeteo_service.get_forecast_at_time(
        place['lat'], place['lon'], eta
    )
    place['weather'] = weather
```

**After (New Code):**
```python
from core.h3_weather_router import weather_router

# Single call - does everything!
result = await weather_router.get_route_with_weather(
    origin=(source_lat, source_lon),
    dest=(dest_lat, dest_lon),
    departure_time=departure_time
)

if result['success']:
    route_info = result['route']
    segments = result['segments']
    stats = result['stats']
    
    # Use the data...
else:
    # Handle error
    error_msg = result['error']
```

**That's it!** The new router handles:
- OSRM routing ✅
- H3 segmentation ✅
- Redis cache checks ✅
- Weather API calls (only for missing data) ✅
- Cache writes ✅

---

## Complete Handler Example

### Example: `/route` Command Handler

```python
from telethon import events
from core.h3_weather_router import weather_router
from datetime import datetime

@bot.on(events.NewMessage(pattern='/route'))
async def handle_route(event):
    """Handle route weather request with H3 caching."""
    
    # Parse user input
    text = event.message.text
    # Example: "/route Tehran to Mashhad"
    
    try:
        # Extract source and destination (use your existing geocoding)
        source_coords = await geocode_city(source_city)  # (lat, lon)
        dest_coords = await geocode_city(dest_city)      # (lat, lon)
        
        # Show "calculating" message
        calc_msg = await event.reply("🔄 Calculating route and weather...")
        
        # Get route with weather using H3 router
        result = await weather_router.get_route_with_weather(
            origin=source_coords,
            dest=dest_coords,
            departure_time=datetime.now()
        )
        
        if not result['success']:
            await calc_msg.edit(f"❌ Error: {result['error']}")
            return
        
        # Extract data
        route = result['route']
        segments = result['segments']
        stats = result['stats']
        
        # Build response message
        response = f"🗺️ **Route: {source_city} → {dest_city}**\n\n"
        response += f"📏 Distance: {route['distance_km']} km\n"
        response += f"⏱️ Duration: {route['duration_hours']:.1f} hours\n"
        response += f"📊 Segments: {stats['total_segments']}\n"
        
        # Show cache performance (optional, for admins)
        if is_admin(event.sender_id):
            response += f"\n💾 Cache: {stats['cache_hit_rate']}% hit rate\n"
            response += f"⚡ API calls: {stats['new_api_calls']}\n"
        
        response += f"\n🌤️ **Weather Forecast:**\n"
        
        # Show weather for key segments (every 50km or so)
        step_size = max(1, len(segments) // 10)  # Show ~10 segments
        for i, segment in enumerate(segments[::step_size]):
            weather = segment['weather']
            response += f"\n📍 Segment {i+1}:\n"
            response += f"   Temp: {weather.get('temperature', 'N/A')}°C\n"
            response += f"   {weather.get('icon', '❓')} {weather.get('description', 'No data')}\n"
        
        await calc_msg.edit(response)
    
    except Exception as e:
        logger.error(f"Route handler error: {e}")
        await event.reply(f"❌ Error processing route: {str(e)}")
```

---

## Response Structure

### Success Response

```python
{
    "success": True,
    "route": {
        "distance_km": 923.5,
        "duration_hours": 10.2,
        "origin": (35.6892, 51.3890),
        "destination": (36.2974, 59.6062),
        "departure_time": "2026-01-01T15:00:00"
    },
    "segments": [
        {
            "h3_index": "871d2ab63ffffff",
            "lat": 35.6892,
            "lon": 51.3890,
            "weather": {
                "temperature": 12.5,
                "description": "Partly cloudy",
                "icon": "⛅",
                "wind_speed": 15,
                "humidity": 45
            }
        },
        # ... more segments
    ],
    "stats": {
        "total_segments": 142,
        "cache_hits": 120,
        "cache_misses": 22,
        "cache_hit_rate": 84.5,
        "new_api_calls": 22
    },
    "errors": None  # or list of non-fatal errors
}
```

### Error Response

```python
{
    "success": False,
    "error": "Routing service unavailable",
    "errors": ["OSRM connection failed", "Fallback also failed"],
    "stats": {
        "cache_hit_rate": 0.0,
        # ... empty stats
    }
}
```

---

## Admin Features

### Show Cache Statistics

```python
from core.h3_weather_router import weather_router

@bot.on(events.NewMessage(pattern='/h3stats'))
async def show_h3_stats(event):
    """Show H3 router statistics (admin only)."""
    
    if not is_admin(event.sender_id):
        return
    
    stats = weather_router.get_stats()
    
    msg = "📊 **H3 Weather Router Statistics**\n\n"
    msg += f"🚀 Total routes: {stats['total_routes']:,}\n"
    msg += f"📐 Segments processed: {stats['total_segments_processed']:,}\n"
    msg += f"✅ Cache hits: {stats['cache_hits']:,}\n"
    msg += f"❌ Cache misses: {stats['cache_misses']:,}\n"
    msg += f"📊 Hit rate: {stats['cache_hit_rate']:.2f}%\n"
    msg += f"🌤️ API calls: {stats['api_calls']:,}\n"
    msg += f"\n**Errors:**\n"
    msg += f"OSRM: {stats['osrm_errors']}\n"
    msg += f"Redis: {stats['redis_errors']}\n"
    msg += f"Weather API: {stats['weather_api_errors']}\n"
    
    await event.reply(msg)
```

---

## Performance Tips

### 1. Batch Route Requests

If multiple users request similar routes, the H3 cache will automatically share data:

```python
# User 1: Tehran → Mashhad (142 segments, all cache misses)
result1 = await weather_router.get_route_with_weather(...)

# User 2: Tehran → Semnan (60 segments, 45 cache hits!)
# Shares ~75% of segments with route 1
result2 = await weather_router.get_route_with_weather(...)
```

### 2. Pre-warm Common Routes

Warm up cache during bot startup:

```python
async def warm_cache():
    """Pre-warm cache with popular routes."""
    popular_routes = [
        ((35.6892, 51.3890), (36.2974, 59.6062)),  # Tehran → Mashhad
        ((35.6892, 51.3890), (32.6546, 51.6680)),  # Tehran → Isfahan
        # ... more
    ]
    
    for origin, dest in popular_routes:
        await weather_router.get_route_with_weather(origin, dest)
        await asyncio.sleep(2)  # Respect rate limits

# In main.py startup
asyncio.create_task(warm_cache())
```

### 3. Monitor Cache Performance

Log cache statistics periodically:

```python
import asyncio

async def log_h3_stats():
    """Log H3 stats every hour."""
    while True:
        await asyncio.sleep(3600)  # 1 hour
        stats = weather_router.get_stats()
        logger.info(f"H3 Cache hit rate: {stats['cache_hit_rate']:.2f}%")
```

---

## Error Handling

### Graceful Degradation

The router handles errors gracefully:

```python
result = await weather_router.get_route_with_weather(origin, dest)

if not result['success']:
    # Check what failed
    if 'OSRM' in result['error']:
        # OSRM is down, might have fallen back to public
        await event.reply("⚠️ Using backup routing (slower)")
    elif 'Redis' in result['error']:
        # Redis is down, still works but no caching
        await event.reply("⚠️ Cache unavailable (slower response)")
    else:
        # Other error
        await event.reply(f"❌ {result['error']}")
```

### Partial Results

Even with some errors, you might get partial results:

```python
if result['success']:
    segments = result['segments']
    
    # Some segments might have no weather data
    valid_segments = [s for s in segments if s['weather'].get('temperature')]
    
    if len(valid_segments) < len(segments) * 0.5:
        await event.reply("⚠️ Only partial weather data available")
```

---

## Testing Your Integration

### 1. Unit Test

```python
import pytest
from core.h3_weather_router import weather_router

@pytest.mark.asyncio
async def test_weather_router():
    result = await weather_router.get_route_with_weather(
        origin=(35.6892, 51.3890),
        dest=(35.8, 50.9)
    )
    
    assert result['success']
    assert result['route']['distance_km'] > 0
    assert len(result['segments']) > 0
```

### 2. Integration Test

```bash
# Run the test script
python test_h3_router.py
```

### 3. Manual Test in Bot

```
/route Tehran to Karaj
```

Expected response time:
- Cold cache: 5-15 seconds
- Warm cache: <1 second

---

## Migration from Old System

### Backwards Compatibility

You can keep both systems during migration:

```python
# Feature flag
USE_H3_ROUTER = os.getenv("USE_H3_ROUTER", "true").lower() == "true"

if USE_H3_ROUTER:
    result = await weather_router.get_route_with_weather(origin, dest)
    # New system
else:
    # Old system (fallback)
    result = await old_route_logic(origin, dest)
```

### A/B Testing

Compare performance:

```python
import time

# Old system
start = time.time()
old_result = await old_route_logic(origin, dest)
old_time = time.time() - start

# New system
start = time.time()
new_result = await weather_router.get_route_with_weather(origin, dest)
new_time = time.time() - start

logger.info(f"Old: {old_time:.2f}s, New: {new_time:.2f}s, Speedup: {old_time/new_time:.1f}x")
```

---

## Troubleshooting

### "No route found"

```python
# Check if coordinates are valid
if not (25 < lat < 40 and 44 < lon < 64):
    await event.reply("❌ Coordinates outside Iran")
```

### "Weather data unavailable"

```python
# Check if weather API is working
if stats['weather_api_errors'] > stats['total_segments'] * 0.5:
    await event.reply("⚠️ Weather service degraded")
```

### "Cache not working"

```python
# Check Redis connection
from core.redis_manager import redis_manager
redis_client = await redis_manager.get_client()
if not redis_client:
    logger.error("Redis unavailable - caching disabled")
```

---

## Next Steps

1. **Test the integration:** Run `python test_h3_router.py`
2. **Update your handlers:** Replace old routing logic
3. **Monitor performance:** Add logging for cache hit rates
4. **Optimize:** Pre-warm cache for popular routes

**Questions?** Check `docs/OSRM_SETUP_GUIDE.md` and `docs/H3_ARCHITECTURE.md`

---

**Last Updated:** 2026-01-01  
**Version:** 1.0.0
