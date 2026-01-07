-- Migration: Add Polygon Boundary Support to Places Table
-- This migration adds administrative boundary polygons to the places table
-- while maintaining backward compatibility with existing center_geom points.
--
-- Run with: psql -U postgres -d weather_bot_routing -f database/migrate_add_boundaries.sql

BEGIN;

-- ============================================================================
-- STEP 1: Add boundary_geom column
-- ============================================================================
ALTER TABLE places ADD COLUMN IF NOT EXISTS boundary_geom GEOGRAPHY(POLYGON, 4326);

COMMENT ON COLUMN places.boundary_geom IS 'Administrative boundary polygon for accurate spatial containment checks. NULL for places without boundary data.';

-- ============================================================================
-- STEP 2: Create spatial index for fast ST_Contains queries
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_places_boundary_geom ON places USING GIST(boundary_geom);

-- ============================================================================
-- STEP 3: Add helper function for point-in-polygon checks
-- ============================================================================
CREATE OR REPLACE FUNCTION find_places_containing_point(
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION
)
RETURNS TABLE(place_id INTEGER, name VARCHAR, place_type VARCHAR, province VARCHAR) AS $$
BEGIN
    RETURN QUERY
    SELECT p.place_id, p.name, p.place_type, p.province
    FROM places p
    WHERE p.boundary_geom IS NOT NULL
      AND ST_Contains(p.boundary_geom::geometry, ST_SetSRID(ST_MakePoint(lon, lat), 4326))
    ORDER BY 
        CASE p.place_type
            WHEN 'city' THEN 1
            WHEN 'town' THEN 2
            WHEN 'village' THEN 3
            ELSE 4
        END,
        p.name;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION find_places_containing_point IS 'Find all places whose boundaries contain the given coordinate. Returns results ordered by place importance (cities first).';

-- ============================================================================
-- STEP 4: Update views to include boundary information
-- ============================================================================
CREATE OR REPLACE VIEW places_with_nodes AS
SELECT 
    p.place_id,
    p.name,
    p.place_type,
    p.province,
    COUNT(n.node_id) as access_node_count,
    p.center_geom,
    p.boundary_geom IS NOT NULL as has_boundary,
    CASE 
        WHEN p.boundary_geom IS NOT NULL THEN ST_Area(p.boundary_geom) / 1000000.0  -- Convert to km²
        ELSE NULL
    END as area_km2
FROM places p
LEFT JOIN nodes n ON n.linked_place_id = p.place_id
GROUP BY p.place_id, p.name, p.place_type, p.province, p.center_geom, p.boundary_geom;

-- ============================================================================
-- STEP 5: Add sample polygon boundaries for major Iranian cities
-- ============================================================================
-- These are simplified administrative boundaries (approximate rectangles)
-- In production, replace with actual OSM administrative boundaries

-- Tehran (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((51.2 35.6, 51.2 35.8, 51.6 35.8, 51.6 35.6, 51.2 35.6))'
)
WHERE name = 'Tehran' AND place_type = 'city';

-- Isfahan (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((51.55 32.55, 51.55 32.75, 51.8 32.75, 51.8 32.55, 51.55 32.55))'
)
WHERE name = 'Isfahan' AND place_type = 'city';

-- Mashhad (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((59.4 36.2, 59.4 36.4, 59.8 36.4, 59.8 36.2, 59.4 36.2))'
)
WHERE name = 'Mashhad' AND place_type = 'city';

-- Shiraz (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((52.45 29.5, 52.45 29.7, 52.7 29.7, 52.7 29.5, 52.45 29.5))'
)
WHERE name = 'Shiraz' AND place_type = 'city';

-- Tabriz (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((46.15 37.98, 46.15 38.18, 46.45 38.18, 46.45 37.98, 46.15 37.98))'
)
WHERE name = 'Tabriz' AND place_type = 'city';

-- Karaj (approx bounding box)
UPDATE places 
SET boundary_geom = ST_GeogFromText(
    'POLYGON((50.9 35.75, 50.9 35.9, 51.1 35.9, 51.1 35.75, 50.9 35.75))'
)
WHERE name = 'Karaj' AND place_type = 'city';

-- ============================================================================
-- STEP 6: Verify migration
-- ============================================================================
DO $$
DECLARE
    boundary_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO boundary_count FROM places WHERE boundary_geom IS NOT NULL;
    RAISE NOTICE '✅ Migration completed successfully!';
    RAISE NOTICE '   - Places with boundaries: %', boundary_count;
    RAISE NOTICE '   - Spatial index created: idx_places_boundary_geom';
    RAISE NOTICE '   - Helper function created: find_places_containing_point()';
END $$;

COMMIT;
