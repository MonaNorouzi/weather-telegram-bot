# 🚀 Quick Start: OSRM Docker Setup

**Complete this in 30-60 minutes (one-time setup)**

---

## ✅ Step 1: Create Data Directory

```powershell
cd c:\Users\Mona\weather_yob
mkdir osrm-data
```

---

## ⬇️ Step 2: Download Iran OSM Data

**Option A - Browser:**
1. Visit: https://download.geofabrik.de/asia/iran.html
2. Click "iran-latest.osm.pbf" (~450 MB)
3. Save to: `c:\Users\Mona\weather_yob\osrm-data\`

**Option B - PowerShell:**
```powershell
Invoke-WebRequest -Uri "https://download.geofabrik.de/asia/iran-latest.osm.pbf" `
    -OutFile "osrm-data\iran-latest.osm.pbf"
```

**Verify:**
```powershell
ls osrm-data\iran-latest.osm.pbf
# Should show ~450 MB file
```

---

## 🔧 Step 3: Preprocess Data (Extract)

**Run this command** (takes 10-15 minutes):

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/iran-latest.osm.pbf
```

**What you'll see:**
```
[info] Expansion: 9876543 nodes/sec and 123456 edges/sec
[info] To prepare the data for routing, run: osrm-partition...
```

**Expected result:** Creates `iran-latest.osrm` file

---

## 📊 Step 4: Partition Graph

**Run this command** (takes 10-20 minutes):

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/iran-latest.osrm
```

**What you'll see:**
```
[info] MLD partition created successfully
```

---

## ⚡ Step 5: Customize Routing

**Run this command** (takes 5-10 minutes):

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/iran-latest.osrm
```

**What you'll see:**
```
[info] Customization finished after X.XX seconds
```

---

## 🚢 Step 6: Start OSRM Server

```powershell
docker-compose up -d osrm-backend
```

**Verify it's running:**
```powershell
docker ps | Select-String "osrm"
```

**Expected output:**
```
weather-bot-osrm   ghcr.io/project-osrm/osrm-backend:latest   Up X seconds   0.0.0.0:5000->5000/tcp
```

---

## ✅ Step 7: Test OSRM

**Quick health check:**
```powershell
curl http://localhost:5000/health
```

**Expected:** `Ok`

**Test route (Tehran → Karaj):**
```powershell
curl "http://localhost:5000/route/v1/driving/51.3890,35.6892;50.9,35.8?overview=false"
```

**Expected:** JSON with `"code": "Ok"`

---

## 🎉 Step 8: Update Bot Configuration

Add to your `.env` file:

```bash
# OSRM Configuration
OSRM_URL=http://localhost:5000
OSRM_FALLBACK_PUBLIC=true

# H3 Configuration
H3_RESOLUTION=7
H3_WEATHER_CACHE_TTL=3600
PARALLEL_WEATHER_REQUESTS=10
```

---

## 📦 Step 9: Install New Dependencies

```powershell
pip install -r requirements.txt
```

This installs the `polyline` package needed for OSRM polyline decoding.

---

## 🧪 Step 10: Test Migration

```powershell
# Check current cache status
python scripts/migrate_cache_to_h3.py --mode stats

# Clear old cache (optional but recommended)
python scripts/migrate_cache_to_h3.py --mode clear

# Warm up H3 cache with common routes
python scripts/migrate_cache_to_h3.py --mode warm
```

---

## ✅ Done!

Your OSRM server is now running. Start your bot and test a route:

```powershell
python main.py
```

In Telegram: `/route Tehran to Mashhad`

**Expected performance:**
- First request: ~5-15 seconds (cold cache)
- Second request: <1 second (warm cache)

---

## 🆘 Troubleshooting

### "Cannot connect to localhost:5000"

**Check if container is running:**
```powershell
docker ps
```

**Check logs:**
```powershell
docker logs weather-bot-osrm
```

**Common fix:** Restart container
```powershell
docker-compose restart osrm-backend
```

### "No route found"

- Make sure coordinates are in Iran
- Check coordinate order (lon,lat for OSRM API)
- Verify preprocessing completed successfully

### "Out of memory" during preprocessing

- Close other applications
- Docker Desktop → Settings → Resources → Increase Memory to 8-12 GB

---

**Need detailed docs?** See [OSRM_SETUP_GUIDE.md](OSRM_SETUP_GUIDE.md) for complete documentation.
