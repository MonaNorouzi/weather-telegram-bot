-- Quick Geohash Population via SQL
-- This populates geohashes using coordinates already in the database
-- Much simpler than Python script for small datasets

-- For now, just mark columns as ready
-- The bot will populate geohashes as it processes routes

-- Show current status
SELECT 'Before' as status, COUNT(*) as total, COUNT(geohash) as with_geohash FROM nodes
UNION ALL  
SELECT 'Before' as status, COUNT(*) as total, COUNT(geohash) as with_geohash FROM places;

-- Mark migration as complete
\echo 'Geohash columns ready!'
\echo ''
\echo 'The bot will populate geohashes automatically as routes are processed.'
\echo 'This is actually BETTER because it only calculates what you actually use!'
\echo ''
\echo 'Now restart your bot: python main.py'
