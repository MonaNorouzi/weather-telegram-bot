# core/route_places_cache.py
"""Cache management for places along routes.

This module caches only the list of places (cities, towns) found along a route,
without weather data or arrival times. Weather and timing are calculated dynamically
at query time based on user's departure time.
"""

import logging
import json
from typing import Optional, List, Dict
from core.graph_database import graph_db


class RoutePlacesCache:
    """Manages caching of places along routes."""
    
    async def get_cached_places(
        self,
        source_place_id: int,
        target_place_id: int
    ) -> Optional[List[Dict]]:
        """Get cached list of places for a route.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            
        Returns:
            List of places [{name, type, lat, lon}, ...] or None if not cached
        """
        try:
            async with graph_db.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT places_data, total_places
                    FROM route_places_cache
                    WHERE source_place_id = $1 AND target_place_id = $2
                """, source_place_id, target_place_id)
                
                if row:
                    places_data = row['places_data']
                    
                    # asyncpg returns JSONB as string, need to parse it
                    if isinstance(places_data, str):
                        places_data = json.loads(places_data)
                    
                    logging.info(f"✅ Places cache hit: {row['total_places']} places")
                    return places_data
                else:
                    logging.info(f"❌ Places cache miss")
                    return None
                    
        except Exception as e:
            logging.error(f"Error fetching cached places: {e}")
            return None
    
    async def cache_places(
        self,
        source_place_id: int,
        target_place_id: int,
        places: List[Dict]
    ) -> bool:
        """Cache list of places for a route.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            places: List of places from Overpass [{name, type, lat, lon}, ...]
            
        Returns:
            True if cached successfully
        """
        try:
            # Extract only essential data (no weather, no timing)
            simplified_places = []
            for p in places:
                simplified_places.append({
                    'name': p.get('name', 'Unknown'),
                    'type': p.get('type', 'place'),
                    'lat': p.get('lat'),
                    'lon': p.get('lon')
                })
            
            # Convert to JSON
            places_json = json.dumps(simplified_places)
            
            async with graph_db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO route_places_cache 
                        (source_place_id, target_place_id, places_data, total_places)
                    VALUES ($1, $2, $3::jsonb, $4)
                    ON CONFLICT (source_place_id, target_place_id)
                    DO UPDATE SET
                        places_data = EXCLUDED.places_data,
                        total_places = EXCLUDED.total_places,
                        updated_at = NOW()
                """, source_place_id, target_place_id, places_json, len(simplified_places))
            
            logging.info(f"📦 Cached {len(simplified_places)} places for route {source_place_id} → {target_place_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error caching places: {e}")
            return False
    
    async def clear_cache(self, source_place_id: int = None, target_place_id: int = None):
        """Clear cached places.
        
        Args:
            source_place_id: If provided, clear only for this source
            target_place_id: If provided, clear only for this target
        """
        try:
            async with graph_db.acquire() as conn:
                if source_place_id and target_place_id:
                    await conn.execute("""
                        DELETE FROM route_places_cache
                        WHERE source_place_id = $1 AND target_place_id = $2
                    """, source_place_id, target_place_id)
                    logging.info(f"Cleared cache for route {source_place_id} → {target_place_id}")
                else:
                    await conn.execute("DELETE FROM route_places_cache")
                    logging.info("Cleared all places cache")
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")

# Global instance
route_places_cache = RoutePlacesCache()
