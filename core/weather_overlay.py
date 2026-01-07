# core/weather_overlay.py
"""Weather Overlay - Fetches weather data for route nodes (informational only).

This module fetches weather conditions for route nodes at estimated arrival times
for display purposes only. Weather does NOT affect the ETA calculation.

Route duration is purely deterministic based on graph edges:
- base_duration_seconds = distance_meters / (max_speed_kmh / 3.6)

Weather data is returned for display (e.g., showing "Snowy ❄️" next to city names).
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
from core.openmeteo_service import openmeteo_service
from core.graph_database import graph_db

@dataclass
class WeatherAdjustedRoute:
    """Route with weather data (informational only)."""
    path_nodes: List[int]
    base_duration_seconds: float
    total_distance_meters: float
    geometries: List[Tuple[float, float]]
    node_weather: List[Dict]  # Weather data for each node (display only)
    weather_summary: str
    places_along_route: List[Dict]  # Places containing route coordinates (polygon-based)

class WeatherOverlay:
    """Applies weather adjustments to route timing."""
    
    async def apply_weather_overlay(
        self,
        path_nodes: List[int],
        base_duration_seconds: float,
        total_distance_meters: float,
        geometries: List[Tuple[float, float]],
        start_time: datetime
    ) -> WeatherAdjustedRoute:
        """Fetch weather data for route nodes (informational only - no duration changes).
        
        Process:
        1. Get coordinates for all nodes in path
        2. Calculate estimated arrival time at each node (using base durations)
        3. Fetch weather for each node at arrival time
        4. Return weather data for display purposes
        
        NOTE: Weather does NOT affect duration. ETA is purely deterministic.
        
        Args:
            path_nodes: List of node IDs
            base_duration_seconds: Base duration from graph (unchanged)
            total_distance_meters: Total distance
            geometries: List of (lat, lon) coordinates
            start_time: Departure time
            
        Returns:
            WeatherAdjustedRoute with weather data (duration unchanged)
        """
        try:
            if not path_nodes or len(path_nodes) < 2:
                logging.warning("Not enough nodes for weather overlay")
                return self._create_default_result(
                    path_nodes, base_duration_seconds, total_distance_meters, geometries
                )
            
            # PERFORMANCE FIX: Sample weather points to avoid rate limiting
            # With Redis cache, even long routes are fast!
            SAMPLE_INTERVAL = 10  # Fetch weather every 10th node
            
            if len(path_nodes) > 50:  # Only sample for long routes
                logging.info(f"⚡ Sampling weather every {SAMPLE_INTERVAL}th node ({len(path_nodes)} total) - Redis cache active!")
            
            # Get edge details for timing
            edge_durations = await self._get_edge_durations(path_nodes)
            
            if not edge_durations:
                logging.warning("No edge durations found, using base duration")
                return self._create_default_result(
                    path_nodes, base_duration_seconds, total_distance_meters, geometries
                )
            
            # Calculate arrival times at each node (using deterministic base durations)
            node_arrival_times = [start_time]
            cumulative_time = 0
            
            for duration in edge_durations:
                cumulative_time += duration
                arrival = start_time + timedelta(seconds=cumulative_time)
                node_arrival_times.append(arrival)
            
            # Find which places contain route coordinates (polygon-based)
            logging.info(f"Checking {len(geometries)} coordinates against place boundaries")
            places_containing = await self._find_places_containing_coordinates(geometries)
            
            # Fetch weather for all nodes (informational only)
            logging.info(f"Fetching weather for {len(path_nodes)} nodes along route")
            node_weather = await self._fetch_weather_for_nodes(geometries, node_arrival_times)
            
            # Enrich weather data with place boundary information
            for i, weather in enumerate(node_weather):
                if weather and i in places_containing:
                    weather['inside_places'] = places_containing[i]
            
            # Generate summary (informational)
            summary = self._generate_weather_summary(node_weather)
            
            # Extract unique places along route
            unique_places = []
            seen_place_ids = set()
            for places_list in places_containing.values():
                for place in places_list:
                    if place['place_id'] not in seen_place_ids:
                        unique_places.append(place)
                        seen_place_ids.add(place['place_id'])
            
            logging.info(f"Weather overlay: {base_duration_seconds/3600:.1f}h duration, "
                        f"{len(node_weather)} nodes with weather, "
                        f"{len(unique_places)} places along route")
            
            return WeatherAdjustedRoute(
                path_nodes=path_nodes,
                base_duration_seconds=base_duration_seconds,
                total_distance_meters=total_distance_meters,
                geometries=geometries,
                node_weather=node_weather,
                weather_summary=summary,
                places_along_route=unique_places
            )
            
        except Exception as e:
            logging.error(f"Error applying weather overlay: {e}")
            import traceback
            traceback.print_exc()
            return self._create_default_result(
                path_nodes, base_duration_seconds, total_distance_meters, geometries
            )
    
    async def _get_edge_durations(self, path_nodes: List[int]) -> List[float]:
        """Get base durations for edges in the path.
        
        Args:
            path_nodes: List of node IDs
            
        Returns:
            List of base_duration_seconds for each edge
        """
        if len(path_nodes) < 2:
            return []
        
        durations = []
        
        async with graph_db.acquire() as conn:
            for i in range(len(path_nodes) - 1):
                duration = await conn.fetchval("""
                    SELECT base_duration_seconds
                    FROM edges
                    WHERE source_node = $1 AND target_node = $2
                """, path_nodes[i], path_nodes[i + 1])
                
                if duration:
                    durations.append(duration)
                else:
                    # Fallback: estimate based on distance
                    logging.warning(f"No edge found between nodes {path_nodes[i]} and {path_nodes[i+1]}")
                    durations.append(60.0)  # 1 minute fallback
        
        return durations
    
    async def _find_places_containing_coordinates(
        self,
        geometries: List[Tuple[float, float]]
    ) -> Dict[int, List[Dict]]:
        """Find which places contain each coordinate using ST_Contains.
        
        Uses PostGIS ST_Contains to check if coordinates are inside place boundaries.
        This enables accurate weather alerts for coordinates physically inside cities.
        
        Args:
            geometries: List of (lat, lon) tuples for route coordinates
            
        Returns:
            Dict mapping coordinate index to list of places containing it
            Format: {0: [{place_id, name, type, province}, ...], 1: [...], ...}
        """
        if not geometries:
            return {}
        
        result = {}
        
        try:
            async with graph_db.acquire() as conn:
                # Batch query: check all coordinates against all places with boundaries
                # Note: We use the helper function created in migration
                for idx, (lat, lon) in enumerate(geometries):
                    places = await conn.fetch("""
                        SELECT place_id, name, place_type, province
                        FROM find_places_containing_point($1, $2)
                    """, lat, lon)
                    
                    if places:
                        result[idx] = [
                            {
                                'place_id': p['place_id'],
                                'name': p['name'],
                                'type': p['place_type'],
                                'province': p['province']
                            }
                            for p in places
                        ]
                        
            if result:
                logging.info(f"✅ Found {len(result)} coordinates inside place boundaries")
            else:
                logging.info("ℹ️ No coordinates found inside known place boundaries")
                
        except Exception as e:
            logging.warning(f"Error checking place boundaries: {e}")
            # Graceful fallback - return empty dict if boundary check fails
            return {}
        
        return result
    
    async def _fetch_weather_for_nodes(
        self,
        geometries: List[Tuple[float, float]],
        arrival_times: List[datetime]
    ) -> List[Dict]:
        """Fetch weather data for nodes at their arrival times.
        
        Args:
            geometries: List of (lat, lon) tuples
            arrival_times: List of datetime objects for arrival at each node
            
        Returns:
            List of weather dicts with temp, code, condition
        """
        if not geometries or not arrival_times:
            return []
        
        # Use batch weather fetching from openmeteo_service
        locations_with_times = [
            (lat, lon, arrival_time)
            for (lat, lon), arrival_time in zip(geometries, arrival_times)
        ]
        
        weather_results = await openmeteo_service.get_batch_forecasts(locations_with_times)
        
        # Convert to list format
        node_weather = []
        for lat, lon in geometries:
            weather = weather_results.get((lat, lon), {})
            
            # Add weather condition category
            if weather:
                weather['condition'] = self._categorize_weather(weather.get('weathercode', 0))
            
            node_weather.append(weather)
        
        return node_weather
    
    def _categorize_weather(self, wmo_code: int) -> str:
        """Categorize WMO weather code into condition.
        
        Args:
            wmo_code: WMO weather code
            
        Returns:
            Condition string (snow, rain, clear, etc.)
        """
        if wmo_code in [71, 73, 75, 77, 85, 86]:
            return 'snow'
        elif wmo_code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
            return 'rain'
        elif wmo_code in [95, 96, 99]:
            return 'thunderstorm'
        elif wmo_code in [45, 48]:
            return 'fog'
        elif wmo_code == 0:
            return 'clear'
        elif wmo_code in [1, 2, 3]:
            return 'cloudy'
        else:
            return 'default'
    
    def _generate_weather_summary(self, node_weather: List[Dict]) -> str:
        """Generate human-readable weather summary (informational only).
        
        Args:
            node_weather: Weather data for all nodes
            
        Returns:
            Summary string describing weather conditions along route
        """
        if not node_weather:
            return "Weather data unavailable"
        
        # Count weather conditions
        from collections import Counter
        conditions = []
        for weather in node_weather:
            if weather and 'condition' in weather:
                conditions.append(weather['condition'])
        
        if not conditions:
            return "Weather data unavailable"
        
        condition_counts = Counter(conditions)
        
        # Generate summary
        if len(condition_counts) == 1:
            condition = list(condition_counts.keys())[0]
            return f"{condition.capitalize()} conditions expected"
        else:
            # Multiple conditions
            most_common = condition_counts.most_common(2)
            if len(most_common) == 1:
                return f"{most_common[0][0].capitalize()} conditions expected"
            else:
                return f"Mixed conditions: {most_common[0][0]}, {most_common[1][0]}"
    
    def _create_default_result(
        self,
        path_nodes: List[int],
        base_duration: float,
        distance: float,
        geometries: List[Tuple[float, float]]
    ) -> WeatherAdjustedRoute:
        """Create default result when weather data unavailable."""
        return WeatherAdjustedRoute(
            path_nodes=path_nodes,
            base_duration_seconds=base_duration,
            total_distance_meters=distance,
            geometries=geometries,
            node_weather=[],
            weather_summary="Weather data unavailable",
            places_along_route=[]
        )

# Global instance
weather_overlay = WeatherOverlay()
