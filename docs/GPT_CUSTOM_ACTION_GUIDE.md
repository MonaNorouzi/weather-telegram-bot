# GPT Custom Action API Guide

## 🎯 Overview

This guide explains how to deploy and configure the Weather Route Planning API as a **Custom Action for OpenAI GPTs**. The API provides weather forecasts for road trips using H3-based segment caching.

## 📦 What You Built

A production-ready FastAPI backend that:
- **Routes**: Uses Mapbox API (with OSRM fallback) for routing
- **Weather**: Fetches forecasts using existing H3 weather router
- **Caching**: Redis-backed cache for sub-second responses
- **Safety**: Rate limiting, circuit breakers, input validation
- **Deployment**: Optimized for Render.com free tier (512MB RAM)

---

## 🚀 Quick Start

### 1. Get API Keys

**Mapbox** (Required):
1. Create account: https://account.mapbox.com/
2. Get access token: https://account.mapbox.com/access-tokens/
3. Free tier: 100,000 requests/month

**OpenWeather** (Already have):
- Use your existing `OPENWEATHER_API_KEY`

### 2. Update `.env` File

Add to your existing `.env`:

```bash
# GPT Custom Action Configuration
MAPBOX_API_KEY=pk.your_actual_mapbox_key_here
RATE_LIMIT_PER_MINUTE=10
ROUTING_TIMEOUT_SECONDS=30
WEATHER_TIMEOUT_SECONDS=15
```

### 3. Install API Dependencies

```powershell
cd c:\Users\Mona\weather_yob
pip install -r requirements.api.txt
```

### 4. Test Locally

```powershell
# Start Redis (if not running)
# Option A: Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option B: Use your existing Redis

# Start FastAPI
uvicorn api.main:app --reload --port 8000
```

Open browser: http://localhost:8000/docs (Swagger UI)

### 5. Test Health Endpoint

```powershell
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "redis": "connected",
  "timestamp": "2026-01-01T20:30:00Z"
}
```

### 6. Test Route Weather Endpoint

```powershell
curl -X POST http://localhost:8000/route-weather `
  -H "Content-Type: application/json" `
  -d '{
    "origin": {"lat": 35.6892, "lon": 51.3890, "name": "Tehran"},
    "destination": {"lat": 36.2974, "lon": 59.6067, "name": "Mashhad"}
  }'
```

---

## ☁️ Deploy to Render.com

### Option A: One-Click Deploy (Recommended)

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add GPT Custom Action API"
   git push origin main
   ```

2. **Connect to Render**:
   - Go to: https://dashboard.render.com
   - Click "New" → "Blueprint"
   - Connect your GitHub repo
   - Render will auto-detect `render.yaml`

3. **Set Environment Variables**:
   - Render will prompt for `MAPBOX_API_KEY`
   - Add `OPENWEATHER_API_KEY` if needed
   - Other vars are pre-configured in `render.yaml`

4. **Deploy**:
   - Click "Apply"
   - Wait ~5 minutes for build

### Option B: Manual Deploy

1. **Create Web Service**:
   - Dashboard → New → Web Service
   - Connect GitHub repo
   - Name: `weather-gpt-api`
   - Environment: Docker
   - Dockerfile path: `./Dockerfile.api`
   - Plan: Free

2. **Add Redis**:
   - Dashboard → New → Redis
   - Name: `redis-cache`
   - Plan: Free (25MB)

3. **Link Services**:
   - In web service settings → Environment
   - Add `REDIS_HOST`, `REDIS_PORT` from Redis service

---

## 🔗 Configure GPT Custom Action

### 1. Export OpenAPI Spec

After deploying:

```powershell
cd c:\Users\Mona\weather_yob
python scripts\export_openapi.py
```

This creates `openapi.json`.

### 2. Update Server URL

Edit `openapi.json`, find:
```json
"servers": [
  {
    "url": "https://weather-gpt-api.onrender.com"
  }
]
```

Replace with your actual Render URL.

### 3. Create GPT

1. Go to: https://chat.openai.com/gpts/editor
2. Click "Create a GPT"
3. Configure:
   - **Name**: Weather Route Planner
   - **Description**: "Get detailed weather forecasts for road trips"
   - **Instructions**: 
     ```
     You are a route weather planning assistant. When users ask about weather 
     on a route, use the Weather Route Planning API to get real-time forecasts 
     for each segment of their journey. Present the information in a clear, 
     user-friendly format.
     ```

4. **Add Action**:
   - Go to "Actions" tab
   - Click "Create new action"
   - Import from file → Upload `openapi.json`
   - Authentication: None (or API Key if you set `GPT_API_KEY`)

### 4. Test in GPT

Try asking:
```
"What's the weather like driving from Tehran to Mashhad tomorrow morning?"
```

GPT should call your API and present weather segments.

---

## 🏗️ Architecture Explanation

### Why FastAPI + Mapbox + Redis?

#### FastAPI vs Flask/Django

| Feature | FastAPI | Flask | Django |
|---------|---------|-------|--------|
| **OpenAPI auto-generation** | ✅ Built-in | ❌ Manual | ❌ Manual |
| **Type validation** | ✅ Pydantic | ❌ Manual | ⚠️ DRF only |
| **Async support** | ✅ Native | ⚠️ Limited | ⚠️ Limited |
| **Performance** | 🚀 Fast | 🐌 Slower | 🐌 Slower |

**Winner**: FastAPI - GPT needs OpenAPI spec, and async handles I/O-heavy APIs.

#### Mapbox vs Self-Hosted OSRM

For GPT Custom Actions specifically:

| Scenario | OSRM (512MB) | Mapbox API |
|----------|--------------|------------|
| **Cold start** | ❌ 30s+ to load OSM | ✅ Instant |
| **Burst traffic** | ❌ May OOM | ✅ Auto-scales |
| **Maintenance** | ⚠️ Manual updates | ✅ Zero effort |
| **Free tier** | Unlimited (self-host) | 100K req/month |

**Verdict**: For unpredictable GPT traffic, Mapbox reliability > self-hosting.

**But**: Keep OSRM for your Telegram bot (you control traffic).

#### Redis as Cache Layer

| Operation | PostgreSQL | Redis |
|-----------|-----------|-------|
| 50 H3 cell lookups | 50 queries × 50ms = 2.5s | 1 MGET × 1ms = 1ms |
| Memory (512MB) | ~200MB overhead | ~25MB data only |
| Cache eviction | Manual | Auto LRU |

**Redis enables** API on free tier!

---

## 🧪 Testing

### Manual Testing

1. **Health Check**:
   ```powershell
   curl https://your-app.onrender.com/health
   ```

2. **Route Weather**:
   ```powershell
   curl -X POST https://your-app.onrender.com/route-weather `
     -H "Content-Type: application/json" `
     -d '{"origin":{"lat":35.69,"lon":51.39},"destination":{"lat":36.30,"lon":59.61}}'
   ```

3. **Cache Stats** (admin):
   ```powershell
   curl https://your-app.onrender.com/stats
   ```

### Automated Tests

```powershell
pytest tests/test_api.py -v
```

### Load Testing

```powershell
# Test rate limiting
for ($i=0; $i -lt 12; $i++) {
    curl https://your-app.onrender.com/health
}
# 11th+ should return 429
```

---

## 📊 Monitoring

### Render Dashboard

- **Metrics**: CPU, Memory, Response time
- **Logs**: Real-time logs
- **Alerts**: Set up email notifications

### Key Metrics to Watch

1. **Memory Usage**: Should stay <400MB
2. **Response Time**: Target <3s for routes
3. **Error Rate**: Target <1%
4. **Cache Hit Rate**: Target >80% (check `/stats`)

---

## 🔧 Troubleshooting

### API Returns 503

**Cause**: Mapbox + OSRM both failing
**Fix**: 
1. Check Mapbox quota: https://account.mapbox.com/
2. Test OSRM fallback: `curl http://localhost:5000/`

### High Memory Usage

**Cause**: Too many parallel requests
**Fix**: Reduce `PARALLEL_WEATHER_REQUESTS` in .env

### Slow Responses

**Cause**: Cache misses
**Fix**: 
1. Check Redis: `curl http://localhost:8000/stats`
2. Increase `H3_WEATHER_CACHE_TTL`

### Rate Limit Errors

**Cause**: Exceeding 10 req/min
**Fix**: Increase `RATE_LIMIT_PER_MINUTE` for premium users

---

## 🔐 Security Best Practices

### Production Checklist

- [x] No hardcoded API keys
- [x] CORS restricted to GPT domains
- [x] Rate limiting enabled
- [x] Input validation with Pydantic
- [ ] Optional: Add `GPT_API_KEY` authentication
- [ ] Optional: Set up monitoring alerts

### Add API Authentication (Optional)

1. Generate API key:
   ```python
   import secrets
   print(secrets.token_urlsafe(32))
   ```

2. Add to `.env`:
   ```bash
   GPT_API_KEY=your_secret_key_here
   ```

3. Update GPT Action:
   - Authentication: API Key
   - Header name: `X-API-Key`
   - Value: Your key

---

## 📈 Scaling

### If Traffic Grows

1. **Upgrade Render Plan**:
   - Free → Starter ($7/mo): 512MB → 1GB RAM
   - Add multiple workers in Dockerfile

2. **Optimize Cache**:
   - Increase Redis to paid plan (256MB)
   - Use longer TTLs for stable weather

3. **CDN for Static Routes**:
   - Cache common routes (Tehran → Mashhad)
   - Use Cloudflare Workers

---

## 🆘 Support

### Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Mapbox API**: https://docs.mapbox.com/api/navigation/
- **Render Docs**: https://render.com/docs
- **OpenAI Actions**: https://platform.openai.com/docs/actions

### Community

- FastAPI Discord: https://discord.gg/fastapi
- Reddit: r/FastAPI, r/ChatGPT

---

## 📝 Example GPT Prompts

Train your GPT with these examples:

**User**: "I'm driving from Tehran to Shiraz tomorrow. What's the weather?"
**GPT**: Calls API → "Your 950 km journey will take about 10 hours. Here's the weather forecast..."

**User**: "Best time to leave for Isfahan this week?"
**GPT**: Calls API multiple times → "Based on weather data, Tuesday 8 AM has the clearest conditions..."

---

## 🎉 You're Done!

Your GPT Custom Action is live! Users can now get weather forecasts for any route through ChatGPT.

**Next Steps**:
1. Share your GPT with friends
2. Monitor usage in Render dashboard
3. Optimize based on metrics

Happy building! 🚀
