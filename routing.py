import asyncio
import aiohttp
import aiofiles
import json
import time
import os
import hashlib
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt

SEARCH_RADIUS = 5000
SAMPLE_INTERVAL_KM = 5
OVERPASS_BATCH_SIZE = 15
OVERPASS_CONCURRENCY = 2
MAX_RETRIES = 5
CACHE_DIR = "route_cache"
OUTPUT_FILENAME = "trip_plan_smart.json"

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class Timer:
    def __init__(self, name):
        self.name = name
        self.start = None
    def __enter__(self):
        self.start = time.time()
        print(f"⏳ شروع: {self.name}...")
        return self
    def __exit__(self, *args):
        elapsed = time.time() - self.start
        print(f"✅ پایان: {self.name} | ⏱️ زمان مصرف شده: {elapsed:.2f} ثانیه")

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    a = sin((lat2-lat1)/2)**2 + cos(lat1) * cos(lat2) * sin((lon2-lon1)/2)**2
    return 2 * asin(sqrt(a)) * 6371

def add_time(start_dt, seconds_elapsed):
    return start_dt + timedelta(seconds=seconds_elapsed)

def sample_route_points(full_coords):
    sampled = [full_coords[0]]
    last = full_coords[0]
    threshold = SAMPLE_INTERVAL_KM / 111.0
    for coord in full_coords:
        if sqrt((coord[1]-last[1])**2 + (coord[0]-last[0])**2) > threshold:
            sampled.append(coord)
            last = coord
    sampled.append(full_coords[-1])
    return sampled

def generate_cache_key(start_lat, start_lon, end_lat, end_lon):
    data = f"{round(start_lat, 3)},{round(start_lon, 3)}-{round(end_lat, 3)},{round(end_lon, 3)}"
    return hashlib.md5(data.encode()).hexdigest()

async def fetch_route_osrm(session, start_lat, start_lon, end_lat, end_lon):
    base_url = "http://router.project-osrm.org/route/v1/driving/"
    url = f"{base_url}{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson&steps=true&annotations=duration"
    async with session.get(url) as resp:
        return await resp.json()

async def fetch_overpass_chunk(session, coords_batch, semaphore, chunk_id):
    coord_str = ",".join([f"{lat},{lon}" for lon, lat in coords_batch])
    query = f"""[out:json][timeout:60];node["place"~"city|town|village|hamlet|suburb|isolated_dwelling"](around:{SEARCH_RADIUS},{coord_str});out body;"""
    
    attempt = 0
    wait_time = 2
    async with semaphore:
        while attempt < MAX_RETRIES:
            try:
                await asyncio.sleep(0.5)
                async with session.post("https://overpass-api.de/api/interpreter", data=query) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('elements', [])
                    elif resp.status == 429:
                        print(f"⚠️ لیمیت Overpass (بخش {chunk_id}). صبر {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        attempt += 1
                        wait_time *= 2
                    else:
                        attempt += 1
                        await asyncio.sleep(wait_time)
            except:
                attempt += 1
                await asyncio.sleep(wait_time)
    return []

async def fetch_weather_bulk(session, locations, start_dt):
    if not locations: return []
    
    chunk_size = 50
    chunks = [locations[i:i + chunk_size] for i in range(0, len(locations), chunk_size)]
    
    all_weather_data = []
    
    for chunk in chunks:
        lats = ",".join([str(loc['coords']['lat']) for loc in chunk])
        lons = ",".join([str(loc['coords']['lon']) for loc in chunk])
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": "temperature_2m",
            "forecast_days": 2,
            "timezone": "auto"
        }
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict) and 'hourly' in data:
                        all_weather_data.append(data)
                    elif isinstance(data, list):
                        all_weather_data.extend(data)
        except Exception as e:
            print(f"Weather Error: {e}")
            
    for i, loc in enumerate(locations):
        try:
            w_data = all_weather_data[i]
            if w_data and 'hourly' in w_data:
                arrival_time = add_time(start_dt, loc['arrival_seconds'])
                target_str = arrival_time.strftime("%Y-%m-%dT%H:00")
                
                times = w_data['hourly']['time']
                temps = w_data['hourly']['temperature_2m']
                
                idx = next((k for k, t in enumerate(times) if t >= target_str), -1)
                if idx != -1:
                    loc['temperature_celsius'] = temps[idx]
                    loc['arrival_time'] = arrival_time.strftime("%H:%M")
        except:
            loc['temperature_celsius'] = "N/A"
            
    return locations

async def get_static_route_data(session, start_lat, start_lon, end_lat, end_lon):
    cache_key = generate_cache_key(start_lat, start_lon, end_lat, end_lon)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        print("💎 مسیر در کش یافت شد! بارگذاری سریع...")
        async with aiofiles.open(cache_file, mode='r', encoding='utf-8') as f:
            content = await f.read()
            return json.loads(content)
            
    print("🌍 مسیر جدید است. دریافت از OSRM و Overpass...")
    
    route_data = await fetch_route_osrm(session, start_lat, start_lon, end_lat, end_lon)
    if route_data.get("code") != "Ok": return None
    
    route = route_data["routes"][0]
    full_coords = route["geometry"]["coordinates"]
    durations = route["legs"][0]["annotation"]["duration"]
    
    accumulated_time = [0]
    curr = 0
    for d in durations:
        curr += d
        accumulated_time.append(curr)
        
    sampled_coords = sample_route_points(full_coords)
    chunks = [sampled_coords[i:i + OVERPASS_BATCH_SIZE] for i in range(0, len(sampled_coords), OVERPASS_BATCH_SIZE)]
    
    overpass_sem = asyncio.Semaphore(OVERPASS_CONCURRENCY)
    tasks = []
    for i, chunk in enumerate(chunks):
        tasks.append(fetch_overpass_chunk(session, chunk, overpass_sem, i+1))
    
    results_nested = await asyncio.gather(*tasks)
    
    route_sparse = full_coords[::10]
    times_sparse = accumulated_time[::10]
    
    processed_places = []
    seen = set()
    
    for batch in results_nested:
        for place in batch:
            p_lat, p_lon = place['lat'], place['lon']
            p_name = place.get('tags', {}).get('name:fa', place.get('tags', {}).get('name', ''))
            
            if not p_name or p_name in seen: continue
            seen.add(p_name)
            
            min_dist = float('inf')
            closest_idx = 0
            for i, (r_lon, r_lat) in enumerate(route_sparse):
                d = (r_lat - p_lat)**2 + (r_lon - p_lon)**2
                if d < min_dist:
                    min_dist = d
                    closest_idx = i
            
            arrival_secs = times_sparse[closest_idx] if closest_idx < len(times_sparse) else times_sparse[-1]
            
            processed_places.append({
                "place": p_name,
                "type": place.get('tags', {}).get('place', 'unknown'),
                "coords": {"lat": p_lat, "lon": p_lon},
                "arrival_seconds": arrival_secs
            })
            
    processed_places.sort(key=lambda x: x['arrival_seconds'])
    
    cache_data = {
        "total_duration_seconds": route["duration"],
        "places": processed_places
    }
    
    async with aiofiles.open(cache_file, mode='w', encoding='utf-8') as f:
        await f.write(json.dumps(cache_data, ensure_ascii=False))
        
    return cache_data

async def main_async(start_lat, start_lon, end_lat, end_lon, start_time_str):
    now = datetime.now()
    start_dt = datetime.strptime(start_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
    
    async with aiohttp.ClientSession() as session:
        
        with Timer("دریافت اطلاعات مسیر و شهرها"):
            static_data = await get_static_route_data(session, start_lat, start_lon, end_lat, end_lon)
            if not static_data:
                print("❌ خطا در دریافت اطلاعات مسیر")
                return

        places = static_data['places']
        print(f"📊 پردازش آب‌وهوا برای {len(places)} نقطه...")
        
        with Timer("دریافت آنلاین آب‌وهوا"):
            final_places = await fetch_weather_bulk(session, places, start_dt)
            
        final_output = {
            "meta": {
                "start_time": start_time_str,
                "estimated_arrival": add_time(start_dt, static_data['total_duration_seconds']).strftime("%H:%M")
            },
            "schedule": final_places
        }
        
        async with aiofiles.open(OUTPUT_FILENAME, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(final_output, ensure_ascii=False, indent=4))
            
        print("\n" + "="*40)
        print(f"✅ انجام شد! تعداد نقاط: {len(final_places)}")
        print(f"💾 فایل: {OUTPUT_FILENAME}")
        print("="*40)

if __name__ == "__main__":
    asyncio.run(main_async(35.6892, 51.3890, 36.2972, 59.6067, "14:00"))