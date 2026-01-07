# Quick Redis Setup for Windows (Without Docker)

## Option A: Install Redis via MSI (Easiest - 5 minutes)

### Step 1: Download Redis
1. Go to: https://github.com/tporadowski/redis/releases
2. Download latest `Redis-x64-*.msi` (e.g., `Redis-x64-5.0.14.1.msi`)
3. Run installer
4. Keep default settings
5. Check "Add to PATH"

### Step 2: Start Redis Service
```powershell
# Redis should auto-start as a Windows service
# To verify:
redis-cli ping
# Should return: PONG
```

### Step 3: Test API
```powershell
uvicorn api.main:app --reload --port 8000
```

---

## Option B: Use Memurai (Redis for Windows - Free)

### Step 1: Download Memurai
1. Go to: https://www.memurai.com/get-memurai
2. Download free developer edition
3. Install (auto-starts as service)

### Step 2: Configure
Memurai is 100% Redis-compatible, no config changes needed!

### Step 3: Test
```powershell
redis-cli ping
# Should return: PONG
```

---

## Option C: Test API Without Redis (Temporary)

The API will work without Redis, just without caching:

### What happens?
- ✅ API still works
- ✅ All features functional
- ❌ No caching (slower responses)
- ❌ Rate limiting uses in-memory only

### How to test
Just start the API:
```powershell
uvicorn api.main:app --reload --port 8000
```

Health check will show:
```json
{
  "status": "healthy",
  "redis": "disconnected",  // ⚠️ Warning but not critical
  "timestamp": "..."
}
```

Route weather endpoint will still work, just slower!

---

## Option D: Install Docker Desktop (For Future Use)

### Step 1: Download Docker Desktop
1. Go to: https://www.docker.com/products/docker-desktop
2. Download for Windows
3. Install (requires restart)
4. Enable WSL 2 if prompted

### Step 2: Start Redis
```powershell
docker run -d -p 6379:6379 redis:7-alpine
```

**Pros**: Industry standard, good for development  
**Cons**: Large download (~500MB), requires virtualization

---

## 🚀 Quick Decision Guide

**I just want to test the API NOW**:
→ Use **Option C** (No Redis)

**I want proper setup (5 min)**:
→ Use **Option A** (Redis MSI installer)

**I want professional setup**:
→ Use **Option D** (Docker Desktop)

**I'm on a corporate machine (blocked downloads)**:
→ Use **Option C** and deploy to Render (uses cloud Redis)

---

## Testing Commands

After Redis is running (or skip it):

```powershell
# Start API
uvicorn api.main:app --reload --port 8000

# Test health (new terminal)
curl http://localhost:8000/health

# Test route weather
curl -X POST http://localhost:8000/route-weather `
  -H "Content-Type: application/json" `
  -d '{\"origin\":{\"lat\":35.69,\"lon\":51.39},\"destination\":{\"lat\":36.30,\"lon\":59.61}}'
```

---

## Troubleshooting

### Redis won't start?
```powershell
# Check if port 6379 is in use
netstat -ano | findstr :6379

# If blocked, kill process
taskkill /PID <process_id> /F
```

### API says "Redis disconnected" but I installed Redis?
```powershell
# Test Redis directly
redis-cli ping
# Should return: PONG

# Check Redis is on port 6379
netstat -ano | findstr :6379
```

### Can't install anything?
Use **Option C** (no Redis) for local testing, then deploy to Render which includes managed Redis!
