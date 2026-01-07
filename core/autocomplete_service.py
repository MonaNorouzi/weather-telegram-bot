# core/autocomplete_service.py
"""Autocomplete Service - Resolves user input to specific Place IDs.

This service implements the "Identity Layer" requirement:
"The bot never searches by raw string. User input is resolved to a place_id 
via an autocomplete service before reaching the backend."
"""

import logging
from typing import List, Dict, Optional
from core.graph_database import graph_db

class AutocompleteService:
    """Provides autocomplete search for places."""
    
    async def search_places(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for places matching the query string.
        
        Args:
            query: User input string (e.g., "Teh", "Mashhad")
            limit: Maximum number of results
            
        Returns:
            List of dicts with {id, name, type, province, country}
        """
        if not query or len(query) < 2:
            return []
            
        async with graph_db.acquire() as conn:
            # Multi-strategy search:
            # 1. Exact match (highest priority)
            # 2. Starts with (high priority)
            # 3. Contains (lower priority)
            # 4. Fuzzy match (lowest priority, via pg_trgm if available, or ILIKE)
            
            # Simple ILIKE implementation for now
            # Order by:
            # - Exact match
            # - Starts with
            # - Population/importance (if we had that metadata)
            # - Alphabetical
            
            rows = await conn.fetch("""
                SELECT 
                    place_id, 
                    name, 
                    place_type, 
                    province,
                    country,
                    ST_Y(center_geom::geometry) as lat,
                    ST_X(center_geom::geometry) as lon,
                    boundary_geom IS NOT NULL as has_boundary
                FROM places
                WHERE name ILIKE $1 || '%'
                ORDER BY 
                    CASE WHEN name ILIKE $1 THEN 0 ELSE 1 END,
                    place_type = 'city' DESC, -- Prefer cities over villages
                    name ASC
                LIMIT $2
            """, query, limit)
            
            results = []
            for row in rows:
                results.append({
                    "id": row['place_id'],
                    "name": row['name'],
                    "type": row['place_type'],
                    "province": row['province'],
                    "country": row['country'],
                    "lat": row['lat'],
                    "lon": row['lon'],
                    "has_boundary": row['has_boundary']
                })
                
            return results
    
    async def get_place_by_id(self, place_id: int) -> Optional[Dict]:
        """Get place details by ID."""
        async with graph_db.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    place_id, name, place_type, province, country,
                    ST_Y(center_geom::geometry) as lat,
                    ST_X(center_geom::geometry) as lon
                FROM places
                WHERE place_id = $1
            """, place_id)
            
            if row:
                return dict(row)
            return None

# Global instance
autocomplete_service = AutocompleteService()
