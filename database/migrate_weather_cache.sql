-- ============================================================================
-- Weather Cache Table for Temporal Slotting
-- ============================================================================
-- High-precision weather caching with:
-- - Temporal slotting (geohash7 + hour + model_run)
-- - Dynamic TTL (expires at top-of-hour, local time)
-- - Model synchronization
-- - O(1) lookups via B-Tree index
--
-- Run with:
-- psql -U postgres -d weather_bot_routing -f database/migrate_weather_cache.sql
-- ============================================================================

\timing on
\set ON_ERROR_STOP on

BEGIN;

-- Create weather cache table
CREATE TABLE IF NOT EXISTS weather_cache (
    cache_key VARCHAR(50) PRIMARY KEY,           -- geohash7_YYYYMMDDHH_modelrun
    geohash VARCHAR(12) NOT NULL,                -- For spatial queries/invalidation
    forecast_hour TIMESTAMP NOT NULL,            -- Forecast time
    model_run_time VARCHAR(30),                  -- Model run timestamp (for invalidation)
    weather_data JSONB NOT NULL,                 -- Actual forecast data
    created_at TIMESTAMP DEFAULT NOW(),          -- When cached
    expires_at TIMESTAMP NOT NULL,               -- Dynamic TTL
    
    -- Metadata
    CONSTRAINT valid_expires CHECK (expires_at > created_at)
);

COMMENT ON TABLE weather_cache IS 'Temporal weather cache with dynamic TTL and model synchronization';
COMMENT ON COLUMN weather_cache.cache_key IS 'Unique key: geohash7_YYYYMMDDHH_modelrun';
COMMENT ON COLUMN weather_cache.geohash IS 'Geohash7 for spatial indexing and invalidation';
COMMENT ON COLUMN weather_cache.expires_at IS 'Expires at top-of-next-hour (local timezone)';
COMMENT ON COLUMN weather_cache.model_run_time IS 'Model run time from API (for cache invalidation)';

COMMIT;

-- ============================================================================
-- Create Indexes (CONCURRENTLY - Zero Downtime)
-- ============================================================================

-- Primary O(1) lookup by cache key
-- Note: Already created via PRIMARY KEY, but documenting for clarity
-- CREATE UNIQUE INDEX idx_weather_cache_key ON weather_cache(cache_key); -- Implicit from PK

-- Geohash + forecast_hour for spatial-temporal queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weather_cache_geohash_hour 
ON weather_cache(geohash, forecast_hour);

-- Expires_at for cleanup queries (simple index, no predicate)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weather_cache_expires 
ON weather_cache(expires_at);

-- Geohash for model invalidation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weather_cache_geohash 
ON weather_cache(geohash);

-- ============================================================================
-- Create Cleanup Function (Automatic Expired Entry Removal)
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION cleanup_expired_weather_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM weather_cache
    WHERE expires_at < NOW();
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    IF deleted_count > 0 THEN
        RAISE NOTICE 'Cleaned up % expired weather cache entries', deleted_count;
    END IF;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_weather_cache IS 'Remove expired cache entries - run periodically';

COMMIT;

-- ============================================================================
-- Sample Queries (For Testing)
-- ============================================================================

-- Check cache statistics
SELECT 
    COUNT(*) as total_entries,
    COUNT(*) FILTER (WHERE expires_at > NOW()) as active_entries,
    COUNT(*) FILTER (WHERE expires_at <= NOW()) as expired_entries,
    pg_size_pretty(pg_total_relation_size('weather_cache')) as table_size
FROM weather_cache;

-- Find most cached geohashes
SELECT 
    geohash,
    COUNT(*) as cache_count,
    MAX(created_at) as last_cached
FROM weather_cache
WHERE expires_at > NOW()
GROUP BY geohash
ORDER BY cache_count DESC
LIMIT 10;

RAISE NOTICE '✅ Weather cache table created successfully';
RAISE NOTICE 'Next steps:';
RAISE NOTICE '1. Integrate temporal_weather_cache.py into openmeteo_service.py';
RAISE NOTICE '2. Test with concurrent requests';
RAISE NOTICE '3. Monitor cache hit rates';
