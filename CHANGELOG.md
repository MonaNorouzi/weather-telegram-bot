# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-04

### Added
- **H3 Hexagonal Caching System**: Intelligent weather caching using Uber's H3 spatial indexing
  - 90%+ cache hit rate on repeated queries
  - Sub-second response times for cached routes
  - Automatic geographic reuse across different routes
- **GPT Custom Action API**: FastAPI backend for ChatGPT integration
  - Mapbox routing with OSRM fallback
  - Rate limiting and circuit breakers
  - OpenAPI documentation
- **Connection Pooling**: Fixed SSL timeout issues with proper aiohttp connector configuration
- **Performance Optimizations**: 
  - Reduced verbose logging (11k lines → <100 lines per route)
  - Optimized places discovery sampling (15km → 20km for long routes)
  - Parallel weather requests balancing (40 concurrent)
- **Documentation**: Comprehensive guides for H3 architecture, caching system, and GPT integration

### Changed
- **Weather Summary Generation**: Fixed structure mismatch in H3 data extraction
- **Places Discovery**: Reduced API load through smarter sampling intervals
- **Overpass Concurrency**: Reduced from 2 to 1 to avoid rate limiting
- **README**: Complete rewrite with professional formatting and detailed setup instructions

### Fixed
- **Critical**: aiohttp ClientSession exhaustion causing SSL timeouts
- **Weather Summary**: "Weather data unavailable" bug with correct H3 data access
- **Temporal Cache Logging**: Removed excessive debug output
- **Singleflight Timeout**: Increased from 30s to 60s for API delays

### Security
- **Secrets Management**: Comprehensive .gitignore for sensitive files
- **Session Protection**: Telethon session files excluded from repository
- **Environment Variables**: All credentials moved to .env file

## [2.0.0] - 2025-12-XX

### Added
- PostgreSQL + pgRouting graph-based routing
- Redis two-layer caching system
- Telegram bot with route planning
- Admin dashboard and commands
- Scheduled weather notifications

### Initial Release
- Basic weather queries
- City-to-city routing
- Integration with Open-Meteo API

---

[2.1.0]: https://github.com/MonaNorouzi/weather-telegram-bot/releases/tag/v2.1.0
[2.0.0]: https://github.com/MonaNorouzi/weather-telegram-bot/releases/tag/v2.0.0
