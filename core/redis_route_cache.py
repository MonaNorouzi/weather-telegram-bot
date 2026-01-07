# core/redis_route_cache.py
"""Redis-based Route Places Cache with PostgreSQL fallback.

This module replaces the PostgreSQL-based route_places_cache with a Redis
implementation that provides sub-millisecond lookups while maintaining
PostgreSQL as a fallback for reliability.

Performance:
- Redis hit: <1ms
- Redis miss + PostgreSQL: 50-200ms (same as before)
- Expected hit rate: 95%+ (routes are frequently repeated)
"""

import logging
import json
from typing import Optional, List, Dict
from redis.exceptions import RedisError
from core.redis_manager import redis_manager
from core.graph_database import graph_db


class RedisRouteCache:
    """Manages route places caching with Redis + PostgreSQL fallback."""
    
    def __init__(self):
        self.stats = {
            "redis_hits": 0,
            "redis_misses": 0,
            "postgres_fallbacks": 0,
            "cache_errors": 0
        }
    
    def _generate_key(self, source_place_id: int, target_place_id: int) -> str:
        """Generate Redis cache key for a route.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            
        Returns:
            Cache key string
        """
        return f"route:places:{source_place_id}:{target_place_id}"
    
    async def get_cached_places(
        self,
        source_place_id: int,
        target_place_id: int
    ) -> Optional[List[Dict]]:
        """Get cached list of places for a route.
        
        Tries Redis first, falls back to PostgreSQL if Redis fails.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            
        Returns:
            List of places [{name, type, lat, lon}, ...] or None if not cached
        """
        cache_key = self._generate_key(source_place_id, target_place_id)
        
        # Try Redis first (HOT path)
        redis_client = await redis_manager.get_client()
        if redis_client:
            try:
                cached_json = await redis_client.get(cache_key)
                
                if cached_json:
                    self.stats["redis_hits"] += 1
                    logging.info(f"✅ Redis cache HIT: {cache_key}")
                    
                    # Parse and return
                    data = json.loads(cached_json)
                    return data.get("places", [])
                else:
                    self.stats["redis_misses"] += 1
                    logging.info(f"❌ Redis cache MISS: {cache_key}")
                    
            except (RedisError, json.JSONDecodeError) as e:
                logging.error(f"Redis error on get: {e}, falling back to PostgreSQL")
                self.stats["cache_errors"] += 1
        
        # Fallback to PostgreSQL (COLD path)
        return await self._get_from_postgres(source_place_id, target_place_id)
    
    async def _get_from_postgres(
        self,
        source_place_id: int,
        target_place_id: int
    ) -> Optional[List[Dict]]:
        """Get cached places from PostgreSQL.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            
        Returns:
            List of places or None
        """
        try:
            self.stats["postgres_fallbacks"] += 1
            
            async with graph_db.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT places_data, total_places
                    FROM route_places_cache
                    WHERE source_place_id = $1 AND target_place_id = $2
                """, source_place_id, target_place_id)
                
                if row:
                    places_data = row['places_data']
                    
                    # asyncpg returns JSONB as dict or string
                    if isinstance(places_data, str):
                        places_data = json.loads(places_data)
                    
                    logging.info(f"✅ PostgreSQL cache hit: {row['total_places']} places")
                    
                    # Also cache in Redis for next time
                    await self._cache_in_redis(source_place_id, target_place_id, places_data)
                    
                    return places_data
                else:
                    logging.info(f"❌ PostgreSQL cache miss")
                    return None
                    
        except Exception as e:
            logging.error(f"Error fetching from PostgreSQL: {e}")
            return None
    
    async def _cache_in_redis(
        self,
        source_place_id: int,
        target_place_id: int,
        places: List[Dict]
    ) -> bool:
        """Store places in Redis (background operation).
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            places: List of places to cache
            
        Returns:
            True if successful
        """
        redis_client = await redis_manager.get_client()
        if not redis_client:
            return False
        
        try:
            cache_key = self._generate_key(source_place_id, target_place_id)
            
            # Prepare cache data
            cache_data = {
                "places": places,
                "total": len(places),
                "cached_at": str(asyncio.get_event_loop().time())
            }
            
            # Store with 24-hour TTL (routes don't change often)
            await redis_client.setex(
                cache_key,
                86400,  # 24 hours
                json.dumps(cache_data)
            )
            
            logging.info(f"📦 Cached {len(places)} places in Redis: {cache_key}")
            return True
            
        except RedisError as e:
            logging.error(f"Error caching in Redis: {e}")
            return False
    
    async def cache_places(
        self,
        source_place_id: int,
        target_place_id: int,
        places: List[Dict]
    ) -> bool:
        """Cache list of places for a route in both Redis and PostgreSQL.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            places: List of places from Overpass [{name, type, lat, lon}, ...] 
            
        Returns:
            True if cached successfully in at least one backend
        """
        redis_success = await self._cache_in_redis(source_place_id, target_place_id, places)
        postgres_success = await self._cache_in_postgres(source_place_id, target_place_id, places)
        
        return redis_success or postgres_success
    
    async def _cache_in_postgres(
        self,
        source_place_id: int,
        target_place_id: int,
        places: List[Dict]
    ) -> bool:
        """Cache places in PostgreSQL for durability.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            places: List of places
            
        Returns:
            True if successful
        """
        try:
            # Extract only essential data
            simplified_places = []
            for p in places:
                simplified_places.append({
                    'name': p.get('name', 'Unknown'),
                    'type': p.get('type', 'place'),
                    'lat': p.get('lat'),
                    'lon': p.get('lon')
                })
            
            # Convert to JSON
            places_json = json.dumps(simplified_places)
            
            async with graph_db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO route_places_cache 
                        (source_place_id, target_place_id, places_data, total_places)
                    VALUES ($1, $2, $3::jsonb, $4)
                    ON CONFLICT (source_place_id, target_place_id)
                    DO UPDATE SET
                        places_data = EXCLUDED.places_data,
                        total_places = EXCLUDED.total_places,
                        updated_at = NOW()
                """, source_place_id, target_place_id, places_json, len(simplified_places))
            
            logging.info(f"📦 Cached {len(simplified_places)} places in PostgreSQL")
            return True
            
        except Exception as e:
            logging.error(f"Error caching in PostgreSQL: {e}")
            return False
    
    async def invalidate_route(
        self,
        source_place_id: int,
        target_place_id: int
    ) -> bool:
        """Invalidate cache for a specific route.
        
        Args:
            source_place_id: Source place ID
            target_place_id: Target place ID
            
        Returns:
            True if invalidated successfully
        """
        cache_key = self._generate_key(source_place_id, target_place_id)
        redis_deleted = False
        postgres_deleted = False
        
        # Delete from Redis
        redis_client = await redis_manager.get_client()
        if redis_client:
            try:
                deleted = await redis_client.delete(cache_key)
                redis_deleted = deleted > 0
                if redis_deleted:
                    logging.info(f"🗑️ Deleted from Redis: {cache_key}")
            except RedisError as e:
                logging.error(f"Error deleting from Redis: {e}")
        
        # Delete from PostgreSQL
        try:
            async with graph_db.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM route_places_cache
                    WHERE source_place_id = $1 AND target_place_id = $2
                """, source_place_id, target_place_id)
                postgres_deleted = True
                logging.info(f"🗑️ Deleted from PostgreSQL")
        except Exception as e:
            logging.error(f"Error deleting from PostgreSQL: {e}")
        
        return redis_deleted or postgres_deleted
    
    async def clear_all(self) -> int:
        """Clear all route caches.
        
        Returns:
            Number of entries cleared
        """
        count = 0
        
        # Clear Redis
        redis_client = await redis_manager.get_client()
        if redis_client:
            try:
                keys = await redis_client.keys("route:places:*")
                if keys:
                    deleted = await redis_client.delete(*keys)
                    count += deleted
                    logging.info(f"🗑️ Cleared {deleted} routes from Redis")
            except RedisError as e:
                logging.error(f"Error clearing Redis: {e}")
        
        # Clear PostgreSQL
        try:
            async with graph_db.acquire() as conn:
                result = await conn.execute("DELETE FROM route_places_cache")
                logging.info("🗑️ Cleared all routes from PostgreSQL")
        except Exception as e:
            logging.error(f"Error clearing PostgreSQL: {e}")
        
        return count
    
    def get_stats(self) -> dict:
        """Get cache statistics.
        
        Returns:
            Dict with hit rates and counts
        """
        total_redis = self.stats["redis_hits"] + self.stats["redis_misses"]
        if total_redis > 0:
            redis_hit_rate = (self.stats["redis_hits"] / total_redis) * 100
        else:
            redis_hit_rate = 0
        
        return {
            **self.stats,
            "total_redis_requests": total_redis,
            "redis_hit_rate_pct": round(redis_hit_rate, 2)
        }


# Global instance
redis_route_cache = RedisRouteCache()


# Import asyncio for cache_data timestamp
import asyncio
