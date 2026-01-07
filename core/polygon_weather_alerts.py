"""
Polygon-Based City Weather Alerts

Uses ST_Contains to detect when route enters city boundaries.
Triggers weather alerts for administrative boundaries, not just proximity.

Features:
- Polygon boundary detection (ST_Contains)
- Geohash-optimized spatial queries
- Real-time weather alerts
- Beautiful Telegram formatting
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from core.graph_database import graph_db
from core import geohash_utils
from core.openmeteo_service import openmeteo_service


class PolygonWeatherAlerts:
    """
    Detect when route crosses city boundaries and generate weather alerts.
    
    Uses:
    - ST_Contains for precise polygon boundary detection
    - Geohash for spatial optimization
    - Temporal cache for fast weather lookups
    """
    
    async def get_cities_along_route(
        self,
        geometries: List[Tuple[float, float]],
        start_time: datetime
    ) -> List[Dict]:
        """
        Find cities whose boundaries contain route points.
        
        Args:
            geometries: List of (lat, lon) route coordinates
            start_time: Departure time for weather forecasts
            
        Returns:
            List of city dicts with weather and arrival time
        """
        if not geometries:
            return []
        
        try:
            # Get unique geohashes for route points (optimization)
            route_geohashes = set()
            for lat, lon in geometries:
                gh = geohash_utils.encode(lat, lon, precision=6)
                route_geohashes.add(gh)
                # Add neighbors for boundary cases
                for neighbor in geohash_utils.neighbors(gh):
                    route_geohashes.add(neighbor)
            
            # Query cities with polygon boundaries that might intersect route
            async with graph_db.acquire() as conn:
                cities = await conn.fetch("""
                    SELECT 
                        place_id,
                        name,
                        place_type,
                        country,
                        ST_Y(center_geom::geometry) as lat,
                        ST_X(center_geom::geometry) as lon,
                        boundary_geom,
                        geohash
                    FROM places
                    WHERE boundary_geom IS NOT NULL
                      AND geohash = ANY($1::text[])
                    ORDER BY name
                """, list(route_geohashes))
            
            if not cities:
                logging.debug("No cities with boundaries found near route")
                return []
            
            # Check which cities actually contain route points (ST_Contains)
            cities_on_route = []
            
            for city in cities:
                # Find first route point that enters this city
                entry_point_idx = await self._find_city_entry_point(
                    city,
                    geometries
                )
                
                if entry_point_idx is not None:
                    # Route enters this city!
                    
                    # Calculate arrival time at entry point
                    progress = entry_point_idx / len(geometries)
                    # Assume constant speed (simplified)
                    arrival_time = start_time + timedelta(hours=progress * 8)  # Rough estimate
                    
                    # Get weather forecast for this city at arrival time
                    weather = await openmeteo_service.get_forecast_at_time(
                        city['lat'],
                        city['lon'],
                        arrival_time
                    )
                    
                    cities_on_route.append({
                        'place_id': city['place_id'],
                        'name': city['name'],
                        'type': city['place_type'],
                        'country': city['country'],
                        'lat': city['lat'],
                        'lon': city['lon'],
                        'entry_idx': entry_point_idx,
                        'arrival_time': arrival_time,
                        'weather': weather,
                        'temp': weather.get('temp') if weather else None,
                        'icon': weather.get('icon', '') if weather else '',
                        'condition': self._get_condition_text(weather)
                    })
            
            # Sort by entry order
            cities_on_route.sort(key=lambda x: x['entry_idx'])
            
            logging.info(f"📍 Found {len(cities_on_route)} cities with boundaries on route")
            
            return cities_on_route
        
        except Exception as e:
            logging.error(f"Error getting polygon-based cities: {e}")
            return []
    
    async def _find_city_entry_point(
        self,
        city: Dict,
        geometries: List[Tuple[float, float]]
    ) -> Optional[int]:
        """
        Find index of first route point that enters city boundary.
        
        Uses ST_Contains for precise boundary detection.
        
        Returns:
            Index of entry point, or None if route doesn't enter city
        """
        try:
            async with graph_db.acquire() as conn:
                for idx, (lat, lon) in enumerate(geometries[::5]):  # Sample every 5th point for performance
                    # Check if this point is within city boundary
                    contains = await conn.fetchval("""
                        SELECT ST_Contains(
                            boundary_geom,
                            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography
                        )
                        FROM places
                        WHERE place_id = $3
                    """, lon, lat, city['place_id'])
                    
                    if contains:
                        return idx * 5  # Adjust for sampling
            
            return None
        
        except Exception as e:
            logging.debug(f"Error checking city boundary: {e}")
            return None
    
    def _get_condition_text(self, weather: Optional[Dict]) -> str:
        """Convert weather code to text description."""
        if not weather:
            return "Unknown"
        
        code = weather.get('weathercode', 0)
        
        if code == 0:
return "Clear"
        elif code in [1, 2, 3]:
            return "Partly Cloudy"
        elif code in [45, 48]:
            return "Foggy"
        elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            return "Rainy"
        elif code in [71, 73, 75, 77, 85, 86]:
            return "Snowy"
        elif code in [95, 96, 99]:
            return "Stormy"
        else:
            return "Variable"
    
    async def format_telegram_alerts(
        self,
        cities: List[Dict],
        origin_name: str,
        dest_name: str
    ) -> str:
        """
        Format polygon-based city alerts for beautiful Telegram display.
        
        Returns:
            Formatted markdown string
        """
        if not cities:
            return ""
        
        lines = [
            "",
            "🏙️ **Cities on Route** (Polygon Boundaries):",
            ""
        ]
        
        for i, city in enumerate(cities[:15]):  # Limit to 15 for readability
            # Beautiful emoji based on position
            if i == 0:
                emoji = "🚩"  # Origin/first city
            elif i == len(cities) - 1:
                emoji = "🏁"  # Destination/last city
            else:
                emoji = "🔹"  # Intermediate
            
            # Format arrival time
            time_str = city['arrival_time'].strftime("%H:%M")
            
            # Weather info
            temp_str = f"{city['temp']}°C" if city['temp'] is not None else "N/A"
            icon = city['icon'] or '🌡️'
            condition = city['condition']
            
            # Build line
            line = f"{emoji} **{city['name']}** ({time_str}) • {temp_str} {icon}"
            
            # Add weather warning if severe
            if city['weather']:
                code = city['weather'].get('weathercode', 0)
                if code in [95, 96, 99]:  # Thunderstorm
                    line += " ⚠️ Storm"
                elif code in [71, 73, 75, 77, 85, 86]:  # Snow
                    line += " ⚠️ Snow"
                elif code in [45, 48]:  # Fog
                    line += " ⚠️ Fog"
            
            lines.append(line)
        
        return "\n".join(lines)


# Global instance
polygon_alerts = PolygonWeatherAlerts()
