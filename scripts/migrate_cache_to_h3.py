# scripts/migrate_cache_to_h3.py
"""
Cache Migration Script: Route-based → H3-based

This script helps migrate from the old route-based caching system to the new
H3 segment-based caching system. It provides multiple options for migration.

Usage:
    python scripts/migrate_cache_to_h3.py [--mode {stats|clear|warm}]
    
Options:
    --mode stats: Show current cache statistics (default)
    --mode clear: Clear old route caches (recommended for clean migration)
    --mode warm: Warm up H3 cache with common routes
"""

import asyncio
import argparse
import logging
import json
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.redis_manager import redis_manager
from core.h3_weather_router import weather_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def show_cache_stats():
    """Display current cache statistics."""
    logger.info("=" * 60)
    logger.info("CACHE STATISTICS - BEFORE MIGRATION")
    logger.info("=" * 60)
    
    redis_client = await redis_manager.get_client()
    if not redis_client:
        logger.error("❌ Redis unavailable!")
        return
    
    try:
        # Count old route cache keys
        route_keys = []
        async for key in redis_client.scan_iter(match="route:places:*"):
            route_keys.append(key)
        
        # Count old weather cache keys (geohash-based)
        old_weather_keys = []
        async for key in redis_client.scan_iter(match="weather:*"):
            # Exclude new H3 keys
            if not key.decode().startswith("weather:h3:"):
                old_weather_keys.append(key)
        
        # Count new H3 weather cache keys
        h3_keys = []
        async for key in redis_client.scan_iter(match="weather:h3:res*"):
            h3_keys.append(key)
        
        # Get Redis memory usage
        info = await redis_client.info('memory')
        memory_used_mb = info['used_memory'] / 1024 / 1024
        
        # Display results
        logger.info(f"\n📊 Cache Statistics:")
        logger.info(f"   Old route cache keys:    {len(route_keys):,}")
        logger.info(f"   Old weather cache keys:  {len(old_weather_keys):,}")
        logger.info(f"   New H3 cache keys:       {len(h3_keys):,}")
        logger.info(f"   Total Redis memory:      {memory_used_mb:.2f} MB")
        
        if route_keys:
            logger.info(f"\n🔍 Sample old route keys:")
            for key in route_keys[:5]:
                logger.info(f"   - {key.decode()}")
        
        if h3_keys:
            logger.info(f"\n🔍 Sample new H3 keys:")
            for key in h3_keys[:5]:
                logger.info(f"   - {key.decode()}")
        
        logger.info("=" * 60)
        
        # Recommendations
        if len(route_keys) > 0 or len(old_weather_keys) > 0:
            logger.info("\n💡 RECOMMENDATION:")
            logger.info("   Run with --mode clear to remove old cache keys")
            logger.info("   This will free up memory for new H3-based cache")
        else:
            logger.info("\n✅ No old cache keys found - ready for H3 caching!")
        
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")


async def clear_old_cache():
    """Clear old route-based and weather caches."""
    logger.info("=" * 60)
    logger.info("CLEARING OLD CACHE KEYS")
    logger.info("=" * 60)
    
    redis_client = await redis_manager.get_client()
    if not redis_client:
        logger.error("❌ Redis unavailable!")
        return
    
    try:
        # Count before
        route_keys = []
        async for key in redis_client.scan_iter(match="route:places:*"):
            route_keys.append(key)
        
        old_weather_keys = []
        async for key in redis_client.scan_iter(match="weather:*"):
            if not key.decode().startswith("weather:h3:"):
                old_weather_keys.append(key)
        
        total_old_keys = len(route_keys) + len(old_weather_keys)
        
        if total_old_keys == 0:
            logger.info("✅ No old cache keys to clear!")
            return
        
        logger.warning(f"\n⚠️  About to delete {total_old_keys:,} old cache keys:")
        logger.warning(f"   - Route cache: {len(route_keys):,}")
        logger.warning(f"   - Weather cache: {len(old_weather_keys):,}")
        
        # Confirm
        print("\n❓ Continue? (yes/no): ", end='')
        confirm = input().strip().lower()
        
        if confirm != 'yes':
            logger.info("❌ Migration cancelled")
            return
        
        # Delete route cache keys
        if route_keys:
            logger.info(f"\n🗑️  Deleting {len(route_keys):,} route cache keys...")
            for i, key in enumerate(route_keys, 1):
                await redis_client.delete(key)
                if i % 100 == 0:
                    logger.info(f"   Progress: {i}/{len(route_keys)}")
        
        # Delete old weather cache keys
        if old_weather_keys:
            logger.info(f"\n🗑️  Deleting {len(old_weather_keys):,} weather cache keys...")
            for i, key in enumerate(old_weather_keys, 1):
                await redis_client.delete(key)
                if i % 100 == 0:
                    logger.info(f"   Progress: {i}/{len(old_weather_keys)}")
        
        logger.info("\n✅ Old cache cleared successfully!")
        logger.info("   New H3 cache will warm up naturally as routes are requested")
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")


async def warm_h3_cache():
    """Pre-warm H3 cache with common routes."""
    logger.info("=" * 60)
    logger.info("WARMING H3 CACHE WITH COMMON ROUTES")
    logger.info("=" * 60)
    
    # Common routes in Iran (lat, lon)
    common_routes = [
        {
            "name": "Tehran → Mashhad",
            "origin": (35.6892, 51.3890),
            "dest": (36.2974, 59.6062)
        },
        {
            "name": "Tehran → Isfahan",
            "origin": (35.6892, 51.3890),
            "dest": (32.6546, 51.6680)
        },
        {
            "name": "Tehran → Shiraz",
            "origin": (35.6892, 51.3890),
            "dest": (29.5918, 52.5836)
        },
        {
            "name": "Tehran → Tabriz",
            "origin": (35.6892, 51.3890),
            "dest": (38.0962, 46.2738)
        },
        {
            "name": "Isfahan → Shiraz",
            "origin": (32.6546, 51.6680),
            "dest": (29.5918, 52.5836)
        }
    ]
    
    logger.info(f"\n🔥 Will warm cache with {len(common_routes)} common routes\n")
    
    total_segments = 0
    total_cache_misses = 0
    
    for i, route in enumerate(common_routes, 1):
        logger.info(f"[{i}/{len(common_routes)}] Processing: {route['name']}")
        
        try:
            result = await weather_router.get_route_with_weather(
                origin=route['origin'],
                dest=route['dest']
            )
            
            if result['success']:
                stats = result['stats']
                total_segments += stats['total_segments']
                total_cache_misses += stats['cache_misses']
                
                logger.info(
                    f"   ✅ {stats['total_segments']} segments, "
                    f"{stats['cache_misses']} new, "
                    f"{stats['cache_hits']} cached"
                )
            else:
                logger.warning(f"   ⚠️  Failed: {result.get('error')}")
        
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
        
        # Small delay to respect API rate limits
        await asyncio.sleep(2)
    
    logger.info("\n" + "=" * 60)
    logger.info("WARMUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total segments processed: {total_segments:,}")
    logger.info(f"New cache entries: {total_cache_misses:,}")
    logger.info(f"Cache reuses: {total_segments - total_cache_misses:,}")
    
    if total_segments > 0:
        reuse_rate = (total_segments - total_cache_misses) / total_segments * 100
        logger.info(f"Reuse rate: {reuse_rate:.1f}%")


async def main():
    parser = argparse.ArgumentParser(
        description='Migrate from route-based to H3-based caching'
    )
    parser.add_argument(
        '--mode',
        choices=['stats', 'clear', 'warm'],
        default='stats',
        help='Migration mode (default: stats)'
    )
    
    args = parser.parse_args()
    
    logger.info("\n🔄 H3 Cache Migration Tool")
    logger.info(f"Mode: {args.mode}\n")
    
    try:
        if args.mode == 'stats':
            await show_cache_stats()
        elif args.mode == 'clear':
            await clear_old_cache()
        elif args.mode == 'warm':
            await warm_h3_cache()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}", exc_info=True)
    finally:
        # Cleanup
        await redis_manager.close()
        logger.info("\n👋 Done!\n")


if __name__ == "__main__":
    asyncio.run(main())
