# core/geohash_utils.py
"""Geohashing utilities for optimized spatial lookups.

This module provides geohashing functions for:
1. Encoding coordinates to geohashes
2. Decoding geohashes to coordinates
3. Finding neighboring geohash cells (for boundary edge cases)
4. Finding candidate hashes for radius searches

Uses pygeohash library for standard geohash implementation.
"""

import pygeohash as pgh
from typing import List, Tuple
import logging

# Precision levels (in characters)
PRECISION_NODE = 7      # ~±76m - For route nodes
PRECISION_PLACE = 6     # ~±610m - For cities/places
PRECISION_CACHE = 5     # ~±2.4km - For cache proximity matching

class GeohashUtils:
    """Centralized geohashing utilities."""
    
    @staticmethod
    def encode(lat: float, lon: float, precision: int = PRECISION_NODE) -> str:
        """Encode coordinates to geohash.
        
        Args:
            lat: Latitude
            lon: Longitude
            precision: Geohash precision (characters). Default: 7 (~76m)
            
        Returns:
            Geohash string
            
        Examples:
            >>> encode(35.6892, 51.3890, 7)
            'tw3vvk4'
        """
        try:
            return pgh.encode(lat, lon, precision=precision)
        except Exception as e:
            logging.error(f"Error encoding geohash for ({lat}, {lon}): {e}")
            return ""
    
    @staticmethod
    def decode(geohash: str) -> Tuple[float, float]:
        """Decode geohash to coordinates.
        
        Args:
            geohash: Geohash string
            
        Returns:
            Tuple of (lat, lon)
            
        Examples:
            >>> decode('tw3vvk4')
            (35.6892, 51.3890)
        """
        try:
            return pgh.decode(geohash)
        except Exception as e:
            logging.error(f"Error decoding geohash '{geohash}': {e}")
            return (0.0, 0.0)
    
    @staticmethod
    def neighbors(geohash: str) -> List[str]:
        """Get all 8 neighboring geohash cells.
        
        Returns neighbors in all 8 directions: N, NE, E, SE, S, SW, W, NW
        
        Args:
            geohash: Center geohash
            
        Returns:
            List of 8 neighbor geohashes
            
        Diagram:
            NW  |  N  | NE
            ----+-----+----
             W  | geohash |  E
            ----+-----+----
            SW  |  S  | SE
        """
        try:
            # Decode center to get lat/lon
            lat, lon = pgh.decode(geohash)
            precision = len(geohash)
            
            # Approximate cell size (degrees)
            # Precision 7 ≈ 0.00068° (~76m)
            delta_map = {
                5: 0.022,    # ~2.4km
                6: 0.0055,   # ~610m
                7: 0.00068,  # ~76m
                8: 0.000085  # ~10m
            }
            delta = delta_map.get(precision, 0.001)
            
            # Calculate 8 neighbors
            neighbors_list = []
            offsets = [
                (delta, 0),      # E
                (-delta, 0),     # W
                (0, delta),      # N
                (0, -delta),     # S
                (delta, delta),  # NE
                (-delta, delta), # NW
                (delta, -delta), # SE
                (-delta, -delta) # SW
            ]
            
            for dlon, dlat in offsets:
                neighbor = pgh.encode(lat + dlat, lon + dlon, precision=precision)
                if neighbor and neighbor != geohash:  # Don't include self
                    neighbors_list.append(neighbor)
            
            # Remove duplicates (edge cases)
            return list(set(neighbors_list))
            
        except Exception as e:
            logging.error(f"Error getting neighbors for '{geohash}': {e}")
            return []
    
    @staticmethod
    def find_candidate_hashes(
        lat: float,
        lon: float,
        precision: int = PRECISION_NODE,
        include_neighbors: bool = True
    ) -> List[str]:
        """Find candidate geohashes for a coordinate.
        
        This is the KEY function for optimizing spatial queries. Instead of
        querying all nodes with ST_DWithin, we first filter by geohash.
        
        Args:
            lat: Latitude
            lon: Longitude
            precision: Geohash precision
            include_neighbors: If True, include 8 neighboring cells (recommended)
            
        Returns:
            List of geohashes to query (1 or 9 total)
            
        Usage:
            # Before (slow):
            SELECT * FROM nodes WHERE ST_DWithin(geom, point, 50)  # Full scan
            
            # After (fast):
            hashes = find_candidate_hashes(lat, lon, precision=7)
            SELECT * FROM nodes WHERE geohash = ANY($hashes) AND ST_DWithin(geom, point, 50)
        """
        center = GeohashUtils.encode(lat, lon, precision)
        
        if not center:
            return []
        
        if not include_neighbors:
            return [center]
        
        # Return center + 8 neighbors = 9 cells
        neighbors = GeohashUtils.neighbors(center)
        return [center] + neighbors if neighbors else [center]
    
    @staticmethod
    def get_prefix(geohash: str, prefix_length: int) -> str:
        """Get prefix of geohash for broader matching.
        
        Used for cache proximity searches.
        
        Args:
            geohash: Full geohash
            prefix_length: Number of characters to keep
            
        Returns:
            Prefix string
            
        Examples:
            >>> get_prefix('tw3vvk4', 4)
            'tw3v'
        """
        if not geohash or prefix_length <= 0:
            return ""
        return geohash[:min(prefix_length, len(geohash))]
    
    @staticmethod
    def validate_geohash(geohash: str) -> bool:
        """Validate that a string is a valid geohash.
        
        Args:
            geohash: String to validate
            
        Returns:
            True if valid geohash, False otherwise
        """
        if not geohash:
            return False
        
        # Geohash uses base32: 0-9, b-z (excluding a, i, l, o)
        valid_chars = set('0123456789bcdefghjkmnpqrstuvwxyz')
        return all(c in valid_chars for c in geohash.lower())
    
    @staticmethod
    def batch_encode(coordinates: List[Tuple[float, float]], precision: int = PRECISION_NODE) -> List[str]:
        """Batch encode multiple coordinates.
        
        More efficient than calling encode() in a loop for large datasets.
        
        Args:
            coordinates: List of (lat, lon) tuples
            precision: Geohash precision
            
        Returns:
            List of geohashes (same order as input)
        """
        return [GeohashUtils.encode(lat, lon, precision) for lat, lon in coordinates]


# Global instance (stateless, so singleton is fine)
geohash_utils = GeohashUtils()


# Convenience functions for direct import
def encode(lat: float, lon: float, precision: int = PRECISION_NODE) -> str:
    """Convenience function: encode coordinates to geohash."""
    return geohash_utils.encode(lat, lon, precision)


def decode(geohash: str) -> Tuple[float, float]:
    """Convenience function: decode geohash to coordinates."""
    return geohash_utils.decode(geohash)


def neighbors(geohash: str) -> List[str]:
    """Convenience function: get neighboring geohashes."""
    return geohash_utils.neighbors(geohash)


def find_candidate_hashes(lat: float, lon: float, precision: int = PRECISION_NODE, include_neighbors: bool = True) -> List[str]:
    """Convenience function: find candidate geohashes for query optimization."""
    return geohash_utils.find_candidate_hashes(lat, lon, precision, include_neighbors)
