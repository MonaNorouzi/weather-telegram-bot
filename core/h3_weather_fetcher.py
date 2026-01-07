# core/h3_weather_fetcher.py
"""
Lightweight H3 Weather Fetcher for pre-computed routes.

Unlike h3_weather_router.py which does both routing and weather,
this module ONLY fetches weather for an existing route geometry.

Perfect for Telegram bot where routing is done by graph_database.
"""

import asyncio
import logging
import h3
import json
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime

import config
from core.redis_manager import redis_manager
from core.openmeteo_service import openmeteo_service

logger = logging.getLogger(__name__)


class H3WeatherFetcher:
    """Fetch weather for pre-computed route using H3 caching."""
    
    def __init__(self):
        self.h3_resolution = config.H3_RESOLUTION
        self.cache_ttl = config.H3_WEATHER_CACHE_TTL
        self.max_parallel_requests = config.PARALLEL_WEATHER_REQUESTS
        
        logger.info(f"H3WeatherFetcher initialized (Resolution {self.h3_resolution})")
    
    async def get_weather_for_route(
        self,
        coordinates: List[Tuple[float, float]],
        departure_time: datetime
    ) -> Dict:
        """
        Get weather for a pre-computed route geometry.
        
        Args:
            coordinates: List of (lat, lon) tuples from routing
            departure_time: Departure time
            
        Returns:
            Dict with segments and stats
        """
        logger.info(f"🌤️ Fetching weather for route ({len(coordinates)} points)")
        
        # Step 1: Convert route to H3 cells
        h3_indices = self._coords_to_h3(coordinates)
        logger.info(f"📐 Route = {len(h3_indices)} H3 cells")
        
        # Step 2: Check cache
        cached_data, missing_indices = await self._check_cache(h3_indices)
        cache_hits = len(cached_data)
        cache_misses = len(missing_indices)
        hit_rate = (cache_hits / len(h3_indices) * 100) if h3_indices else 0
        
        logger.info(f"💾 H3 Cache: {cache_hits}/{len(h3_indices)} cached ({hit_rate:.1f}% hit)")
        
        # Step 3: Fetch missing
        new_data = {}
        if missing_indices:
            logger.info(f"⚡ Fetching {len(missing_indices)} missing cells...")
            new_data = await self._fetch_missing(missing_indices, departure_time)
            
            # Step 4: Cache new data
            if new_data:
                await self._cache_data(new_data)
        
        # Step 5: Merge
        all_data = {**cached_data, **new_data}
        
        # Step 6: Build segments
        segments = self._build_segments(h3_indices, all_data)
        
        return {
            "segments": segments,
            "stats": {
                "total_segments": len(h3_indices),
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "cache_hit_rate": round(hit_rate, 2),
                "new_api_calls": len(new_data)
            }
        }
    
    def _coords_to_h3(self, coordinates: List[Tuple[float, float]]) -> Set[str]:
        """Convert coordinates to unique H3 cells."""
        h3_indices = set()
        
        for lat, lon in coordinates:
            try:
                h3_index = h3.latlng_to_cell(lat, lon, self.h3_resolution)
                h3_indices.add(h3_index)
            except Exception as e:
                logger.warning(f"H3 conversion failed for ({lat}, {lon}): {e}")
        
        return h3_indices
    
    async def _check_cache(
        self,
        h3_indices: Set[str]
    ) -> Tuple[Dict[str, Dict], Set[str]]:
        """Bulk cache check using Redis MGET."""
        redis_client = await redis_manager.get_client()
        
        if not redis_client:
            logger.warning("Redis unavailable, all cache misses")
            return {}, h3_indices
        
        keys = [f"weather:h3:res{self.h3_resolution}:{idx}" for idx in h3_indices]
        
        try:
            values = await redis_client.mget(keys)
            
            cached_data = {}
            missing_indices = set()
            
            for h3_index, value in zip(h3_indices, values):
                if value:
                    try:
                        cached_data[h3_index] = json.loads(value)
                    except:
                        missing_indices.add(h3_index)
                else:
                    missing_indices.add(h3_index)
            
            return cached_data, missing_indices
        except Exception as e:
            logger.error(f"Redis error: {e}")
            return {}, h3_indices
    
    async def _fetch_missing(
        self,
        h3_indices: Set[str],
        forecast_time: datetime
    ) -> Dict[str, Dict]:
        """Fetch weather for missing H3 cells."""
        semaphore = asyncio.Semaphore(self.max_parallel_requests)
        
        async def fetch_one(h3_index: str):
            async with semaphore:
                try:
                    lat, lon = h3.cell_to_latlng(h3_index)
                    weather = await openmeteo_service.get_forecast_at_time(
                        lat, lon, forecast_time
                    )
                    return h3_index, weather if weather else None
                except Exception as e:
                    logger.error(f"Weather fetch error for {h3_index}: {e}")
                    return h3_index, None
        
        tasks = [fetch_one(idx) for idx in h3_indices]
        results = await asyncio.gather(*tasks)
        
        return {idx: data for idx, data in results if data is not None}
    
    async def _cache_data(self, weather_data: Dict[str, Dict]):
        """Cache weather data with TTL."""
        redis_client = await redis_manager.get_client()
        
        if not redis_client or not weather_data:
            return
        
        try:
            pipe = redis_client.pipeline()
            
            for h3_index, data in weather_data.items():
                key = f"weather:h3:res{self.h3_resolution}:{h3_index}"
                value = json.dumps(data)
                pipe.setex(key, self.cache_ttl, value)
            
            await pipe.execute()
            logger.info(f"✅ Cached {len(weather_data)} H3 cells (TTL: {self.cache_ttl}s)")
        except Exception as e:
            logger.error(f"Cache write error: {e}")
    
    def _build_segments(
        self,
        h3_indices: Set[str],
        weather_data: Dict[str, Dict]
    ) -> List[Dict]:
        """Build segment list with weather."""
        segments = []
        
        for h3_index in h3_indices:
            lat, lon = h3.cell_to_latlng(h3_index)
            weather = weather_data.get(h3_index, {})
            
            segments.append({
                "h3_index": h3_index,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "weather": weather
            })
        
        return segments


# Global instance
h3_weather_fetcher = H3WeatherFetcher()
