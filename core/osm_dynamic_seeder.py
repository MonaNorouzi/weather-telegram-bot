"""
OSM Dynamic Seeder - Auto-fetch missing cities from OpenStreetMap

When GPT or users request a city not in database:
1. Query Overpass API for city boundary
2. Extract polygon geometry
3. Calculate geohash
4. Inject into places table
5. Return place_id for routing

Handles global cities on-demand with zero manual data entry.
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from core import geohash_utils
from core.graph_database import graph_db


class OSMDynamicSeeder:
    """
    Dynamically fetch and seed missing cities from OpenStreetMap.
    
    Features:
    - Overpass API integration
    - Automatic polygon boundary extraction
    - Geohash calculation
    - Database injection
    - Caching to avoid duplicate requests
    """
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    
    def __init__(self):
        self._seeding_lock = asyncio.Lock()
        self._in_flight = {}  # Prevent duplicate fetches
        
    async def get_or_seed_place(
        self,
        city_name: str,
        country: str = None,
        admin_level: int = 8
    ) -> Optional[int]:
        """
        Get place_id for city, seeding from OSM if not in database.
        
        Args:
            city_name: City name (e.g., "Paris")
            country: Country name for disambiguation (e.g., "France")
            admin_level: OSM admin level (8=city, 6=region, 4=state)
            
        Returns:
            place_id or None if not found
        """
        # Check if already in database
        existing = await self._find_existing_place(city_name, country)
        if existing:
            logging.info(f"✅ Place exists: {city_name} (ID: {existing})")
            return existing
        
        # Check if another request is already seeding this
        cache_key = f"{city_name}_{country or 'unknown'}".lower()
        
        async with self._seeding_lock:
            if cache_key in self._in_flight:
                # Wait for other request to complete
                logging.debug(f"⏳ Waiting for in-flight seeding: {city_name}")
                return await self._in_flight[cache_key]
            
            # Start seeding
            task = asyncio.create_task(self._seed_from_osm(city_name, country, admin_level))
            self._in_flight[cache_key] = task
        
        try:
            place_id = await task
            return place_id
        finally:
            async with self._seeding_lock:
                del self._in_flight[cache_key]
    
    async def _find_existing_place(self, city_name: str, country: str = None) -> Optional[int]:
        """Check if place already exists in database."""
        try:
            async with graph_db.acquire() as conn:
                if country:
                    # Search with country filter
                    place_id = await conn.fetchval("""
                        SELECT place_id FROM places
                        WHERE LOWER(name) = LOWER($1)
                          AND LOWER(country) = LOWER($2)
                        LIMIT 1
                    """, city_name, country)
                else:
                    # Search by name only
                    place_id = await conn.fetchval("""
                        SELECT place_id FROM places
                        WHERE LOWER(name) = LOWER($1)
                        LIMIT 1
                    """, city_name)
                
                return place_id
        except Exception as e:
            logging.error(f"Error checking existing place: {e}")
            return None
    
    async def _seed_from_osm(
        self,
        city_name: str,
        country: str = None,
        admin_level: int = 8
    ) -> Optional[int]:
        """
        Fetch city from OSM and seed into database.
        
        Returns:
            place_id if successful, None otherwise
        """
        logging.info(f"🌍 Seeding {city_name} from OpenStreetMap...")
        
        # Build Overpass QL query
        query = self._build_overpass_query(city_name, country, admin_level)
        
        try:
            # Query Overpass API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.OVERPASS_URL,
                    data={"data": query},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        logging.error(f"Overpass API error: {resp.status}")
                        return None
                    
                    data = await resp.json()
            
            # Extract boundary geometry
            boundary_data = self._extract_boundary(data)
            if not boundary_data:
                logging.warning(f"No boundary found for {city_name}")
                return None
            
            # Insert into database
            place_id = await self._insert_place(
                city_name,
                boundary_data['polygon_coords'],
                boundary_data['center'],
                boundary_data.get('metadata', {})
            )
            
            if place_id:
                logging.info(f"✅ Seeded {city_name} (ID: {place_id})")
            
            return place_id
        
        except asyncio.TimeoutError:
            logging.error(f"Timeout querying OSM for {city_name}")
            return None
        except Exception as e:
            logging.error(f"Error seeding {city_name} from OSM: {e}")
            return None
    
    def _build_overpass_query(self, city_name: str, country: str = None, admin_level: int = 8) -> str:
        """
        Build Overpass QL query to fetch city boundary.
        
        Returns:
            Overpass QL query string
        """
        # Base query for city boundary
        query = f"""
        [out:json][timeout:25];
        (
          relation["boundary"="administrative"]["admin_level"="{admin_level}"]["name"="{city_name}"]
        """
        
        if country:
            query += f'["is_in:country"="{country}"]'
        
        query += """
        );
        out geom;
        """
        
        return query
    
    def _extract_boundary(self, osm_data: Dict) -> Optional[Dict]:
        """
        Extract polygon boundary from OSM Overpass response.
        
        Returns:
            Dict with polygon_coords, center, metadata
        """
        try:
            elements = osm_data.get('elements', [])
            if not elements:
                return None
            
            # Get first administrative boundary
            boundary = elements[0]
            
            # Extract geometry
            if 'members' in boundary:
                # Relation with members (most common for admin boundaries)
                coords = self._extract_relation_geometry(boundary)
            elif 'geometry' in boundary:
                # Direct geometry
                coords = [(member['lon'], member['lat']) for member in boundary['geometry']]
            else:
                return None
            
            if len(coords) < 3:
                logging.warning("Boundary has < 3 points, invalid polygon")
                return None
            
            # Calculate centroid
            center = self._calculate_centroid(coords)
            
            # Extract metadata
            tags = boundary.get('tags', {})
            metadata = {
                'osm_id': boundary.get('id'),
                'osm_type': boundary.get('type'),
                'name': tags.get('name'),
                'admin_level': tags.get('admin_level'),
                'population': tags.get('population'),
                'wikipedia': tags.get('wikipedia'),
                'wikidata': tags.get('wikidata')
            }
            
            return {
                'polygon_coords': coords,
                'center': center,
                'metadata': metadata
            }
        
        except Exception as e:
            logging.error(f"Error extracting boundary: {e}")
            return None
    
    def _extract_relation_geometry(self, relation: Dict) -> List[Tuple[float, float]]:
        """Extract coordinates from OSM relation members."""
        coords = []
        
        for member in relation.get('members', []):
            if member.get('role') == 'outer' and 'geometry' in member:
                # Outer boundary
                for node in member['geometry']:
                    coords.append((node['lon'], node['lat']))
        
        return coords
    
    def _calculate_centroid(self, coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Calculate polygon centroid (simple average)."""
        if not coords:
            return (0.0, 0.0)
        
        lon_sum = sum(c[0] for c in coords)
        lat_sum = sum(c[1] for c in coords)
        count = len(coords)
        
        return (lat_sum / count, lon_sum / count)
    
    async def _insert_place(
        self,
        name: str,
        polygon_coords: List[Tuple[float, float]],
        center: Tuple[float, float],
        metadata: Dict
    ) -> Optional[int]:
        """
        Insert place into database with polygon boundary.
        
        Returns:
            place_id if successful
        """
        try:
            # Convert coords to WKT POLYGON
            wkt_coords = ', '.join(f"{lon} {lat}" for lon, lat in polygon_coords)
            # Close polygon
            first = polygon_coords[0]
            wkt = f"POLYGON(({wkt_coords}, {first[0]} {first[1]}))"
            
            # Calculate geohash for center
            lat, lon = center
            geohash = geohash_utils.encode(lat, lon, precision=6)
            
            # Extract metadata
            country = metadata.get('is_in:country', 'Unknown')
            place_type = 'city'  # Default to city
            if metadata.get('admin_level') == '6':
                place_type = 'region'
            
            async with graph_db.acquire() as conn:
                place_id = await conn.fetchval("""
                    INSERT INTO places (
                        name, place_type, country, center_geom, boundary_geom,
                        geohash, metadata
                    )
                    VALUES (
                        $1, $2, $3,
                        ST_SetSRID(ST_MakePoint($4, $5), 4326),
                        ST_GeogFromText($6),
                        $7, $8
                    )
                    RETURNING place_id
                """, name, place_type, country, lon, lat, wkt, geohash, metadata)
                
                logging.info(f"📍 Inserted {name} with boundary (geohash: {geohash})")
                return place_id
        
        except Exception as e:
            logging.error(f"Error inserting place: {e}")
            return None


# Global instance
osm_seeder = OSMDynamicSeeder()
