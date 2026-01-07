# core/redis_manager.py
"""Redis Connection Manager with auto-reconnect and health monitoring.

This module provides a centralized Redis connection pool that:
- Auto-reconnects on connection failures
- Provides health checks for monitoring
- Manages connection lifecycle
- Handles graceful shutdown
"""

import logging
import asyncio
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
import config


class RedisManager:
    """Manages Redis connection pool with fault tolerance."""
    
    def __init__(self):
        self.redis: Optional[Redis] = None
        self.pool: Optional[ConnectionPool] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        
    async def connect(self, retry_count: int = 3, retry_delay: float = 2.0) -> bool:
        """Connect to Redis with retry logic.
        
        Args:
            retry_count: Number of connection attempts
            retry_delay: Seconds to wait between retries
            
        Returns:
            True if connected successfully
        """
        for attempt in range(retry_count):
            try:
                logging.info(f"🔌 Connecting to Redis at {config.REDIS_HOST}:{config.REDIS_PORT} (attempt {attempt + 1}/{retry_count})...")
                
                # Create connection pool
                self.pool = ConnectionPool.from_url(
                    config.get_redis_url(),
                    max_connections=config.REDIS_MAX_CONNECTIONS,
                    decode_responses=True,  # Auto-decode bytes to strings
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    retry_on_timeout=True
                )
                
                # Create Redis client
                self.redis = Redis(connection_pool=self.pool)
                
                # Test connection
                await self.redis.ping()
                
                self._connected = True
                logging.info(f"✅ Redis connected successfully!")
                return True
                
            except RedisConnectionError as e:
                logging.warning(f"⚠️ Redis connection attempt {attempt + 1} failed: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logging.error("❌ Redis connection failed after all retries")
                    self._connected = False
                    return False
            except Exception as e:
                logging.error(f"❌ Unexpected error connecting to Redis: {e}")
                self._connected = False
                return False
        
        return False
    
    async def disconnect(self):
        """Close Redis connection gracefully."""
        if self.redis:
            try:
                await self.redis.aclose()
                logging.info("🔌 Redis disconnected")
            except Exception as e:
                logging.error(f"Error disconnecting Redis: {e}")
            finally:
                self.redis = None
                self._connected = False
        
        if self.pool:
            await self.pool.disconnect()
            self.pool = None
    
    async def ping(self) -> bool:
        """Check if Redis is reachable.
        
        Returns:
            True if Redis responds to PING
        """
        if not self.redis:
            return False
        
        try:
            return await self.redis.ping()
        except RedisError:
            return False
    
    async def get_info(self) -> dict:
        """Get Redis server information.
        
        Returns:
            Dict with Redis INFO output
        """
        if not self.redis:
            return {}
        
        try:
            return await self.redis.info()
        except RedisError as e:
            logging.error(f"Error getting Redis info: {e}")
            return {}
    
    async def get_stats(self) -> dict:
        """Get cache statistics from Redis.
        
        Returns:
            Dict with hit rate, memory usage, etc.
        """
        info = await self.get_info()
        
        if not info:
            return {
                "connected": False,
                "error": "Redis not connected"
            }
        
        # Calculate hit rate
        keyspace_hits = int(info.get('keyspace_hits', 0))
        keyspace_misses = int(info.get('keyspace_misses', 0))
        total_requests = keyspace_hits + keyspace_misses
        
        if total_requests > 0:
            hit_rate = (keyspace_hits / total_requests) * 100
        else:
            hit_rate = 0
        
        return {
            "connected": True,
            "used_memory_human": info.get('used_memory_human', 'N/A'),
            "used_memory_peak_human": info.get('used_memory_peak_human', 'N/A'),
            "total_connections_received": info.get('total_connections_received', 0),
            "keyspace_hits": keyspace_hits,
            "keyspace_misses": keyspace_misses,
            "hit_rate_pct": round(hit_rate, 2),
            "uptime_in_seconds": info.get('uptime_in_seconds', 0),
            "connected_clients": info.get('connected_clients', 0)
        }
    
    def is_connected(self) -> bool:
        """Check if Redis connection is established.
        
        Returns:
            True if connected
        """
        return self._connected
    
    async def ensure_connected(self) -> bool:
        """Ensure Redis is connected, reconnect if needed.
        
        Returns:
            True if connected (or reconnected)
        """
        if self.is_connected() and await self.ping():
            return True
        
        logging.warning("⚠️ Redis connection lost, attempting reconnect...")
        return await self.connect()
    
    async def get_client(self) -> Optional[Redis]:
        """Get Redis client (with auto-reconnect).
        
        Returns:
            Redis client or None if connection failed
        """
        if not await self.ensure_connected():
            return None
        return self.redis


# Global instance
redis_manager = RedisManager()


async def init_redis():
    """Initialize Redis connection (call at app startup)."""
    success = await redis_manager.connect()
    if not success:
        logging.warning("⚠️ Redis connection failed - caching will fall back to PostgreSQL")
    return success


async def close_redis():
    """Close Redis connection (call at app shutdown)."""
    await redis_manager.disconnect()
