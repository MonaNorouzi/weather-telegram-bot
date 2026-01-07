# core/h3_weather_router.py
"""
H3-based Weather Router with Delta Caching.

This module implements intelligent segment-based caching using Uber H3 geospatial
indexing. Instead of caching entire routes, it caches weather data for individual
H3 hexagons, dramatically improving cache hit rates and reducing API calls.

Key Features:
- Resolution 7 H3 indexing (~5km hexagons) for optimal weather accuracy vs memory
- Delta-caching: Only fetch weather for uncached segments
- Parallel weather API calls with rate limiting
- Sub-10s latency target for most routes
- Graceful degradation (OSRM/Redis failures)

Architecture:
    1. OSRM → Route Geometry (polyline)
    2. Geometry → H3 Indices (Resolution 7)
    3. Redis MGET → Identify cached vs missing segments
    4. Weather API → Fetch only missing (Delta)
    5. Redis MSET → Cache new segments (60min TTL)
    6. Return merged results

Example:
    >>> router = WeatherRouter()
    >>> result = await router.get_route_with_weather(
    ...     origin=(35.6892, 51.3890),  # Tehran
    ...     dest=(36.2974, 59.6062)     # Mashhad
    ... )
    >>> print(f"Route: {result['distance_km']}km, {len(result['segments'])} segments")
    >>> print(f"Cache hits: {result['stats']['cache_hits']}/{result['stats']['total_segments']}")
"""

import asyncio
import logging
import h3
import polyline
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime, timedelta
import json

import config
from core.redis_manager import redis_manager
from core.openmeteo_service import openmeteo_service

logger = logging.getLogger(__name__)


class WeatherRouter:
    """
    Main weather routing engine with H3-based segment caching.
    
    This class coordinates OSRM routing, H3 spatial indexing, Redis caching,
    and weather API calls to provide fast route weather forecasts.
    """
    
    def __init__(self):
        # H3 Configuration
        # Resolution 7 is the "Goldilocks zone":
        # - Average hexagon edge: ~5.16 km
        # - Area: ~25.18 km²
        # - Weather accuracy: Excellent (weather is uniform within 5km)
        # - Memory usage: ~450K hexagons cover Iran vs 15M for Resolution 8
        # - Cache hit rate: High reusability across different routes
        self.h3_resolution = config.H3_RESOLUTION
        
        # Cache Configuration
        self.cache_ttl = config.H3_WEATHER_CACHE_TTL  # 60 minutes default
        
        # Rate Limiting for Weather API
        # Prevents overwhelming the weather service with parallel requests
        self.max_parallel_weather_requests = config.PARALLEL_WEATHER_REQUESTS
        
        # Statistics
        self.stats = {
            "total_routes": 0,
            "total_segments_processed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls": 0,
            "osrm_errors": 0,
            "redis_errors": 0,
            "weather_api_errors": 0
        }
        
        logger.info(f"WeatherRouter initialized with H3 Resolution {self.h3_resolution}")
    
    async def get_route_with_weather(
        self,
        origin: Tuple[float, float],
        dest: Tuple[float, float],
        departure_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get route with weather forecast for each segment.
        
        This is the main public API. It orchestrates all the delta-caching logic.
        
        Args:
            origin: (latitude, longitude) of starting point
            dest: (latitude, longitude) of destination
            departure_time: Departure time (default: now)
            
        Returns:
            Dict containing:
                - route: OSRM route data (distance, duration, geometry)
                - segments: List of H3 segments with weather data
                - stats: Cache performance statistics
                - errors: List of any non-fatal errors encountered
        
        Raises:
            OSRMConnectionError: If OSRM is unavailable and no fallback
            ValueError: If inputs are invalid
        """
        self.stats["total_routes"] += 1
        errors = []
        
        if departure_time is None:
            departure_time = datetime.now()
        
        logger.info(f"🚀 Route request: {origin} → {dest} at {departure_time}")
        
        # Step 1: Get route geometry from OSRM
        try:
            route_data = await self._get_route_from_osrm(origin, dest)
            if not route_data:
                raise ValueError("Failed to get route from OSRM")
        except Exception as e:
            logger.error(f"OSRM error: {e}")
            self.stats["osrm_errors"] += 1
            errors.append(f"OSRM error: {str(e)}")
            return {
                "success": False,
                "error": "Routing service unavailable",
                "errors": errors,
                "stats": self._get_request_stats()
            }
        
        # Step 2: Convert route geometry to H3 indices
        h3_indices = self._route_geometry_to_h3(route_data["coordinates"])
        logger.info(f"📐 Route converted to {len(h3_indices)} unique H3 segments")
        
        # Step 3: Smart cache check - identify what's cached vs missing
        cached_data, missing_indices = await self._check_h3_cache(h3_indices, departure_time)
        
        cache_hit_rate = (len(cached_data) / len(h3_indices) * 100) if h3_indices else 0
        logger.info(
            f"💾 Cache: {len(cached_data)} hits, {len(missing_indices)} misses "
            f"({cache_hit_rate:.1f}% hit rate)"
        )
        
        self.stats["total_segments_processed"] += len(h3_indices)
        self.stats["cache_hits"] += len(cached_data)
        self.stats["cache_misses"] += len(missing_indices)
        
        # Step 4: Fetch weather ONLY for missing segments (Delta)
        new_weather_data = {}
        if missing_indices:
            logger.info(f"🌤️  Fetching weather for {len(missing_indices)} missing segments...")
            new_weather_data = await self._fetch_missing_weather(
                missing_indices,
                departure_time,
                errors
            )
            self.stats["api_calls"] += len(new_weather_data)
            
            # Step 5: Cache the newly fetched data
            if new_weather_data:
                await self._cache_weather_data(new_weather_data, departure_time)
        
        # Step 6: Merge cached + fresh data
        all_weather_data = {**cached_data, **new_weather_data}
        
        # Step 7: Build final response with segments
        segments = self._build_segments(h3_indices, all_weather_data, route_data["coordinates"])
        
        return {
            "success": True,
            "route": {
                "distance_km": round(route_data["distance"] / 1000, 2),
                "duration_hours": round(route_data["duration"] / 3600, 2),
                "origin": origin,
                "destination": dest,
                "departure_time": departure_time.isoformat()
            },
            "segments": segments,
            "stats": {
                "total_segments": len(h3_indices),
                "cache_hits": len(cached_data),
                "cache_misses": len(missing_indices),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "new_api_calls": len(new_weather_data)
            },
            "errors": errors if errors else None
        }
    
    async def _get_route_from_osrm(
        self,
        origin: Tuple[float, float],
        dest: Tuple[float, float]
    ) -> Optional[Dict]:
        """
        Get route geometry from OSRM (local or fallback to public).
        
        Args:
            origin: (lat, lon) starting point
            dest: (lat, lon) destination
            
        Returns:
            Dict with coordinates, distance, duration
        """
        import aiohttp
        
        # Format: lon,lat;lon,lat (OSRM uses lon,lat order!)
        coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        
        # Try local OSRM first
        osrm_url = config.OSRM_URL
        url = f"{osrm_url}/route/v1/driving/{coords}"
        params = {
            "overview": "full",
            "geometries": "polyline"  # Encoded polyline for efficiency
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == "Ok" and data.get("routes"):
                            route = data["routes"][0]
                            # Decode polyline to coordinates
                            encoded_polyline = route["geometry"]
                            coordinates = polyline.decode(encoded_polyline)
                            
                            return {
                                "coordinates": coordinates,  # List of (lat, lon) tuples
                                "distance": route["distance"],  # meters
                                "duration": route["duration"]   # seconds
                            }
                    logger.warning(f"OSRM returned status {resp.status}")
        except Exception as e:
            logger.warning(f"Local OSRM failed: {e}")
            
            # Fallback to public OSRM if enabled
            if config.OSRM_FALLBACK_PUBLIC:
                logger.info("Falling back to public OSRM...")
                try:
                    fallback_url = f"https://router.project-osrm.org/route/v1/driving/{coords}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(fallback_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data.get("code") == "Ok" and data.get("routes"):
                                    route = data["routes"][0]
                                    coordinates = polyline.decode(route["geometry"])
                                    return {
                                        "coordinates": coordinates,
                                        "distance": route["distance"],
                                        "duration": route["duration"]
                                    }
                except Exception as fallback_error:
                    logger.error(f"Fallback OSRM also failed: {fallback_error}")
        
        return None
    
    def _route_geometry_to_h3(self, coordinates: List[Tuple[float, float]]) -> Set[str]:
        """
        Convert route geometry (list of lat/lon points) to unique H3 indices.
        
        This handles the "snap to road" logic implicitly via OSRM's geometry.
        We deduplicate H3 indices to avoid redundant cache checks.
        
        Args:
            coordinates: List of (lat, lon) tuples from OSRM
            
        Returns:
            Set of unique H3 index strings
        """
        h3_indices = set()
        
        for lat, lon in coordinates:
            try:
                # Convert lat/lon to H3 index at configured resolution
                # H3 v4 uses latlng_to_cell instead of geo_to_h3
                h3_index = h3.latlng_to_cell(lat, lon, self.h3_resolution)
                h3_indices.add(h3_index)
            except Exception as e:
                logger.warning(f"Failed to convert ({lat}, {lon}) to H3: {e}")
        
        return h3_indices
    
    async def _check_h3_cache(
        self,
        h3_indices: Set[str],
        forecast_time: datetime
    ) -> Tuple[Dict[str, Dict], Set[str]]:
        """
        Bulk cache lookup using Redis MGET (single round-trip).
        
        Args:
            h3_indices: Set of H3 index strings to check
            forecast_time: Time for weather forecast
            
        Returns:
            Tuple of (cached_data_dict, missing_indices_set)
        """
        redis_client = await redis_manager.get_client()
        
        if not redis_client:
            logger.warning("Redis unavailable, treating all as cache misses")
            self.stats["redis_errors"] += 1
            return {}, h3_indices
        
        # Generate Redis keys: weather:h3:res7:{h3_index}
        # Note: We're storing the latest weather for each H3 cell, not time-specific
        # Time-based filtering happens in the weather data itself
        keys = [f"weather:h3:res{self.h3_resolution}:{idx}" for idx in h3_indices]
        
        try:
            # MGET - bulk get in single round-trip
            values = await redis_client.mget(keys)
            
            cached_data = {}
            missing_indices = set()
            
            for h3_index, value in zip(h3_indices, values):
                if value:
                    try:
                        weather_data = json.loads(value)
                        cached_data[h3_index] = weather_data
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode cached data for {h3_index}")
                        missing_indices.add(h3_index)
                else:
                    missing_indices.add(h3_index)
            
            return cached_data, missing_indices
            
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            self.stats["redis_errors"] += 1
            # On error, treat all as misses
            return {}, h3_indices
    
    async def _fetch_missing_weather(
        self,
        h3_indices: Set[str],
        forecast_time: datetime,
        errors: List[str]
    ) -> Dict[str, Dict]:
        """
        Fetch weather data ONLY for missing H3 segments (Delta).
        
        Uses asyncio semaphore for rate limiting to respect weather API limits.
        
        Args:
            h3_indices: Set of H3 indices needing weather data
            forecast_time: Forecast time
            errors: List to append non-fatal errors
            
        Returns:
            Dict mapping H3 index to weather data
        """
        semaphore = asyncio.Semaphore(self.max_parallel_weather_requests)
        
        async def fetch_one(h3_index: str) -> Tuple[str, Optional[Dict]]:
            """Fetch weather for a single H3 hexagon."""
            async with semaphore:
                try:
                    # Convert H3 index back to lat/lon (cell center)
                    # H3 v4 uses cell_to_latlng instead of h3_to_geo
                    lat, lon = h3.cell_to_latlng(h3_index)
                    
                    # Call weather API
                    weather = await openmeteo_service.get_forecast_at_time(
                        lat, lon, forecast_time
                    )
                    
                    if weather:
                        return h3_index, weather
                    else:
                        errors.append(f"No weather data for H3 {h3_index}")
                        return h3_index, None
                        
                except Exception as e:
                    logger.error(f"Weather API error for {h3_index}: {e}")
                    self.stats["weather_api_errors"] += 1
                    errors.append(f"Weather API error: {str(e)}")
                    return h3_index, None
        
        # Fetch all in parallel (with semaphore limiting concurrency)
        tasks = [fetch_one(idx) for idx in h3_indices]
        results = await asyncio.gather(*tasks)
        
        # Filter out failures
        weather_data = {idx: data for idx, data in results if data is not None}
        
        return weather_data
    
    async def _cache_weather_data(
        self,
        weather_data: Dict[str, Dict],
        forecast_time: datetime
    ) -> None:
        """
        Cache newly fetched weather data in Redis with TTL.
        
        Uses MSET for batch writes (single round-trip).
        
        Args:
            weather_data: Dict mapping H3 index to weather data
            forecast_time: Forecast time (for logging)
        """
        redis_client = await redis_manager.get_client()
        
        if not redis_client or not weather_data:
            return
        
        try:
            # Use pipeline for batch SET with TTL
            pipe = redis_client.pipeline()
            
            for h3_index, data in weather_data.items():
                key = f"weather:h3:res{self.h3_resolution}:{h3_index}"
                value = json.dumps(data)
                pipe.setex(key, self.cache_ttl, value)
            
            await pipe.execute()
            logger.info(f"✅ Cached {len(weather_data)} weather segments (TTL: {self.cache_ttl}s)")
            
        except Exception as e:
            logger.error(f"Failed to cache weather data: {e}")
            self.stats["redis_errors"] += 1
    
    def _build_segments(
        self,
        h3_indices: Set[str],
        weather_data: Dict[str, Dict],
        coordinates: List[Tuple[float, float]]
    ) -> List[Dict]:
        """
        Build final segment list with weather data.
        
        Args:
            h3_indices: All H3 indices for the route
            weather_data: Weather data for each H3 index
            coordinates: Original route coordinates
            
        Returns:
            List of segment dicts with location and weather
        """
        segments = []
        
        for h3_index in h3_indices:
            # H3 v4 uses cell_to_latlng instead of h3_to_geo
            lat, lon = h3.cell_to_latlng(h3_index)
            weather = weather_data.get(h3_index, {
                "temperature": None,
                "description": "No data",
                "icon": "❓"
            })
            
            segments.append({
                "h3_index": h3_index,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "weather": weather
            })
        
        return segments
    
    def _get_request_stats(self) -> Dict:
        """Get statistics for the current request."""
        return {
            "cache_hit_rate": round(
                (self.stats["cache_hits"] / self.stats["total_segments_processed"] * 100)
                if self.stats["total_segments_processed"] > 0 else 0,
                2
            ),
            **self.stats
        }
    
    def get_stats(self) -> Dict:
        """Get global statistics for all requests."""
        return self._get_request_stats()


# Global instance
weather_router = WeatherRouter()
