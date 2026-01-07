# Graph Routing System - Setup Guide

This document explains how to set up and use the graph database routing system.

## Overview

The graph-based routing system uses PostgreSQL + PostGIS + pgRouting to create an intelligent caching layer that:
- ✅ Caches routes as a growing graph of nodes and edges
- ✅ Reduces external API calls (OSRM) for frequently queried routes
- ✅ Applies dynamic weather overlays without storing weather in the static graph
- ✅ Supports multi-entry access points for cities
- ✅ Grows organically with each new route query

## Prerequisites

1. **PostgreSQL 12+** with extensions:
   - PostGIS 3.0+
   - pgRouting 3.0+

2. **Python packages** (already in requirements.txt):
   - asyncpg==0.29.0
   - psycopg2-binary==2.9.9

## Installation

### Step 1: Install PostgreSQL

#### Windows:
```bash
# Download from: https://www.postgresql.org/download/windows/
# OR use Chocolatey:
choco install postgresql

# Install PostGIS:
# Download from: https://postgis.net/install/
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install postgresql-14 postgresql-14-postgis-3 postgresql-14-pgrouting
```

#### macOS:
```bash
brew install postgresql@14 postgis pgrouting
brew services start postgresql@14
```

### Step 2: Configure Database

1. Create database and user:
```sql
-- Login as postgres user
psql -U postgres

-- Create database
CREATE DATABASE weather_bot_routing;

-- Create user (optional, or use postgres)
CREATE USER weather_bot WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE weather_bot_routing TO weather_bot;
```

2. Update `.env` file:
```bash
# Add these lines to your .env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=weather_bot_routing
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
```

### Step 3: Initialize Database Schema

Run the initialization script:

```bash
# Activate your conda environment
conda activate weather

# Run database initialization
python database/init_db.py
```

Expected output:
```
============================================================
Graph Database Initialization
============================================================

🔌 Connection: postgres@localhost:5432
📦 Creating database 'weather_bot_routing'...
✅ Database 'weather_bot_routing' created successfully
📄 Reading schema from C:\...\schema.sql
🔨 Executing schema...
✅ Schema executed successfully

🔍 Verifying extensions...
  ✅ PostGIS installed: 3.x.x
  ✅ pgRouting installed: 3.x.x

🔍 Verifying tables...
  ✅ Table 'places' exists (10 rows)
  ✅ Table 'nodes' exists (0 rows)
  ✅ Table 'edges' exists (0 rows)

📊 Graph Statistics:
  Places: 10
  Nodes: 0 (Access: 0, Intermediate: 0)
  Edges: 0
  Total Road Distance: 0 km

============================================================
✅ Database initialization completed successfully!
============================================================
```

## Usage

### Using Graph-Powered Routes

The bot now has TWO route commands:

1. **`/route`** - Original OSRM/Overpass-based routing (always uses external APIs)
2. **`/graph_route`** - NEW graph-powered routing with intelligent caching

#### Example: Graph Route

```
User: /graph_route
Bot: 🚗 Route Finder (Graph-Powered)
     📍 Send starting city:

User: Tehran
Bot: ✅ Start: Tehran
     🎯 Send destination:

User: Isfahan  
Bot: ✅ Dest: Isfahan
     ⏰ Departure time (HH:MM):

User: 08:00
Bot: ✅ Time: 08:00
     🚗 Fast route (1) or with traffic (2)?

User: 1
Bot: 🗺️ Checking graph database...
     🌍 Cache Miss (External API)
     🔍 Finding places along route...
     🌤️ Getting weather for 150 places...
     
     🛣️ Tehran ➝ Isfahan
     📏 420km ⏱️ ~5.2h
     ⚡ Ideal time
     🔄 Graph: Cache Miss (External API)
     ☁️ Clear weather expected along route
     
     📍 Cities:
     1. 🚩 Tehran (08:00) 12°C
     2. 🔹 Qom (09:15) 14°C
     3. 🔹 Kashan (10:30) 16°C
     4. 🏁 Isfahan (13:12) 18°C
     ...
```

**Second time (same route):**
```
User: /graph_route
... (same input)

Bot: 🗺️ Checking graph database...
     💎 Cache Hit
     🔍 Finding places along route...
     
     🛣️ Tehran ➝ Isfahan
     📏 420km ⏱️ ~5.1h
     ⚡ Ideal time
     🔄 Graph: 💎 Cache Hit  ← FAST! No OSRM call
     ☁️ Rain (2 segments)
     ...
```

### Architecture Components

The routing system consists of these modules:

1. **`graph_database.py`** - Connection pool manager
2. **`graph_routing_engine.py`** - Pathfinding with pgRouting
3. **`graph_builder.py`** - Cache miss handling, place management
4. **`graph_injector.py`** - Injects OSRM data into graph
5. **`weather_overlay.py`** - Dynamic weather adjustments
6. **`graph_route_service.py`** - High-level orchestration
7. **`graph_route_handler.py`** - Telegram bot integration

### Monitoring Graph Growth

Check database stats:

```python
from core.graph_database import graph_db
import asyncio

async def check_stats():
    await graph_db.initialize()
    stats = await graph_db.get_graph_stats()
    print(f"Places: {stats['total_places']}")
    print(f"Nodes: {stats['total_nodes']}")
    print(f"Edges: {stats['total_edges']}")
    print(f"Road Distance: {stats['total_road_km']:.1f} km")

asyncio.run(check_stats())
```

Or directly in PostgreSQL:
```sql
SELECT * FROM graph_stats;

SELECT * FROM places_with_nodes;
```

## Troubleshooting

### PostgreSQL connection failed

**Error:** `asyncpg.exceptions.InvalidCatalogNameError: database "weather_bot_routing" does not exist`

**Solution:** Run `python database/init_db.py` to create the database.

---

**Error:** `asyncpg.exceptions.UndefinedFunctionError: function postgis_version() does not exist`

**Solution:** PostGIS not installed. Install with:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;
```

---

### Graph database not available warning

If you see:
```
⚠️ Graph database not available: [connection error]
  Route caching will use file-based fallback
```

The bot will still work using the original file-based cache, but won't benefit from graph caching. Check PostgreSQL is running and credentials in `.env` are correct.

### Performance Expectations

- **First query (cache miss):** ~40-60 seconds (same as before - queries OSRM + Overpass + Weather)
- **Repeat query (cache hit):** ~5-10 seconds (only weather fetch, no OSRM/Overpass)
- **Graph growth:** Linear with unique routes queried

## Future Enhancements

Possible improvements:
1. Pre-populate graph with major highway routes
2. Store place names in graph to avoid Overpass queries on cache hits
3. Implement "split point" logic for optimal branch selection
4. Add route alternatives using pgRouting's k-shortest paths
5. Periodic graph optimization (remove rarely-used edges)

## Support

For issues or questions, check:
- PostgreSQL logs: `/var/log/postgresql/`
- Bot logs: Check console output when running `python main.py`
- Database connection: Try `psql -U postgres -d weather_bot_routing`
