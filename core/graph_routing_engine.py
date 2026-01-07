# core/graph_routing_engine.py
"""Graph Routing Engine using PostgreSQL + PostGIS + pgRouting.

This module implements the core routing logic using the graph database.
It handles place-to-node resolution, multi-entry access points, and pathfinding.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from core.graph_database import graph_db

@dataclass
class RouteResult:
    """Result of a route query."""
    path_nodes: List[int]  # Sequence of node IDs
    total_distance_meters: float
    total_duration_seconds: float
    geometries: List[Tuple[float, float]]  # List of (lat, lon) points
    edge_details: List[Dict]  # List of edge info (distance, duration, road_type)

class GraphRoutingEngine:
    """Core routing engine using graph database and pgRouting."""
    
    async def find_route(self, source_place_id: int, target_place_id: int) -> Optional[RouteResult]:
        """Find optimal route between two places using graph database.
        
        This implements the "Manager's Constraint" by:
        1. Resolving places to their access nodes
        2. Trying all combinations of source/target access points
        3. Selecting the optimal path
        
        Args:
            source_place_id: Starting place ID
            target_place_id: Destination place ID
            
        Returns:
            RouteResult if path found, None otherwise
        """
        try:
            # Step 1: Resolve places to access nodes
            source_nodes = await self._get_access_nodes(source_place_id)
            target_nodes = await self._get_access_nodes(target_place_id)
            
            if not source_nodes:
                logging.warning(f"No access nodes found for source place {source_place_id}")
                return None
            
            if not target_nodes:
                logging.warning(f"No access nodes found for target place {target_place_id}")
                return None
            
            logging.info(f"Found {len(source_nodes)} source nodes and {len(target_nodes)} target nodes")
            
            # Step 2: Try all combinations and find optimal path
            best_route = None
            best_cost = float('inf')
            
            for src_node in source_nodes:
                for tgt_node in target_nodes:
                    route = await self._find_path_dijkstra(src_node, tgt_node)
                    if route and route.total_duration_seconds < best_cost:
                        best_cost = route.total_duration_seconds
                        best_route = route
            
            if best_route:
                logging.info(f"Route found: {len(best_route.path_nodes)} nodes, "
                           f"{best_route.total_distance_meters/1000:.1f} km, "
                           f"{best_route.total_duration_seconds/3600:.1f} hours")
            else:
                logging.warning("No path found in graph (cache miss)")
            
            return best_route
            
        except Exception as e:
            logging.error(f"Error finding route: {e}")
            return None
    
    async def _get_access_nodes(self, place_id: int) -> List[int]:
        """Get all access nodes for a place.
        
        Args:
            place_id: Place ID
            
        Returns:
            List of node IDs linked to this place
        """
        async with graph_db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT node_id FROM nodes WHERE linked_place_id = $1",
                place_id
            )
            return [row['node_id'] for row in rows]
    
    async def _find_path_dijkstra(self, source_node: int, target_node: int) -> Optional[RouteResult]:
        """Find shortest path between two nodes using pgRouting Dijkstra.
        
        Args:
            source_node: Starting node ID
            target_node: Ending node ID
            
        Returns:
            RouteResult if path exists, None otherwise
        """
        async with graph_db.acquire() as conn:
            # Use pgr_dijkstra with base_duration_seconds as cost
            path_rows = await conn.fetch("""
                SELECT 
                    path.seq,
                    path.node,
                    path.edge,
                    path.cost,
                    path.agg_cost,
                    e.distance_meters,
                    e.base_duration_seconds,
                    e.road_type,
                    e.geometry
                FROM pgr_dijkstra(
                    'SELECT edge_id as id, source_node as source, target_node as target, 
                     base_duration_seconds as cost FROM edges',
                    $1::bigint, $2::bigint, directed => true
                ) AS path
                LEFT JOIN edges e ON path.edge = e.edge_id
                ORDER BY path.seq
            """, source_node, target_node)
            
            if not path_rows:
                return None
            
            # Extract path information
            path_nodes = [row['node'] for row in path_rows]
            total_duration = path_rows[-1]['agg_cost'] if path_rows else 0
            total_distance = sum(row['distance_meters'] or 0 for row in path_rows)
            
            # Get geometries for all nodes in path
            geometries = await self._get_node_geometries(path_nodes)
            
            # Build edge details
            edge_details = []
            for row in path_rows:
                if row['edge'] is not None:  # Last row has no edge
                    edge_details.append({
                        'distance_meters': row['distance_meters'],
                        'duration_seconds': row['base_duration_seconds'],
                        'road_type': row['road_type'],
                        'cost': row['cost']
                    })
            
            return RouteResult(
                path_nodes=path_nodes,
                total_distance_meters=total_distance,
                total_duration_seconds=total_duration,
                geometries=geometries,
                edge_details=edge_details
            )
    
    async def _get_node_geometries(self, node_ids: List[int]) -> List[Tuple[float, float]]:
        """Get (lat, lon) coordinates for a list of nodes.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            List of (lat, lon) tuples
        """
        if not node_ids:
            return []
        
        async with graph_db.acquire() as conn:
            rows = await conn.fetch("""
                SELECT node_id, ST_Y(geometry::geometry) as lat, ST_X(geometry::geometry) as lon
                FROM nodes
                WHERE node_id = ANY($1::int[])
                ORDER BY array_position($1::int[], node_id)
            """, node_ids)
            
            return [(row['lat'], row['lon']) for row in rows]
    
    async def check_path_exists(self, source_place_id: int, target_place_id: int) -> bool:
        """Quick check if any path exists between two places in the graph.
        
        Used for cache miss detection.
        
        Args:
            source_place_id: Starting place ID
            target_place_id: Destination place ID
            
        Returns:
            True if path exists, False otherwise
        """
        route = await self.find_route(source_place_id, target_place_id)
        return route is not None

# Global instance
routing_engine = GraphRoutingEngine()
