"""
GPT-Optimized JSON API for Weather Routing

Designed specifically for GPT-4 Function Calling:
- Low token usage (structured, no markdown)
- High parsing accuracy (strict JSON schema)
- Minimal verbosity
- Fast serialization

This interface allows GPT agents to query routes with weather
without wasting tokens on human-readable formatting.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from core.graph_routing_engine import graph_routing_engine
from core.weather_overlay import weather_overlay
from core.osm_dynamic_seeder import osm_seeder


@dataclass
class GPTRoute:
    """Minimal route data for GPT."""
    duration_seconds: float
    distance_meters: float
    path_count: int
    weather_summary: str
    places: List[str]  # Just names
    warnings: List[str]  # Concise warnings


@dataclass
class GPTWeatherPoint:
    """Minimal weather data."""
    place: str
    temp_c: Optional[int]
    condition: str  # emoji
    time_iso: str


class GPTJsonAPI:
    """
    JSON API optimized for GPT Function Calling.
    
    Key Principles:
    - Return pure JSON (no markdown, no formatting)
    - Minimize token usage (abbreviate keys, remove nulls)
    - Maximize parsing accuracy (strict schema)
    - Fast execution (async, cached)
    """
    
    async def get_route(
        self,
        from_city: str,
        to_city: str,
        departure_time: Optional[str] = None,
        from_country: Optional[str] = None,
        to_country: Optional[str] = None
    ) -> Dict:
        """
        Get route with weather for GPT agents.
        
        Args:
            from_city: Origin city name
            to_city: Destination city name
            departure_time: ISO 8601 (optional, defaults to now)
            from_country: Origin country (for disambiguation)
            to_country: Destination country (for disambiguation)
            
        Returns:
            {
                "success": bool,
                "route": {...},
                "weather": [...],
                "errors": [...]
            }
        """
        errors = []
        
        try:
            # Parse departure time
            if departure_time:
                try:
                    start_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                except ValueError:
                    start_time = datetime.now()
                    errors.append(f"Invalid time format, using now")
            else:
                start_time = datetime.now()
            
            # Get or seed places (dynamic OSM fetching)
            from_place_id = await osm_seeder.get_or_seed_place(from_city, from_country)
            to_place_id = await osm_seeder.get_or_seed_place(to_city, to_country)
            
            if not from_place_id:
                return {
                    "success": False,
                    "errors": [f"City not found: {from_city}"]
                }
            
            if not to_place_id:
                return {
                    "success": False,
                    "errors": [f"City not found: {to_city}"]
                }
            
            # Find route
            route_result = await graph_routing_engine.find_route(from_place_id, to_place_id)
            
            if not route_result:
                return {
                    "success": False,
                    "errors": ["No route found between cities"]
                }
            
            # Apply weather
            weather_result = await weather_overlay.apply_weather_overlay(
                path_nodes=route_result.path_nodes,
                base_duration_seconds=route_result.total_duration_seconds,
                total_distance_meters=route_result.total_distance_meters,
                geometries=route_result.geometries,
                start_time=start_time
            )
            
            # Build GPT-optimized response
            return {
                "success": True,
                "route": {
                    "dur_sec": int(weather_result.base_duration_seconds),
                    "dist_m": int(weather_result.total_distance_meters),
                    "nodes": len(weather_result.path_nodes),
                    "summary": weather_result.weather_summary
                },
                "weather": [
                    {
                        "loc": w.get('place_name', 'Unknown'),
                        "temp": w.get('temp'),
                        "icon": w.get('icon', ''),
                        "time": w.get('arrival_time_str', '')
                    }
                    for w in (weather_result.node_weather or [])[:10]  # Limit to 10 for token efficiency
                ],
                "places": [p.get('name', '') for p in (weather_result.places_along_route or [])[:20]],
                "errors": errors if errors else None
            }
        
        except Exception as e:
            logging.error(f"GPT API error: {e}")
            return {
                "success": False,
                "errors": [f"Internal error: {str(e)}"]
            }
    
    async def get_weather(
        self,
        city: str,
        country: Optional[str] = None,
        forecast_time: Optional[str] = None
    ) -> Dict:
        """
        Get weather for a single city (GPT-optimized).
        
        Args:
            city: City name
            country: Country (optional)
            forecast_time: ISO 8601 (optional)
            
        Returns:
            {
                "success": bool,
                "city": str,
                "temp_c": int,
                "condition": str,
                "time": str,
                "errors": [...]
            }
        """
        try:
            # Get or seed place
            place_id = await osm_seeder.get_or_seed_place(city, country)
            
            if not place_id:
                return {
                    "success": False,
                    "errors": [f"City not found: {city}"]
                }
            
            # Get coordinates
            from core.graph_database import graph_db
            async with graph_db.acquire() as conn:
                coords = await conn.fetchrow("""
                    SELECT
                        ST_Y(center_geom::geometry) as lat,
                        ST_X(center_geom::geometry) as lon
                    FROM places
                    WHERE place_id = $1
                """, place_id)
            
            if not coords:
                return {
                    "success": False,
                    "errors": ["Could not get coordinates"]
                }
            
            # Parse forecast time
            if forecast_time:
                try:
                    target_time = datetime.fromisoformat(forecast_time.replace('Z', '+00:00'))
                except ValueError:
                    target_time = datetime.now()
            else:
                target_time = datetime.now()
            
            # Get weather (uses temporal cache!)
            from core.openmeteo_service import openmeteo_service
            weather = await openmeteo_service.get_forecast_at_time(
                coords['lat'],
                coords['lon'],
                target_time
            )
            
            if not weather:
                return {
                    "success": False,
                    "errors": ["Weather data unavailable"]
                }
            
            return {
                "success": True,
                "city": city,
                "temp_c": weather.get('temp'),
                "condition": weather.get('icon', ''),
                "code": weather.get('weathercode'),
                "time": target_time.isoformat(),
                "errors": None
            }
        
        except Exception as e:
            logging.error(f"GPT weather API error: {e}")
            return {
                "success": False,
                "errors": [str(e)]
            }
    
    async def search_city(
        self,
        query: str,
        country: Optional[str] = None,
        limit: int = 5
    ) -> Dict:
        """
        Search for cities (with auto-seeding from OSM).
        
        Args:
            query: City name query
            country: Country filter (optional)
            limit: Max results (default 5)
            
        Returns:
            {
                "success": bool,
                "cities": [{"name": str, "country": str, "id": int}, ...],
                "errors": [...]
            }
        """
        try:
            from core.graph_database import graph_db
            
            # Search existing
            async with graph_db.acquire() as conn:
                if country:
                    results = await conn.fetch("""
                        SELECT place_id, name, country, place_type
                        FROM places
                        WHERE name ILIKE $1 AND country ILIKE $2
                        LIMIT $3
                    """, f"%{query}%", f"%{country}%", limit)
                else:
                    results = await conn.fetch("""
                        SELECT place_id, name, country, place_type
                        FROM places
                        WHERE name ILIKE $1
                        LIMIT $2
                    """, f"%{query}%", limit)
            
            cities = [
                {
                    "id": r['place_id'],
                    "name": r['name'],
                    "country": r['country'],
                    "type": r['place_type']
                }
                for r in results
            ]
            
            # If no results and exact query, try OSM
            if not cities and len(query) > 2:
                logging.info(f"No local results for '{query}', trying OSM...")
                place_id = await osm_seeder.get_or_seed_place(query, country)
                
                if place_id:
                    # Fetch the seeded place
                    async with graph_db.acquire() as conn:
                        result = await conn.fetchrow("""
                            SELECT place_id, name, country, place_type
                            FROM places
                            WHERE place_id = $1
                        """, place_id)
                    
                    if result:
                        cities = [{
                            "id": result['place_id'],
                            "name": result['name'],
                            "country": result['country'],
                            "type": result['place_type']
                        }]
            
            return {
                "success": True,
                "cities": cities,
                "count": len(cities),
                "errors": None
            }
        
        except Exception as e:
            logging.error(f"GPT search API error: {e}")
            return {
                "success": False,
                "cities": [],
                "errors": [str(e)]
            }


# Global instance
gpt_api = GPTJsonAPI()
