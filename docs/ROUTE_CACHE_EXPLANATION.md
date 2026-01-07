# 🗺️ Route Cache - توضیح کامل

## سیستم Route Caching چطور کار می‌کنه؟

Route Cache یک سیستم **2-layer caching** است:
1. **Redis** (Hot cache - خیلی سریع)
2. **PostgreSQL** (Cold cache - کمی کندتر)

---

## معماری کامل:

```
User Request: تهران → مشهد
        ↓
┌───────────────────────────────────┐
│   1. Get Place IDs                │
│   تهران → place_id: 11            │
│   مشهد → place_id: 1282           │
└───────────────────────────────────┘
        ↓
┌───────────────────────────────────┐
│   2. Check Redis Cache            │
│   Key: route:graph:11:1282        │
└───────────────────────────────────┘
        ↓
    ┌───┴───┐
    │       │
  HIT?    MISS?
    │       │
    ↓       ↓
┌─────┐  ┌──────────────────────────┐
│ YES │  │   3. Check PostgreSQL    │
│     │  │   SELECT * FROM routes   │
│     │  │   WHERE source=11        │
│     │  │   AND target=1282        │
│     │  └──────────────────────────┘
│     │         ↓
│     │     ┌───┴───┐
│     │     │       │
│     │   HIT?    MISS?
│     │     │       │
│     │     ↓       ↓
│     │  ┌─────┐  ┌──────────────────┐
│     │  │ YES │  │   4. Graph Query │
│     │  │     │  │   pgr_dijkstra() │
│     │  │     │  └──────────────────┘
│     │  │     │         ↓
│     │  │     │  ┌──────────────────┐
│     │  │     │  │   5. Save Route  │
│     │  │     │  │   - PostgreSQL   │
│     │  │     │  │   - Redis (warm) │
│     │  │     │  └──────────────────┘
│     │  │     │
│     │  ↓     ↓
│     └──┴─────┘
│         ↓
│   ┌──────────────────────────────┐
│   │   6. Return Cached Route     │
│   │   💎 Cached Route            │
│   └──────────────────────────────┘
└───────────────────────────────────┘
```

---

## مثال واقعی گام به گام:

### درخواست 1: تهران → مشهد (اولین بار)

#### گام 1: تبدیل نام به ID
```python
# core/graph_builder.py
place_id = await get_or_create_place("تهران", ...)
# نتیجه: place_id = 11

place_id = await get_or_create_place("مشهد", ...)
# نتیجه: place_id = 1282
```

**نکته مهم**: اگه "Tehran" بگید، با normalization همون ID (11) رو میده! ✅

---

#### گام 2: چک کردن Redis
```python
# core/redis_route_cache.py
cache_key = f"route:graph:11:1282"
cached_route = await redis_client.get(cache_key)

# نتیجه: None (اولین باره!)
```

**Redis MISS** ❌

---

#### گام 3: چک کردن PostgreSQL
```python
# core/redis_route_cache.py -> _get_from_postgres()
SELECT route_data, geometries, nodes, distance_km, duration_hours
FROM routes
WHERE source_place_id = 11 
  AND target_place_id = 1282
LIMIT 1

# نتیجه: NULL (هنوز ذخیره نشده!)
```

**PostgreSQL MISS** ❌

---

#### گام 4: محاسبه مسیر از Graph
```python
# core/graph_routing_engine.py
route = await _find_path_dijkstra(
    source_node=111,  # nearest node to تهران
    target_node=2227  # nearest node to مشهد
)

# پیدا کردن نزدیک‌ترین nodes:
SELECT id FROM nodes
ORDER BY ST_Distance(geom, ST_Point(51.389, 35.689))
LIMIT 1
# نتیجه: node_id = 111

# محاسبه مسیر با Dijkstra:
SELECT * FROM pgr_dijkstra(
    'SELECT id, source, target, cost FROM edges',
    111,  -- start
    2227, -- end
    directed := true
)

# نتیجه: 
# - 782 nodes
# - 126.4 km
# - 8.2 hours
# زمان: ~10 ثانیه
```

**Route Calculated** ✅

---

#### گام 5: ذخیره در Cache

##### 5a. ذخیره در PostgreSQL
```python
# core/graph_routing_engine.py
INSERT INTO routes (
    source_place_id, 
    target_place_id,
    route_data,
    geometries,
    nodes,
    distance_km,
    duration_hours,
    created_at
) VALUES (
    11,      -- تهران
    1282,    -- مشهد
    '{"path": [111, 125, ...]}',
    '[[35.689, 51.389], ...]',
    '[111, 125, 138, ...]',
    126.4,
    8.2,
    NOW()
)
```

**Saved to PostgreSQL** ✅ (TTL: ندارد - دائمی!)

---

##### 5b. ذخیره در Redis
```python
# core/redis_route_cache.py
cache_key = "route:graph:11:1282"
cache_value = json.dumps({
    "route_data": {...},
    "geometries": [...],
    "nodes": [...],
    "distance_km": 126.4,
    "duration_hours": 8.2
})

await redis_client.setex(
    cache_key,
    604800,  # 7 روز = 604800 ثانیه
    cache_value
)
```

**Saved to Redis** ✅ (TTL: 7 روز)

---

#### گام 6: نمایش به کاربر
```
🔄 Status: 🌍 New Route
⏱️ Routing: 10.2s (first time)
```

---

### درخواست 2: Tehran → Mashhad (دومین بار - همون مسیر!)

#### گام 1: تبدیل نام به ID
```python
# با city_normalizer:
"Tehran" → normalized: "tehran" → place_id: 11 ✅
"Mashhad" → normalized: "mashhad" → place_id: 1282 ✅

# همون IDs!
```

---

#### گام 2: چک کردن Redis
```python
cache_key = "route:graph:11:1282"
cached_route = await redis_client.get(cache_key)

# نتیجه: {...} (پیدا شد!) ✅
```

**Redis HIT** ✅
**زمان**: <10ms (خیلی سریع!)

---

#### گام 3-6: رد می‌شن!
چون از Redis پیدا شد، نیازی به PostgreSQL یا Graph query نیست!

---

#### نمایش به کاربر:
```
🔄 Status: 💎 Cached Route
⏱️ Routing: 0.01s (from cache!)
```

---

### درخواست 3: تهران → مشهد (بعد از 8 روز - Redis expired!)

#### گام 1: تبدیل نام
```python
place_ids: (11, 1282)
```

---

#### گام 2: چک Redis
```python
cache_key = "route:graph:11:1282"
cached_route = await redis_client.get(cache_key)

# نتیجه: None (TTL تمام شده - 7 روز گذشته)
```

**Redis MISS** ❌

---

#### گام 3: چک PostgreSQL
```python
SELECT * FROM routes
WHERE source_place_id = 11 
  AND target_place_id = 1282

# نتیجه: {...} (پیدا شد!) ✅
```

**PostgreSQL HIT** ✅
**زمان**: ~50ms (کمی کندتر از Redis اما خیلی بهتر از Graph!)

---

#### گام 4: Warm Redis Cache
```python
# دوباره در Redis ذخیره می‌کنیم:
await redis_client.setex(
    "route:graph:11:1282",
    604800,
    cache_value
)
```

**Redis Warmed** ✅

---

#### نمایش:
```
🔄 Status: 💎 Cached Route
⏱️ Routing: 0.05s (from PostgreSQL, Redis warmed)
```

---

## مقایسه عملکرد:

| Scenario | Cache Layer | زمان | توضیح |
|----------|------------|------|--------|
| **اولین بار** | ❌ MISS | ~10s | Graph query (Dijkstra) |
| **دومین بار** | ✅ Redis | ~10ms | Hot cache |
| **بعد 8 روز** | ✅ PostgreSQL | ~50ms | Cold cache |
| **بعد 365 روز** | ✅ PostgreSQL | ~50ms | دائمی! |

---

## Cache Keys چطوری ساخته میشن؟

### کلید Redis:
```python
f"route:graph:{source_place_id}:{target_place_id}"

مثال:
"route:graph:11:1282"  # تهران → مشهد
```

### کلید PostgreSQL:
```sql
WHERE source_place_id = 11 AND target_place_id = 1282
```

**نکته**: چون از `place_id` استفاده می‌کنه (نه نام)، فارسی و انگلیسی یکسانن! ✅

---

## TTL (Time To Live):

### Redis:
```python
TTL = 7 روز (604800 ثانیه)
```
**چرا؟**
- Redis سریعه اما memory محدوده
- بعد 7 روز، routes کمتر استفاده شده expire میشن
- اما PostgreSQL هنوز داره!

### PostgreSQL:
```python
TTL = ∞ (دائمی)
```
**چرا؟**
- Disk ارزونه
- Routes تغییر نمی‌کنن (جاده‌ها ثابتن)
- یک بار محاسبه، برای همیشه!

---

## چه وقت Cache MISS میشه?

### 1. مسیر جدید
```
تبریز → بوشهر (هرگز محاسبه نشده)
→ Graph query
```

### 2. شهر جدید اضافه شده
```python
# شهر جدید در graph:
await graph_builder.add_new_city("کرمانشاه")

# مسیرهای قدیمی:
تهران → مشهد (قبلاً محاسبه شده) ✅ still cached
تهران → کرمانشاه (جدید) ❌ cache miss
```

### 3. Redis restart شده
```
Redis down → همه Redis cache‌ها پاک شد
اما PostgreSQL هنوز داره!
→ PostgreSQL hit → Redis warm
```

---

## Invalidation چطوریه؟

### معمولاً نیازی نیست!
چون:
- جاده‌ها تغییر نمی‌کنن
- Graph ثابته
- Routes همیشه یکسانن

### فقط اگه:
```python
# اگه manually جاده جدید اضافه کردیم:
await graph_builder.inject_new_road(...)

# باید cache رو invalidate کنیم:
await redis_route_cache.invalidate_route(
    source_place_id=11,
    target_place_id=1282
)

# DELETE از PostgreSQL:
DELETE FROM routes 
WHERE source_place_id = 11 AND target_place_id = 1282
```

---

## خلاصه:

### Route Cache = 2 Layer
1. **Redis** (Hot, 7 days, ~10ms)
2. **PostgreSQL** (Cold, Forever, ~50ms)

### Key = place_id
```
"route:graph:{source_id}:{target_id}"
```

### Flow:
```
Request
  ↓
Redis? → YES → Return (10ms) ✅
  ↓ NO
PostgreSQL? → YES → Warm Redis → Return (50ms) ✅
  ↓ NO
Graph Query → Save Both → Return (10s) ✅
```

### مزایا:
- 1000× سریع‌تر (10s → 10ms)
- فارسی/انگلیسی یکسان
- دائمی (PostgreSQL)
- Scalable (Redis)

**همه چیز هوشمنده!** 🧠
