# core/route_sampler.py
"""Distance-based route sampling for optimal coverage"""

from math import sqrt
from typing import List, Tuple
import logging


def sample_by_distance(coordinates: List[List[float]], interval_km: float = 5.0) -> List[List[float]]:
    """Sample route points at consistent distance intervals
    
    This ensures even coverage along the entire route, unlike index-based sampling
    which can create gaps in areas with high coordinate density.
    
    Args:
        coordinates: List of [lon, lat] coordinate pairs from OSRM
        interval_km: Distance between sample points in kilometers
        
    Returns:
        List of sampled [lon, lat] coordinate pairs
    """
    if not coordinates or len(coordinates) < 2:
        return coordinates
    
    sampled = [coordinates[0]]
    last_point = coordinates[0]
    
    # Convert km to degrees (approximate: 1 degree ≈ 111km at equator)
    threshold_degrees = interval_km / 111.0
    
    for coord in coordinates[1:]:
        # Calculate Euclidean distance in degrees
        lon_diff = coord[0] - last_point[0]
        lat_diff = coord[1] - last_point[1]
        distance_degrees = sqrt(lon_diff**2 + lat_diff**2)
        
        if distance_degrees > threshold_degrees:
            sampled.append(coord)
            last_point = coord
    
    # Always include the final point
    if coordinates[-1] not in sampled:
        sampled.append(coordinates[-1])
    
    logging.info(f"Route sampler: {len(coordinates)} coords -> {len(sampled)} samples (every {interval_km}km)")
    return sampled


def calculate_accumulated_durations(durations: List[float]) -> List[float]:
    """Calculate accumulated time at each route segment
    
    Args:
        durations: List of duration in seconds for each segment
        
    Returns:
        List of accumulated seconds from start
    """
    accumulated = [0.0]
    total = 0.0
    
    for duration in durations:
        total += duration
        accumulated.append(total)
    
    return accumulated
