# core/graph_builder.py
"""Graph Builder - Handles cache misses and graph growth.

This module is responsible for:
1. Detecting when a route is not in the graph (cache miss)
2. Querying external APIs (OSRM) for route data
3. Coordinating graph injection via graph_injector module
4. Implementing "split point" logic for optimal graph growth
"""

import logging
from typing import Optional, Tuple, Dict
from core.graph_database import graph_db
from core.osrm_service import osrm_service
from core.graph_routing_engine import routing_engine
from core.graph_injector import graph_injector

class GraphBuilder:
    """Handles cache misses and manages graph growth strategy."""
    
    async def handle_cache_miss(
        self, 
        source_place_id: int, 
        target_place_id: int,
        source_coords: Tuple[float, float],
        target_coords: Tuple[float, float]
    ) -> bool:
        """Handle route cache miss by fetching from OSRM and injecting into graph.
        
        Strategy:
        1. Query OSRM for route with annotations
        2. Parse waypoints and timing data
        3. Inject into graph as node-edge chain
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID  
            source_coords: (lat, lon) of source
            target_coords: (lat, lon) of target
            
        Returns:
            True if successfully injected, False otherwise
        """
        try:
            # Split Point Logic: Check for nearby hubs to connect to
            # This avoids duplicating long highway segments
            logging.info(f"🔄 Checking for split-point optimization near target...")
            
            # Find hubs near the destination
            # We look for major nodes (cities/towns) within 50km
            close_hubs = await self.find_nearest_hub_nodes(target_coords, max_distance_km=50)
            
            best_split_route = None
            
            if close_hubs:
                logging.info(f"Found {len(close_hubs)} potential hubs near target")
                
                # Check each hub for a valid connection
                for hub in close_hubs:
                    hub_node_id = hub['node_id']
                    
                    # 1. Check if we have a path from Source -> Hub in our graph
                    # We need to know which place this node belongs to for the routing engine
                    # But routing engine takes PLACE IDs. 
                    # Actually, our routing engine can route node-to-node internally, 
                    # but the public API is place-to-place.
                    # Let's use internal method for node-to-node check.
                    
                    # Find path from any source access node to this hub node
                    # This is a bit complex efficiently. 
                    # Simplified approach: Check if the hub's LINKED PLACE is reachable from source place
                    
                    hub_place_id = await self._get_place_id_for_node(hub_node_id)
                    if not hub_place_id:
                        continue
                        
                    # Check existing graph path: Source Place -> Hub Place
                    existing_path = await routing_engine.find_route(source_place_id, hub_place_id)
                    
                    if existing_path:
                        logging.info(f"  Found existing path to hub '{hub['place_name']}': {existing_path.total_duration_seconds/60:.1f} min")
                        
                        # 2. Get OSRM path for the "Last Mile": Hub -> Target
                        # We need coords of the hub node
                        hub_coords = await self._get_node_coords(hub_node_id)
                        
                        if not hub_coords:
                            continue
                            
                        last_mile_route = await osrm_service.get_route_with_annotations(hub_coords, target_coords)
                        
                        if last_mile_route:
                            total_split_time = existing_path.total_duration_seconds + last_mile_route['duration']
                            
                            # Compare with direct OSRM route
                            # Direct OSRM: Source -> Target
                            # We already fetched this above? No, we haven't yet.
                            
                            # Let's fetch direct route now to compare
                            direct_route = await osrm_service.get_route_with_annotations(source_coords, target_coords)
                            
                            if not direct_route:
                                continue
                                
                            logging.info(f"  Split time via {hub['place_name']}: {total_split_time:.1f}s vs Direct: {direct_route['duration']:.1f}s")
                            
                            # Decision: If split time is not significantly worse (e.g., < 10% slower)
                            # PREFER the split to grow graph organically
                            if total_split_time <= direct_route['duration'] * 1.1:
                                logging.info(f"✅ Split Point Strategy WIN: Extending from {hub['place_name']}")
                                
                                # Inject ONLY the last mile: Hub -> Target
                                # We need to link the START of this route to the HUB node
                                # The inject_route method usually links to places.
                                # Be careful: 'hub' is a node, not just a place. 
                                # But we can treat it as injecting a route from Hub Place -> Target Place
                                
                                success = await graph_injector.inject_route(
                                    last_mile_route,
                                    hub_place_id, # Source is the Hub Place
                                    target_place_id,
                                    hub_coords,
                                    target_coords
                                )
                                
                                if success:
                                    return True
            
            # Fallback: Full OSRM injection (Standard cache miss)
            logging.info("⤵️ Standard Strategy: Injecting full route Source -> Target")
            
            # Query OSRM with annotations for timing data
            route_data = await osrm_service.get_route_with_annotations(source_coords, target_coords)
            
            if not route_data:
                logging.error("OSRM query failed")
                return False
            
            # Inject route into graph
            success = await graph_injector.inject_route(
                route_data,
                source_place_id,
                target_place_id,
                source_coords,
                target_coords
            )
            
            return success
            
        except Exception as e:
            logging.error(f"Error handling cache miss: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _get_place_id_for_node(self, node_id: int) -> Optional[int]:
        """Get the linked place ID for a node."""
        async with graph_db.acquire() as conn:
            return await conn.fetchval("SELECT linked_place_id FROM nodes WHERE node_id = $1", node_id)

    async def _get_node_coords(self, node_id: int) -> Optional[Tuple[float, float]]:
        """Get coordinates for a node."""
        async with graph_db.acquire() as conn:
            row = await conn.fetchrow("SELECT ST_Y(geometry::geometry) as lat, ST_X(geometry::geometry) as lon FROM nodes WHERE node_id = $1", node_id)
            if row:
                return (row['lat'], row['lon'])
            return None
    
    async def find_nearest_hub_nodes(
        self, 
        coords: Tuple[float, float], 
        max_distance_km: float = 50
    ) -> list:
        """Find nearby hub nodes for "split point" logic.
        
        When adding a new destination near existing routes, find major
        nodes (cities) in the vicinity to connect to.
        
        Args:
            coords: (lat, lon) of new destination
            max_distance_km: Maximum search radius in km
            
        Returns:
            List of nearby node IDs with their distances
        """
        lat, lon = coords
        
        async with graph_db.acquire() as conn:
            # Find nodes linked to cities within radius
            rows = await conn.fetch("""
                SELECT 
                    n.node_id,
                    p.name as place_name,
                    ST_Distance(
                        n.geometry,
                        ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                    ) as distance_meters
                FROM nodes n
                JOIN places p ON n.linked_place_id = p.place_id
                WHERE p.place_type IN ('city', 'town')
                AND ST_DWithin(
                    n.geometry,
                    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                    $3
                )
                ORDER BY distance_meters ASC
                LIMIT 10
            """, lon, lat, max_distance_km * 1000)
            
            return [
                {
                    'node_id': row['node_id'],
                    'place_name': row['place_name'],
                    'distance_km': row['distance_meters'] / 1000
                }
                for row in rows
            ]
    
    async def link_place_to_nearest_node(
        self,
        place_id: int,
        place_coords: Tuple[float, float],
        candidate_nodes: list,
        max_distance_km: float = 5.0
    ) -> Optional[int]:
        """Link a place to its nearest node on the route to create a hub.
        
        Args:
            place_id: ID of the place to link
            place_coords: (lat, lon) of the place
            candidate_nodes: List of node IDs on this route
            max_distance_km: Max distance to consider (default 5km)
            
        Returns:
            node_id if linked successfully, None otherwise
        """
        if not candidate_nodes:
            return None
            
        lat, lon = place_coords
        
        try:
            async with graph_db.acquire() as conn:
                # Find nearest unlinked node
                nearest = await conn.fetchrow("""
                    SELECT node_id,
                        ST_Distance(
                            geometry,
                            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                        ) as distance_meters
                    FROM nodes
                    WHERE node_id = ANY($3)
                    AND linked_place_id IS NULL
                    ORDER BY distance_meters
                    LIMIT 1
                """, lon, lat, candidate_nodes)
                
                if not nearest:
                    return None
                
                distance_km = nearest['distance_meters'] / 1000.0
                
                if distance_km > max_distance_km:
                    logging.debug(f"Place {place_id} too far ({distance_km:.1f}km)")
                    return None
                
                # Link it!
                await conn.execute("""
                    UPDATE nodes
                    SET linked_place_id = $1,
                        node_type = 'access_point'
                    WHERE node_id = $2
                """, place_id, nearest['node_id'])
                
                logging.info(f"🔗 Linked place {place_id} to node {nearest['node_id']} ({distance_km:.2f}km)")
                return nearest['node_id']
                
        except Exception as e:
            logging.error(f"Error linking place {place_id}: {e}")
            return None

    
    async def get_or_create_place(
        self,
        name: str,
        place_type: str,
        coords: Tuple[float, float],
        province: Optional[str] = None
    ) -> int:
        """Get existing place or create new one.
        
        IMPORTANT: Normalizes city names so 'تهران' and 'Tehran' 
        both resolve to the same place_id for cache consistency.
        
        Args:
            name: Place name (will be normalized)
            place_type: Type (city, town, village, etc.)
            coords: (lat, lon)
            province: Province name (optional)
            
        Returns:
            Place ID
        """
        from core.city_normalizer import city_normalizer
        
        lat, lon = coords
        
        # CRITICAL: Normalize name for cache consistency
        # This ensures "تهران" and "Tehran" use the same place_id
        normalized_name = city_normalizer.normalize(name)
        
        async with graph_db.acquire() as conn:
            # Try to find existing place using normalized name
            place_id = await conn.fetchval("""
                SELECT place_id FROM places
                WHERE name = $1 AND place_type = $2 AND province IS NOT DISTINCT FROM $3
            """, normalized_name, place_type, province)
            
            if place_id:
                logging.info(f"Found existing place: {name} → {normalized_name} (ID: {place_id})")
                return place_id
            
            # Create new place with normalized name
            place_id = await conn.fetchval("""
                INSERT INTO places (name, place_type, province, center_geom)
                VALUES ($1, $2, $3, ST_SetSRID(ST_MakePoint($4, $5), 4326))
                ON CONFLICT (name, place_type, province) DO UPDATE
                SET center_geom = EXCLUDED.center_geom
                RETURNING place_id
            """, normalized_name, place_type, province, lon, lat)
            
            logging.info(f"Created new place: {name} → {normalized_name} (ID: {place_id})")
            return place_id

# Global instance
graph_builder = GraphBuilder()
