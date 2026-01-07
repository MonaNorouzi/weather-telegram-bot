# core/places_manager.py
"""Manages places (cities, towns, villages) in the database.

This module ensures all discovered places are stored in the places table,
whether they come from user input or Overpass API discoveries.
"""

import logging
from typing import Optional, Dict, List
from core.graph_database import graph_db
from core import geohash_utils
from core.city_normalizer import city_normalizer
from core.overpass_service import overpass_service


class PlacesManager:
    """Manages place entities in the database."""
    
    async def ensure_place_exists(
        self,
        name: str,
        place_type: str,
        coords: tuple,
        province: str = None,
        boundary_coords: List[tuple] = None,
        fetch_boundary: bool = True
    ) -> int:
        """Ensure a place exists in database, create if not.
        
        Args:
            name: Place name
            place_type: city, town, village, hamlet, suburb
            coords: (lat, lon) tuple for center point
            province: Province name (optional)
            boundary_coords: List of (lat, lon) tuples defining polygon boundary (optional)
            fetch_boundary: If True, automatically fetch boundary from Overpass API for cities (default: True)
            
        Returns:
            place_id
        """
        lat, lon = coords
        
        # Normalize city name for consistent database/cache operations
        # This ensures "تهران" and "Tehran" both resolve to "tehran"
        normalized_name = city_normalizer.normalize(name)
        
        # Calculate geohash (precision 6 for places = ~610m)
        geohash = geohash_utils.encode(lat, lon, precision=geohash_utils.PRECISION_PLACE)
        
        try:
            async with graph_db.acquire() as conn:
                # Check if exists using normalized name
                existing = await conn.fetchval("""
                    SELECT place_id FROM places
                    WHERE name = $1 AND place_type = $2
                    LIMIT 1
                """, normalized_name, place_type)
                
                if existing:
                    # Update boundary and geohash if provided
                    if boundary_coords:
                        await self._update_place_boundary(conn, existing, boundary_coords)
                    # Update geohash if NULL
                    await conn.execute("""
                        UPDATE places SET geohash = $1 WHERE place_id = $2 AND geohash IS NULL
                    """, geohash, existing)
                    
                    # Fetch boundary from Overpass if requested and not present
                    if fetch_boundary and place_type in ['city', 'town']:
                        has_boundary = await conn.fetchval(
                            "SELECT boundary_geom IS NOT NULL FROM places WHERE place_id = $1",
                            existing
                        )
                        if not has_boundary:
                            await self._fetch_and_store_boundary(conn, existing, name)
                    
                    return existing
                
                # Create new place with normalized name and geohash
                if boundary_coords and len(boundary_coords) >= 3:
                    # With boundary
                    place_id = await conn.fetchval("""
                        INSERT INTO places (name, place_type, province, center_geom, boundary_geom, geohash)
                        VALUES (
                            $1, $2, $3, 
                            ST_SetSRID(ST_MakePoint($4, $5), 4326),
                            ST_GeogFromText($6),
                            $7
                        )
                        RETURNING place_id
                    """, normalized_name, place_type, province, lon, lat, self._coords_to_wkt_polygon(boundary_coords), geohash)
                    logging.info(f"📍 Created place with boundary+geohash: {name} → {normalized_name} - hash: {geohash}")
                else:
                    # Center point only
                    place_id = await conn.fetchval("""
                        INSERT INTO places (name, place_type, province, center_geom, geohash)
                        VALUES ($1, $2, $3, ST_SetSRID(ST_MakePoint($4, $5), 4326), $6)
                        RETURNING place_id
                    """, normalized_name, place_type, province, lon, lat, geohash)
                    logging.info(f"📍 Created place with geohash: {name} → {normalized_name} - hash: {geohash}")
                    
                    # Fetch boundary from Overpass for cities/towns if requested
                    if fetch_boundary and place_type in ['city', 'town']:
                        await self._fetch_and_store_boundary(conn, place_id, name)
                
                return place_id
                
        except Exception as e:
            logging.error(f"Error ensuring place exists: {e}")
            raise
    
    async def bulk_ensure_places(
        self,
        places_list: List[Dict],
        fetch_boundary: bool = False  # CRITICAL: False by default for performance!
    ) -> Dict[str, int]:
        """Ensure multiple places exist in database.
        
        Args:
            places_list: List of dicts with {name, type, lat, lon}
            fetch_boundary: If True, fetch boundaries from Overpass (SLOW! default: False)
            
        Returns:
            Dict mapping place name to place_id
        """
        result = {}
        
        for place in places_list:
            try:
                place_id = await self.ensure_place_exists(
                    name=place.get('name', 'Unknown'),
                    place_type=place.get('type', 'place'),
                    coords=(place.get('lat'), place.get('lon')),
                    province=place.get('province'),
                    fetch_boundary=fetch_boundary  # Pass through the parameter
                )
                result[place['name']] = place_id
            except Exception as e:
                logging.warning(f"Could not add place {place.get('name')}: {e}")
        
        logging.info(f"✅ Ensured {len(result)} places exist in database")
        return result
    
    def _coords_to_wkt_polygon(self, coords: List[tuple]) -> str:
        """Convert list of (lat, lon) coordinates to WKT POLYGON string.
        
        Args:
            coords: List of (lat, lon) tuples defining polygon boundary
            
        Returns:
            WKT format polygon string, e.g., 'POLYGON((lon1 lat1, lon2 lat2, ...))'
        """
        # PostGIS expects lon, lat order (X, Y)
        # Ensure polygon is closed (first and last point same)
        if coords[0] != coords[-1]:
            coords = coords + [coords[0]]
        
        coord_strings = [f"{lon} {lat}" for lat, lon in coords]
        return f"POLYGON(({', '.join(coord_strings)}))"
    
    async def _update_place_boundary(self, conn, place_id: int, boundary_coords: List[tuple]):
        """Update existing place with boundary geometry.
        
        Args:
            conn: Database connection
            place_id: ID of place to update
            boundary_coords: List of (lat, lon) tuples
        """
        if len(boundary_coords) >= 3:
            await conn.execute("""
                UPDATE places
                SET boundary_geom = ST_GeogFromText($1)
                WHERE place_id = $2
            """, self._coords_to_wkt_polygon(boundary_coords), place_id)
            logging.info(f"🔄 Updated boundary for place_id {place_id}")
    
    async def _fetch_and_store_boundary(self, conn, place_id: int, city_name: str):
        """Fetch city boundary from Overpass API and store in database.
        
        Args:
            conn: Database connection
            place_id: Place ID to update
            city_name: City name to search for
        """
        try:
            logging.info(f"🌍 Fetching boundary for {city_name} from Overpass API...")
            boundary_data = await overpass_service.get_city_boundary(city_name, country="Iran")
            
            if boundary_data and boundary_data.get('coordinates'):
                coords = boundary_data['coordinates']
                if len(coords) >= 3:
                    wkt = self._coords_to_wkt_polygon(coords)
                    await conn.execute("""
                        UPDATE places
                        SET boundary_geom = ST_GeogFromText($1),
                            metadata = jsonb_set(
                                COALESCE(metadata, '{}'),
                                '{osm_id}',
                                to_jsonb($2::text)
                            )
                        WHERE place_id = $3
                    """, wkt, str(boundary_data.get('osm_id', '')), place_id)
                    logging.info(f"✅ Stored boundary for {city_name} ({len(coords)} points, OSM ID: {boundary_data.get('osm_id')})")
                else:
                    logging.warning(f"⚠️ Boundary for {city_name} has too few points: {len(coords)}")
            else:
                logging.warning(f"⚠️ No boundary data fetched for {city_name}")
        except Exception as e:
            logging.warning(f"⚠️ Could not fetch boundary for {city_name}: {e}")
            # Non-fatal: continue without boundary

# Global instance
places_manager = PlacesManager()
