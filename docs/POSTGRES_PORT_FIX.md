# PostgreSQL Port Fix - SOLVED!

## Problem Found ✅
Your PostgreSQL is configured to use **port 5433** instead of the standard 5432.

```
listen_addresses = '*'  ✅ Correct
port = 5433            ⚠️ Non-standard port
```

---

## QUICK FIX (Recommended)

### Update Your `.env` File

**Location:** `c:\Users\Mona\weather_yob\.env`

**Add or update this line:**
```env
POSTGRES_PORT=5433
```

**Complete .env should have:**
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=weather_bot_routing
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
```

---

## Test It Works

```bash
# Test connection (use -p 5433)
psql -h localhost -p 5433 -U postgres -c "SELECT 1;"

# If that works, run migrations:
psql -h localhost -p 5433 -U postgres -d weather_bot_routing -f database/migrate_weather_cache.sql

# Run quick start
python scripts/quick_start.py

# Start your bot!
python main.py
```

---

## Alternative: Change PostgreSQL to Port 5432

Only if you really want the standard port:

1. Edit `C:\Program Files\PostgreSQL\17\data\postgresql.conf`
2. Line 64: Change `port = 5433` to `port = 5432`
3. Restart: `net stop postgresql-x64-17` then `net start postgresql-x64-17`
4. Keep `.env` with `POSTGRES_PORT=5432`

---

## You're Almost There! 🎉

Once .env is updated, everything will work perfectly!
