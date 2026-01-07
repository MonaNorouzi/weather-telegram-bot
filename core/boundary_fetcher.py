"""City Boundary Service - Add get_city_boundary method to existing OverpassService.

This extends the existing Overpass service to support boundary fetching
in addition to the existing route places functionality.
"""

import aiohttp
import logging
import config
from typing import Optional, Dict, List, Tuple

async def get_city_boundary(city_name: str, country: str = "Iran") -> Optional[Dict]:
    """Get administrative boundary polygon for a city from Overpass API.
    
    Args:
        city_name: City name (e.g., "Tehran", "Semnan")
        country: Country name for disambiguation (default: "Iran")
        
    Returns:
        Dict with:
        - coordinates: List of (lat, lon) tuples forming the boundary
        - center: (lat, lon) of the boundary center
        - osm_id: OpenStreetMap relation ID
        - admin_level: Administrative level (typically 8 for cities)
    """
    BASE_URL = "https://overpass-api.de/api/interpreter"
    
    # Build Overpass QL query for administrative boundaries
    # admin_level=8 for cities, admin_level=6 for provinces
    query = f"""
    [out:json][timeout:25];
    area[name="{country}"]->.country;
    (
      relation["boundary"="administrative"]["admin_level"~"^(6|8)$"]["name"="{city_name}"](area.country);
    );
    out geom;
    """
    
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                BASE_URL,
                data={"data": query},
                proxy=config.PROXY_URL,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    logging.error(f"Overpass API error: {resp.status}")
                    return None
                
                data = await resp.json()
                elements = data.get("elements", [])
                
                if not elements:
                    logging.warning(f"No boundary found for {city_name}")
                    return None
                
                # Get the first (most relevant) result
                relation = elements[0]
                
                # Extract boundary coordinates from members
                boundary_coords = _extract_boundary_coords(relation)
                
                if not boundary_coords:
                    logging.warning(f"Could not extract coordinates for {city_name}")
                    return None
                
                # Calculate center point
                center = _calculate_center(boundary_coords)
                
                result = {
                    "coordinates": boundary_coords,
                    "center": center,
                    "osm_id": relation.get("id"),
                    "admin_level": relation.get("tags", {}).get("admin_level"),
                    "name": relation.get("tags", {}).get("name"),
                }
                
                logging.info(f"✅ Found boundary for {city_name}: {len(boundary_coords)} points")
                return result
                
    except Exception as e:
        logging.error(f"Overpass API error for {city_name}: {e}")
        return None


def _extract_boundary_coords(relation: Dict) -> List[Tuple[float, float]]:
    """Extract boundary coordinates from Overpass relation response."""
    coords = []
    
    # Overpass returns geometry in 'members' for relations
    members = relation.get("members", [])
    
    for member in members:
        if member.get("role") == "outer":  # Outer boundary
            geometry = member.get("geometry", [])
            for point in geometry:
                lat = point.get("lat")
                lon = point.get("lon")
                if lat is not None and lon is not None:
                    coords.append((lat, lon))
    
    # If no outer members, try direct 'bounds'
    if not coords and "bounds" in relation:
        bounds = relation["bounds"]
        # Create a simple rectangle from bounds
        coords = [
            (bounds["minlat"], bounds["minlon"]),
            (bounds["minlat"], bounds["maxlon"]),
            (bounds["maxlat"], bounds["maxlon"]),
            (bounds["maxlat"], bounds["minlon"]),
            (bounds["minlat"], bounds["minlon"])  # Close the polygon
        ]
    
    return coords


def _calculate_center(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Calculate the geometric center of a polygon."""
    if not coords:
        return (0, 0)
    
    avg_lat = sum(lat for lat, lon in coords) / len(coords)
    avg_lon = sum(lon for lat, lon in coords) / len(coords)
    
    return (avg_lat, avg_lon)
