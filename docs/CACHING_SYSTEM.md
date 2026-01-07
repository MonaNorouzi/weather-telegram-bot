# 📋 سیستم Caching - مستندات کامل

## 🏗️ معماری کلی: 2-Layer Caching

پروژه از یک **معماری 2-لایه** استفاده می‌کند:

### Layer 1: Redis (Hot Cache - فوق‌سریع)
- **سرعت:** <1ms
- **استفاده:** داده‌های پرتکرار
- **TTL:** Dynamic (به timezone وابسته)
- **Persistence:** In-memory (volatile)

### Layer 2: PostgreSQL (Cold Cache - دائمی)
- **سرعت:** 50-200ms
- **استفاده:** Fallback + long-term storage
- **TTL:** ندارد (permanent)
- **Persistence:** Disk-based (durable)

---

## 🔴 Redis Caches (3 نوع)

### 1️⃣ Redis Route Cache (`redis_route_cache.py`)

**کاربرد:** Cache کردن places یافت شده روی مسیر

**Structure:**
```python
Key: "route:places:{source_id}:{target_id}"
Value: JSON list of places
TTL: 7 days (604800 seconds)
```

**جریان کار:**
```
1. User request: تهران → مشهد
2. Check Redis: route:places:11:234
   ├─ HIT → Return از Redis (<1ms)
   └─ MISS → Query Overpass API (250s)
       └─ Store در Redis + PostgreSQL
```

**Dual-Write Strategy:**
- همزمان در Redis و PostgreSQL ذخیره می‌شود
- Redis برای سرعت
- PostgreSQL برای durability

**کد نمونه:**
```python
async def get_cached_places(source_id, target_id):
    # Try Redis first (HOT)
    redis_key = f"route:places:{source_id}:{target_id}"
    cached = await redis.get(redis_key)
    
    if cached:
        stats["redis_hits"] += 1
        return json.loads(cached)
    
    # Fallback to PostgreSQL (COLD)
    pg_result = await postgres.get(source_id, target_id)
    
    if pg_result:
        # Warm up Redis
        await redis.set(redis_key, json.dumps(pg_result), ex=604800)
        stats["postgres_hits"] += 1
        return pg_result
    
    # Cache MISS - fetch from Overpass
    return None
```

---

### 2️⃣ Redis Weather Cache (`redis_weather_cache.py`)

**کاربرد:** Cache کردن پیش‌بینی آب‌وهوا

**Structure:**
```python
Key: "weather:{geohash}_{hour}_{model_run}"
# مثال: "weather:tq6mu37_2026010117_unknown"

Value: {
    "temperature": 12.5,
    "icon": "☁️",
    "weather_description": "Cloudy",
    "cached_at": "2025-12-31T00:30:00Z",
    "expires_at": "2026-01-01T17:29:59Z"
}

TTL: Dynamic (تا آخر ساعت بعدی در timezone محلی)
```

#### ویژگی‌های پیشرفته:

#### A) Dynamic TTL (هوشمند!)
```python
def calculate_ttl(forecast_time, location_tz):
    """Expire at top of next hour in local timezone"""
    local_time = forecast_time.astimezone(location_tz)
    next_hour = (local_time + timedelta(hours=1)).replace(minute=0, second=0)
    ttl = (next_hour - datetime.now(location_tz)).total_seconds()
    return ttl
```

**مثال:**
- الان: 13:45
- Forecast: 14:30
- TTL: تا 15:00 (15 دقیقه)
- چرا؟ چون بعد از 15:00 داده باید refresh شود

#### B) Singleflight Pattern (جلوگیری از Thundering Herd)

**مشکل:** 500 درخواست همزمان برای همان داده → 500 API call!

**راه‌حل:** فقط اولین request API را صدا می‌زند، بقیه منتظر می‌مانند

```python
class SingleflightLock:
    async def get_or_fetch(self, key, fetch_func):
        lock_key = f"lock:{key}"
        
        # Try to acquire lock
        acquired = await redis.set(lock_key, "1", nx=True, ex=30)
        
        if acquired:
            # I'm the ONE - fetch data
            stats["locks_acquired"] += 1
            result = await fetch_func()
            await redis.set(key, result)
            await redis.delete(lock_key)
            return result
        else:
            # Wait for the ONE to finish
            stats["waits"] += 1
            for _ in range(30):
                await asyncio.sleep(1)
                cached = await redis.get(key)
                if cached:
                    return cached
            
            # Timeout - fetch anyway
            stats["timeouts"] += 1
            return await fetch_func()
```

**نتیجه:**
- 500 request → فقط 1 API call
- 499 request دیگر از cache می‌خوانند
- **API cost reduction: 99.8%**

#### C) Stale-While-Revalidate (Fault Tolerance)

اگر Redis down شود، داده‌های **کمی قدیمی** را serve می‌کند:

```python
async def get(lat, lon, forecast_time, allow_stale=True):
    cached = await redis.get(key)
    
    if cached:
        expires_at = cached['expires_at']
        now = datetime.now()
        
        if now > expires_at:
            # Expired!
            age = (now - expires_at).total_seconds()
            
            if allow_stale and age <= 3600:  # Max 1 hour stale
                stats["stale_serves"] += 1
                logging.warning(f"Serving stale data ({age}s old)")
                return cached  # Better than nothing!
        
        return cached
```

---

### 3️⃣ Redis Geospatial Cache (`redis_geospatial_cache.py`)

**کاربرد:** پیدا کردن نودهای نزدیک (برای graph routing)

**Structure:**
```python
Key: "geo:nodes"
Type: Redis ZSET with geohash scores
Members: 4,250 node IDs with (lon, lat) coordinates
Commands: GEOADD, GEORADIUS, GEODIST, GEOPOS
```

**Redis GEO Commands:**

```python
# Load all nodes at startup
await redis.geoadd("geo:nodes", 
    (lon1, lat1, "node_123"),
    (lon2, lat2, "node_456"),
    # ... 4,250 nodes
)

# Find nearby nodes (SUPER FAST!)
results = await redis.georadius(
    "geo:nodes",
    longitude=51.5,
    latitude=35.7,
    radius=5,  # km
    unit="km",
    withdist=True,
    count=10,
    sort="ASC"
)
# Returns: [(node_id, distance_km), ...]
```

**Performance Comparison:**
```
PostGIS ST_DWithin:  50-100ms
Redis GEORADIUS:     <1ms
─────────────────────────────
Speedup:             50-100x faster!
```

---

## 🔄 جریان کامل یک Request

مثال: User می‌گوید "تهران به مشهد"

### مرحله 1: Route Cache Check

```
[User] تهران → مشهد

[Handler] Check Redis route cache
  ├─ Key: route:places:11:234
  ├─ Redis.get() → <1ms
  └─ Result: MISS (first time)

[Handler] Check PostgreSQL cache
  ├─ Query: SELECT * FROM route_places_cache WHERE...
  ├─ Postgres.fetch() → 50ms
  └─ Result: MISS

[Handler] Call Overpass API
  ├─ Sample: 198 points (every 5km on 987km route)
  ├─ Batches: 14 batches × 15 points
  ├─ Retries: Exponential backoff on 429/504
  ├─ Time: ~250 seconds (SLOW!)
  └─ Result: 425 places found

[Handler] Store in caches (Dual-Write)
  ├─ Redis: SET route:places:11:234 [...] EX 604800
  └─ PostgreSQL: INSERT INTO route_places_cache
  
[Handler] Return 425 places to user
```

### مرحله 2: Weather Fetch (برای هر place)

```
[Handler] For each of 425 places in parallel:

Place #1: کرج (35.8, 50.9) at 10:30
  ├─ Geohash: tq6mu37
  ├─ Hour: 2026010110
  ├─ Redis key: weather:tq6mu37_2026010110_*
  
  [Singleflight Lock]
  ├─ Check lock: lock:weather:tq6mu37_2026010110
  ├─ Lock not exists → I'm FIRST!
  ├─ Acquire lock (30s TTL)
  
  [Fetch Weather]
  ├─ Call OpenMeteo API → 500ms
  ├─ Calculate dynamic TTL → 3600s
  ├─ Store in Redis
  ├─ Release lock
  └─ Return: {"temperature": 8, "icon": "☁️"}

Place #2: کرج (35.8, 50.9) at 10:30 [SAME LOCATION & TIME!]
  ├─ Redis key: weather:tq6mu37_2026010110_*
  
  [Singleflight Lock]
  ├─ Check lock: EXISTS!
  ├─ Wait for first request...
  ├─ Poll Redis every 1s
  ├─ After 2s: Data available!
  └─ Return from cache → <1ms (NO API CALL!)

Place #3: قم (34.6, 50.8) at 12:00
  ├─ Different location/time
  ├─ New key: weather:tq6qkwq_2026010112_*
  ├─ Another singleflight Lock...
  
... (422 more places)

[Statistics]
├─ Unique (geohash, hour) combinations: ~50
├─ API calls WITH singleflight: 50
├─ API calls WITHOUT singleflight: 425
└─ Savings: 88% fewer API calls!
```

**نتیجه:**
```
Without cache: 425 API calls × 500ms = 212 seconds
With cache + singleflight: ~50 API calls × 500ms = 25 seconds
With warm cache: 0 API calls = <1 second
```

---

## 📊 Performance Metrics

### Before Redis (PostgreSQL only)

```
┌──────────────────────────────┬─────────────┐
│ Operation                    │ Time        │
├──────────────────────────────┼─────────────┤
│ Route places cache           │ 50-200ms    │
│ Weather fetch (425 places)   │ 100-500ms/ea│
│ Geospatial queries           │ 50-100ms    │
│                              │             │
│ Total (cold):                │ 3-10 min    │
│ Total (warm):                │ 30-60 sec   │
└──────────────────────────────┴─────────────┘
```

### After Redis (2-Layer)

```
┌──────────────────────────────┬─────────────┐
│ Operation                    │ Time        │
├──────────────────────────────┼─────────────┤
│ Route cache (Redis hit)      │ <1ms        │
│ Route cache (PG fallback)    │ 50ms        │
│ Weather (Redis hit)          │ <1ms        │
│ Weather (API miss)           │ 500ms       │
│ Geospatial (Redis)           │ <1ms        │
│                              │             │
│ Total (warm cache):          │ <5 sec      │
│ Total (cold cache):          │ 30-60 sec   │
└──────────────────────────────┴─────────────┘
```

**بهبود کلی: 10-120x سریع‌تر!** 🚀

---

## 🔧 Admin Commands

### `/cachestats` - آمار Redis

نمایش آمار کامل Redis:

```
📊 Redis Cache Statistics

🔴 Redis Status: ✅ Connected
💾 Memory Usage: 45.2 MB / 512 MB (8.8%)
📈 Total Keys: 1,247
⏱️ Uptime: 2 days, 5 hours

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🗺️ Route Cache
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Cache Hits:    234
❌ Cache Misses:  12
📊 Hit Rate:      95.1%
🔄 PG Fallbacks:  3

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌤️ Weather Cache
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Cache Hits:         1,456
❌ Cache Misses:       89
📊 Hit Rate:           94.2%
⚡ Singleflight Locks: 56
⏳ Singleflight Waits: 412
💾 Stale Serves:       2

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Geospatial Cache  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Nodes Loaded:      4,250
🎯 Redis Hits:        567
❌ PostGIS Fallbacks: 3
📊 Hit Rate:          99.5%
```

### `/clearcache` - پاک کردن cache

```
🗑️ Clear Cache Options:

1️⃣ Clear route cache only
2️⃣ Clear weather cache only
3️⃣ Clear geospatial cache only
4️⃣ Clear ALL Redis caches
5️⃣ Cancel

Reply with option number (1-5):
```

### `/reloadgeo` - Reload geospatial index

```
🔄 Reloading geospatial index...

📍 Fetching nodes from PostgreSQL...
   └─ Found 4,250 nodes

⚡ Loading into Redis in batches...
   ├─ Batch 1/43: 100 nodes ✅
   ├─ Batch 2/43: 100 nodes ✅
   ...
   └─ Batch 43/43: 50 nodes ✅

✅ Successfully loaded 4,250 nodes in 0.14s
```

---

## 🛡️ Fault Tolerance

### سناریو 1: Redis Down

```python
# در هر Redis operation
redis_client = await redis_manager.get_client()

if not redis_client:
    # Gracefully fallback to PostgreSQL
    logging.warning("⚠️ Redis unavailable, using PostgreSQL fallback")
    stats["redis_unavailable"] += 1
    return await get_from_postgres()
```

**رفتار:**
- هیچ exception throw نمی‌شود
- Seamless fallback به PostgreSQL
- کاربر متوجه نمی‌شود (فقط کمی کندتر)

### سناریو 2: PostgreSQL Down

```python
try:
    result = await postgres.fetch(query)
except Exception as e:
    logging.error(f"❌ PostgreSQL error: {e}")
    
    # Try to serve stale data from Redis
    stale = await redis.get(key, allow_stale=True)
    
    if stale:
        logging.warning("⚠️ Serving stale data from Redis")
        return stale
    
    # Last resort: return empty/error
    return None
```

### سناریو 3: Both Down

```python
if not redis_client and not postgres_available:
    # Graceful degradation
    logging.critical("🔴 Both caches unavailable!")
    
    # Still try to serve user, just slower
    return await fetch_from_external_api()
```

---

## 🔍 Monitoring & Debugging

### Logging Levels

**INFO:** Normal operations
```
[INFO] ✅ Redis cache HIT: route:places:11:234
[INFO] 💾 Cached 425 places in Redis
```

**WARNING:** Degraded performance
```
[WARNING] ⚠️ Redis unavailable, using PostgreSQL
[WARNING] ⚠️ Serving stale weather (1200s old)
```

**ERROR:** Issues needing attention
```
[ERROR] ❌ Redis connection failed: Connection refused
[ERROR] ❌ Singleflight timeout after 30s
```

### Statistics Tracking

همه ماژول‌های cache آمار جمع‌آوری می‌کنند:

```python
class RedisRouteCache:
    def __init__(self):
        self.stats = {
            "redis_hits": 0,
            "redis_misses": 0,
            "postgres_hits": 0,
            "postgres_misses": 0,
            "cache_errors": 0
        }
    
    def get_stats(self):
        total = self.stats["redis_hits"] + self.stats["redis_misses"]
        hit_rate = (self.stats["redis_hits"] / total * 100) if total > 0 else 0
        
        return {
            **self.stats,
            "hit_rate_percent": round(hit_rate, 2)
        }
```

---

## 📝 Configuration (`.env`)

```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=           # Optional
REDIS_MAX_CONNECTIONS=50  # Connection pool size
```

### پیکربندی پیشرفته:

```python
# core/redis_manager.py
class RedisManager:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2.0
        self.health_check_interval = 60  # seconds
        self.auto_reconnect = True
```

---

## 🚀 Performance Tuning Tips

### 1. TTL Optimization

```python
# Short TTL for volatile data
route_cache_ttl = 7 * 24 * 3600  # 7 days

# Dynamic TTL for time-sensitive data
weather_ttl = calculate_dynamic_ttl(forecast_time, timezone)

# No expiry for stable data
geospatial_ttl = None  # Never expires
```

### 2. Connection Pooling

```python
# Adjust based on load
REDIS_MAX_CONNECTIONS = 50  # Default
REDIS_MAX_CONNECTIONS = 100 # High load
REDIS_MAX_CONNECTIONS = 20  # Low memory
```

### 3. Batch Operations

```python
# Bad: Individual SETs
for item in items:
    await redis.set(key, value)

# Good: Pipeline
async with redis.pipeline() as pipe:
    for item in items:
        pipe.set(key, value)
    await pipe.execute()
```

---

## 📚 مراجع و منابع

- [Redis Documentation](https://redis.io/docs/)
- [Redis GEO Commands](https://redis.io/commands#geo)
- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [Singleflight Pattern](https://github.com/golang/groupcache/blob/master/singleflight/singleflight.go)
- [Stale-While-Revalidate](https://web.dev/stale-while-revalidate/)

---

## ❓ FAQ

### چرا 2 لایه؟
- Redis: سرعت (<1ms)
- PostgreSQL: Durability + Fallback

### چرا Singleflight؟
جلوگیری از waste کردن API quota با 500 درخواست همزمان برای همان داده

### چرا Dynamic TTL؟
تا داده‌های weather همیشه fresh باشند (expire at hour boundaries)

### چگونه Redis را update کنم؟
Auto-update دارد. فقط وقتی ایران OSM update می‌شود باید `/reloadgeo` بزنید.

### چطور عملکرد cache را بهبود دهم?
1. Check `/cachestats` for hit rate
2. اگر hit rate < 80%: TTL را افزایش دهید
3. Monitor memory usage
4. Use batch operations where possible

---

**آخرین بروزرسانی:** 2025-12-31  
**نسخه:** 2.0.0 (با Redis Integration)
