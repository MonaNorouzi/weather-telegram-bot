# PostgreSQL Troubleshooting Guide for Windows

## Current Issue
PostgreSQL service shows as "Running" but not accepting TCP/IP connections on port 5432.

## Quick Diagnosis Steps

### Step 1: Check Service Status
```powershell
Get-Service postgresql-x64-17
```

### Step 2: Check if PostgreSQL is Listening
```powershell
netstat -ano | findstr :5432
```
**Expected:** Should show `LISTENING` on port 5432  
**If empty:** PostgreSQL not listening = configuration issue

### Step 3: Check PostgreSQL Logs
```powershell
Get-Content "C:\Program Files\PostgreSQL\17\data\log\*.log" -Tail 50
```
Look for errors about:
- Port conflicts
- Configuration errors
- Permission issues

---

## Fix #1: Verify Configuration Files

### A. Check `postgresql.conf`

**Location:** `C:\Program Files\PostgreSQL\17\data\postgresql.conf`

**Open as Administrator** and verify these lines are UN-commented:

```conf
listen_addresses = '*'          # Must NOT have # at start
port = 5432                     # Must NOT have # at start
```

**Before (Wrong):**
```conf
#listen_addresses = 'localhost'
#port = 5432
```

**After (Correct):**
```conf
listen_addresses = '*'
port = 5432
```

### B. Check `pg_hba.conf`

**Location:** `C:\Program Files\PostgreSQL\17\data\pg_hba.conf`

**Add or modify this line:**
```conf
host    all             all             127.0.0.1/32            trust
```

Should look like:
```conf
# TYPE  DATABASE        USER            ADDRESS                 METHOD
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
```

---

## Fix #2: Restart PostgreSQL (As Administrator)

**Critical:** Changes only apply after restart!

### Option A: PowerShell (Run as Admin)
```powershell
# Stop service
net stop postgresql-x64-17

# Wait 5 seconds
Start-Sleep -Seconds 5

# Start service
net start postgresql-x64-17

# Check if listening
netstat -ano | findstr :5432
```

### Option B: Services GUI
1. Windows + R → `services.msc`
2. Find `postgresql-x64-17`
3. Right-click → Restart
4. Wait 10 seconds

---

## Fix #3: Check Firewall

**If still not working after restart:**

```powershell
# Allow PostgreSQL through Windows Firewall
New-NetFirewallRule -DisplayName "PostgreSQL" -Direction Inbound -LocalPort 5432 -Protocol TCP -Action Allow
```

---

## Fix #4: Alternative Port Test

**If port 5432 is blocked by another service:**

### Find What's Using Port 5432
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 5432).OwningProcess
```

### Use Different Port (if needed)
Edit `postgresql.conf`:
```conf
port = 5433  # Different port
```

Then update your `.env` file:
```env
POSTGRES_PORT=5433
```

---

## Quick Test After Fix

```bash
# Should work now
psql -h localhost -U postgres -c "SELECT version();"

# Or test with Python
python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('postgresql://postgres@localhost/postgres'))"
```

---

## Common Issues & Solutions

### Issue 1: "Access Denied" when restarting
**Solution:** Run PowerShell as Administrator  
Right-click PowerShell → Run as administrator

### Issue 2: Config changes don't apply
**Solution:** Must restart service after editing files

### Issue 3: Can connect with `psql` but not Python
**Solution:** Check `.env` file has correct credentials:
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=weather_bot_routing
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

### Issue 4: Port already in use
**Solution:** Either kill the other process or use different port

---

## Nuclear Option: Reinstall PostgreSQL

If nothing works:

1. Uninstall PostgreSQL
2. Delete `C:\Program Files\PostgreSQL`
3. Delete `C:\Users\Mona\AppData\Local\PostgreSQL`
4. Reinstall with **"Enable TCP/IP connections" checked**
5. During install, note the password you set

---

## What to Do Right Now

**Try this sequence:**

1. **Open PowerShell as Administrator**
2. **Run these commands:**
```powershell
# Stop PostgreSQL
net stop postgresql-x64-17

# Check config (should show listen_addresses = '*')
Select-String -Path "C:\Program Files\PostgreSQL\17\data\postgresql.conf" -Pattern "listen_addresses"

# Check port (should show port = 5432)
Select-String -Path "C:\Program Files\PostgreSQL\17\data\postgresql.conf" -Pattern "^port"

# Start PostgreSQL
net start postgresql-x64-17

# Wait 10 seconds
Start-Sleep -Seconds 10

# Check if listening
netstat -ano | findstr :5432
```

3. **If you see LISTENING** → Success! ✅
4. **If still not listening** → Check logs:
```powershell
Get-Content "C:\Program Files\PostgreSQL\17\data\log\*.log" -Tail 50
```

---

## Expected Success Output

```
PS> netstat -ano | findstr :5432
  TCP    0.0.0.0:5432           0.0.0.0:0              LISTENING       1234
  TCP    [::]:5432              [::]:0                 LISTENING       1234
```

Then test:
```bash
psql -U postgres -c "SELECT 1;"
```

Should return:
```
 ?column?
----------
        1
(1 row)
```

---

## Next Steps After PostgreSQL Works

1. ✅ Test connection: `psql -U postgres -c "SELECT 1;"`
2. ✅ Run migrations: `psql -U postgres -d weather_bot_routing -f database/migrate_weather_cache.sql`
3. ✅ Run verification: `python scripts/quick_start.py`
4. ✅ Start bot: `python main.py`
5. ✅ Demo your enterprise features! 🚀
