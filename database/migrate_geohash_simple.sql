-- Simple Enterprise Migration: Add Geohash Columns
-- No complex features, just the essentials

\timing on

-- Add geohash columns
ALTER TABLE places ADD COLUMN IF NOT EXISTS geohash VARCHAR(12);
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS geohash VARCHAR(12);

-- Add comments
COMMENT ON COLUMN places.geohash IS 'Geohash precision 6 (~610m) for fast proximity searches';
COMMENT ON COLUMN nodes.geohash IS 'Geohash precision 7 (~76m) for fast node matching';

-- Show results
SELECT
    'places' as table_name,
    COUNT(*) as total_rows,
    COUNT(geohash) as with_geohash
FROM places
UNION ALL
SELECT
    'nodes' as table_name,
    COUNT(*) as total_rows,
    COUNT(geohash) as with_geohash
FROM nodes;

\echo 'Migration complete! Now run: python scripts/backfill_geohashes.py'
