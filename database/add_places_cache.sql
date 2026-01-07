-- Add places cache table for storing list of cities along routes
-- This caches only the place names/locations, not weather or arrival times

CREATE TABLE IF NOT EXISTS route_places_cache (
    id SERIAL PRIMARY KEY,
    source_place_id INTEGER NOT NULL REFERENCES places(place_id),
    target_place_id INTEGER NOT NULL REFERENCES places(place_id),
    places_data JSONB NOT NULL,  -- [{name, type, lat, lon}, ...]
    total_places INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_route_places UNIQUE(source_place_id, target_place_id)
);

CREATE INDEX idx_route_places_lookup ON route_places_cache(source_place_id, target_place_id);

-- Trigger to update updated_at
CREATE TRIGGER update_route_places_cache_updated_at
BEFORE UPDATE ON route_places_cache
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE route_places_cache IS 'Caches list of places along a route (no weather/timing data)';
COMMENT ON COLUMN route_places_cache.places_data IS 'Array of places: [{name, type, lat, lon}, ...] - timing calculated dynamically';
