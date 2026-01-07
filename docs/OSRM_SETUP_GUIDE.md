# 🐳 OSRM Setup Guide for Weather Bot

This guide walks you through setting up a **self-hosted OSRM routing engine** for Iran to achieve lightning-fast route calculations.

---

## 📋 Prerequisites

Before starting, ensure you have:

- **Docker** installed and running
- **8 GB RAM** minimum (12 GB recommended for OSRM preprocessing)
- **5 GB free disk space** (for OSM data + preprocessed files)
- **Stable internet connection** (for downloading ~450 MB OSM file)
- **Windows PowerShell** or equivalent terminal

---

## 🗺️ Step 1: Download Iran OSM Data

OSRM needs OpenStreetMap data for Iran. We'll use **Geofabrik**, which provides daily-updated extracts.

### Option A: Download via Browser

1. Visit: https://download.geofabrik.de/asia/iran.html
2. Download **iran-latest.osm.pbf** (~450 MB)
3. Save to: `c:\Users\Mona\weather_yob\osrm-data\iran-latest.osm.pbf`

### Option B: Download via PowerShell

```powershell
# Navigate to project directory
cd c:\Users\Mona\weather_yob

# Create data directory
mkdir osrm-data -Force

# Download Iran OSM data
Invoke-WebRequest -Uri "https://download.geofabrik.de/asia/iran-latest.osm.pbf" `
    -OutFile "osrm-data\iran-latest.osm.pbf"
```

**Expected result:** File `osrm-data\iran-latest.osm.pbf` should be ~450 MB

---

## ⚙️ Step 2: Preprocess OSM Data (One-Time Setup)

OSRM requires three preprocessing steps to convert raw OSM data into a routable graph. This takes **30-60 minutes** but only needs to be done once (or when updating OSM data).

### 2.1 Extract (10-15 minutes)

Extracts the road network from OSM data.

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-extract `
    -p /opt/car.lua /data/iran-latest.osm.pbf
```

**What this does:**
- Reads `iran-latest.osm.pbf`
- Extracts road network using car profile
- Outputs `iran-latest.osrm` and related files

**Expected output:**
```
[info] Expansion: 9876543 nodes/sec and 123456 edges/sec
[info] To prepare the data for routing, run: osrm-partition iran-latest.osrm
```

### 2.2 Partition (10-20 minutes)

Partitions the graph for faster queries.

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-partition `
    /data/iran-latest.osrm
```

**What this does:**
- Creates hierarchical partitions
- Optimizes for multi-level Dijkstra (MLD) algorithm

**Expected output:**
```
[info] Loaded 123456 nodes and 234567 edges
[info] MLD partition created successfully
```

### 2.3 Customize (5-10 minutes)

Customizes routing weights for car profile.

```powershell
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-customize `
    /data/iran-latest.osrm
```

**What this does:**
- Applies car-specific routing costs
- Pre-computes shortcuts for faster routing

**Expected output:**
```
[info] Customization finished after X.XX seconds
```

### Verify Preprocessing Completed

Check that these files exist in `osrm-data\`:

```powershell
ls osrm-data\iran-latest.* | Select-Object Name, Length
```

**You should see:**
- `iran-latest.osm.pbf` (original OSM data)
- `iran-latest.osrm` (extracted graph)
- `iran-latest.osrm.names`
- `iran-latest.osrm.hsgr`
- `iran-latest.osrm.geometry`
- `iran-latest.osrm.edges`
- `iran-latest.osrm.cells`
- `iran-latest.osrm.mldgr`
- And several other `.osrm.*` files

---

## 🚀 Step 3: Start OSRM Container

Now that preprocessing is complete, start the OSRM routing server.

```powershell
# Navigate to project root
cd c:\Users\Mona\weather_yob

# Start OSRM container
docker-compose up -d osrm-backend
```

**What this does:**
- Starts OSRM HTTP server on port 5000
- Mounts `osrm-data` directory (read-only)
- Sets up health checks and auto-restart

**Check if running:**

```powershell
docker ps | Select-String "osrm"
```

**Expected output:**
```
weather-bot-osrm   ghcr.io/project-osrm/osrm-backend:latest   Up 30 seconds   0.0.0.0:5000->5000/tcp
```

---

## 🧪 Step 4: Test OSRM

Verify OSRM is working correctly.

### Test 1: Health Check

```powershell
curl http://localhost:5000/health
```

**Expected:** `Ok`

### Test 2: Sample Route (Tehran → Karaj)

```powershell
# Tehran (35.6892,51.3890) to Karaj (35.8,50.9)
# Note: OSRM uses lon,lat order!
curl "http://localhost:5000/route/v1/driving/51.3890,35.6892;50.9,35.8?overview=false"
```

**Expected JSON response:**
```json
{
  "code": "Ok",
  "routes": [
    {
      "distance": 38743.2,
      "duration": 2145.6,
      ...
    }
  ]
}
```

**If you see `"code": "Ok"`**, OSRM is working! 🎉

---

## 🔧 Step 5: Update Bot Configuration

Update your `.env` file to use the local OSRM instance:

```bash
# OSRM Configuration
OSRM_URL=http://localhost:5000
OSRM_FALLBACK_PUBLIC=true

# H3 Configuration (defaults are good for most cases)
H3_RESOLUTION=7
H3_WEATHER_CACHE_TTL=3600
PARALLEL_WEATHER_REQUESTS=10
```

---

## 🔄 Updating OSM Data (Monthly Maintenance)

Iran's road network changes over time. To update:

### 1. Download Latest Data

```powershell
cd c:\Users\Mona\weather_yob\osrm-data

# Backup old data (optional)
mv iran-latest.osm.pbf iran-latest.osm.pbf.backup

# Download new data
Invoke-WebRequest -Uri "https://download.geofabrik.de/asia/iran-latest.osm.pbf" `
    -OutFile "iran-latest.osm.pbf"
```

### 2. Stop OSRM Container

```powershell
docker-compose stop osrm-backend
```

### 3. Re-run Preprocessing

```powershell
# Extract
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-extract `
    -p /opt/car.lua /data/iran-latest.osm.pbf

# Partition
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-partition `
    /data/iran-latest.osrm

# Customize
docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-customize `
    /data/iran-latest.osrm
```

### 4. Restart OSRM

```powershell
docker-compose up -d osrm-backend
```

---

## 🐛 Troubleshooting

### Problem: "No such container: weather-bot-osrm"

**Solution:** Start the container first:
```powershell
docker-compose up -d osrm-backend
```

### Problem: "Cannot connect to localhost:5000"

**Check 1:** Is the container running?
```powershell
docker ps | Select-String "osrm"
```

**Check 2:** Check container logs:
```powershell
docker logs weather-bot-osrm
```

**Common causes:**
- Preprocessing not completed (missing `.osrm` files)
- Port 5000 already in use by another application
- Docker networking issue

### Problem: "No route found" for valid coordinates

**Possible causes:**
- Coordinates outside Iran (OSRM only has Iran data)
- Coordinates not on a road (OSRM can't route to random field)
- Wrong coordinate order (OSRM uses `lon,lat`, not `lat,lon`)

**Solution:** Verify coordinates are within Iran and on road network

### Problem: Preprocessing fails with "Out of memory"

**Solution:** Close other applications and increase Docker memory:
1. Docker Desktop → Settings → Resources
2. Increase Memory to 8-12 GB
3. Restart Docker

### Problem: Container crashes after starting

**Check logs:**
```powershell
docker logs weather-bot-osrm --tail 100
```

**Common error:** `iran-latest.osrm not found`
- Means preprocessing wasn't completed
- Re-run Steps 2.1, 2.2, 2.3

---

## 📊 Performance Expectations

### Query Times (Tehran → Mashhad, ~900km)

| Routing Engine | Response Time |
|----------------|---------------|
| Public OSRM    | 300-500ms     |
| Local OSRM     | **10-30ms**   |
| Speedup        | **15-50x**    |

### Full Route with Weather (Cold Cache)

| Component      | Time          |
|----------------|---------------|
| OSRM routing   | 10-30ms       |
| H3 conversion  | 5-10ms        |
| Redis check    | 1-5ms         |
| Weather API    | 2-10s         |
| **Total**      | **2-15s**     |

### Full Route with Weather (Warm Cache)

| Component      | Time          |
|----------------|---------------|
| OSRM routing   | 10-30ms       |
| H3 conversion  | 5-10ms        |
| Redis hits     | 1-2ms         |
| **Total**      | **<100ms**    |

---

## 🎯 Next Steps

1. ✅ OSRM is now running and ready
2. Install new Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Test the new H3 weather router (see main README)
4. Monitor performance with `/cachestats` command

---

## 📚 Additional Resources

- **OSRM Documentation:** https://project-osrm.org/
- **Geofabrik Downloads:** https://download.geofabrik.de/
- **H3 Hexagon System:** https://h3geo.org/
- **Docker Compose Docs:** https://docs.docker.com/compose/

---

**Last Updated:** 2026-01-01  
**Version:** 1.0.0
