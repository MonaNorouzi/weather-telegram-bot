# handlers/cache_admin_handler.py
"""Admin commands for managing Redis cache.

Commands:
- /cachestats - View cache statistics
- /clearcache <type> - Clear specific cache type
- /reloadgeo - Reload geospatial index
"""

import logging
from telethon import events, Button
from core.redis_manager import redis_manager
from core.redis_route_cache import redis_route_cache
from core.redis_weather_cache import redis_weather_cache
from core.redis_geospatial_cache import redis_geo_cache
import config


def register_cache_admin_handlers(client):
    """Register cache management admin handlers."""
    
    @client.on(events.NewMessage(pattern=r'^/cachestats$'))
    async def cmd_cache_stats(event):
        """Display comprehensive cache statistics."""
        # Check admin permission
        if event.sender_id != config.ADMIN_ID:
            await event.respond("❌ Admin only command")
            return
        
        try:
            # Get Redis server stats
            redis_stats = await redis_manager.get_stats()
            
            # Get module-specific stats
            route_stats = redis_route_cache.get_stats()
            weather_stats = redis_weather_cache.get_stats()
            geo_stats = redis_geo_cache.get_stats()
            
            # Format message
            if redis_stats.get("connected"):
                msg = "📊 **Redis Cache Statistics**\n\n"
                
                # Server stats
                msg += "**🔴 Redis Server:**\n"
                msg += f"• Memory: {redis_stats.get('used_memory_human', 'N/A')}\n"
                msg += f"• Peak Memory: {redis_stats.get('used_memory_peak_human', 'N/A')}\n"
                msg += f"• Hit Rate: {redis_stats.get('hit_rate_pct', 0):.2f}%\n"
                msg += f"• Clients: {redis_stats.get('connected_clients', 0)}\n"
                msg += f"• Uptime: {redis_stats.get('uptime_in_seconds', 0) // 3600}h\n\n"
                
                # Route cache stats
                msg += "**🛣️ Route Places Cache:**\n"
                msg += f"• Redis Hits: {route_stats.get('redis_hits', 0)}\n"
                msg += f"• Redis Misses: {route_stats.get('redis_misses', 0)}\n"
                msg += f"• PostgreSQL Fallbacks: {route_stats.get('postgres_fallbacks', 0)}\n"
                msg += f"• Hit Rate: {route_stats.get('redis_hit_rate_pct', 0):.2f}%\n\n"
                
                # Weather cache stats
                msg += "**🌦️ Weather Cache:**\n"
                msg += f"• Cache Hits: {weather_stats.get('cache_hits', 0)}\n"
                msg += f"• Cache Misses: {weather_stats.get('cache_misses', 0)}\n"
                msg += f"• Stale Serves: {weather_stats.get('stale_serves', 0)}\n"
                msg += f"• Hit Rate: {weather_stats.get('hit_rate_pct', 0):.2f}%\n"
                
                # Singleflight stats
                sf_stats = weather_stats.get('singleflight_stats', {})
                if sf_stats:
                    msg += f"• Singleflight Dedup Rate: {sf_stats.get('dedup_rate_pct', 0):.2f}%\n"
                msg += "\n"
                
                # Geospatial stats
                msg += "**📍 Geospatial Cache:**\n"
                msg += f"• Redis Hits: {geo_stats.get('redis_hits', 0)}\n"
                msg += f"• PostgreSQL Fallbacks: {geo_stats.get('postgres_fallbacks', 0)}\n"
                msg += f"• Nodes Loaded: {geo_stats.get('nodes_loaded', 0)}\n"
                
            else:
                msg = "❌ **Redis Not Connected**\n\n"
                msg += "Caching is falling back to PostgreSQL.\n"
                msg += f"Error: {redis_stats.get('error', 'Unknown')}"
            
            await event.respond(msg)
            
        except Exception as e:
            logging.error(f"Error getting cache stats: {e}")
            await event.respond(f"❌ Error: {e}")
    
    @client.on(events.NewMessage(pattern=r'^/clearcache\s*(.*)$'))
    async def cmd_clear_cache(event):
        """Clear specific cache types."""
        # Check admin permission
        if event.sender_id != config.ADMIN_ID:
            await event.respond("❌ Admin only command")
            return
        
        try:
            cache_type = event.pattern_match.group(1).strip().lower()
            
            if not cache_type or cache_type == "help":
                await event.respond(
                    "**Cache Clear Options:**\n\n"
                    "/clearcache routes - Clear route places cache\n"
                    "/clearcache weather - Clear weather cache\n"
                    "/clearcache geo - Clear geospatial index\n"
                    "/clearcache all - Clear everything"
                )
                return
            
            redis_client = await redis_manager.get_client()
            if not redis_client:
                await event.respond("❌ Redis not connected")
                return
            
            cleared_count = 0
            
            if cache_type in ["routes", "all"]:
                count = await redis_route_cache.clear_all()
                cleared_count += count
                logging.info(f"Cleared {count} route cache entries")
            
            if cache_type in ["weather", "all"]:
                keys = await redis_client.keys("weather:*")
                if keys:
                    deleted = await redis_client.delete(*keys)
                    cleared_count += deleted
                    logging.info(f"Cleared {deleted} weather cache entries")
            
            if cache_type in ["geo", "all"]:
                success = await redis_geo_cache.clear_index()
                if success:
                    cleared_count += 1
                    logging.info("Cleared geospatial index")
            
            await event.respond(
                f"✅ **Cache Cleared**\n\n"
                f"Type: {cache_type}\n"
                f"Entries removed: {cleared_count}"
            )
            
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")
            await event.respond(f"❌ Error: {e}")
    
    @client.on(events.NewMessage(pattern=r'^/reloadgeo$'))
    async def cmd_reload_geo(event):
        """Reload geospatial index from database."""
        # Check admin permission
        if event.sender_id != config.ADMIN_ID:
            await event.respond("❌ Admin only command")
            return
        
        try:
            await event.respond("🔄 Reloading geospatial index...")
            
            # Force reload
            node_count = await redis_geo_cache.load_all_nodes(force_reload=True)
            
            await event.respond(
                f"✅ **Geospatial Index Reloaded**\n\n"
                f"Nodes loaded: {node_count}"
            )
            
        except Exception as e:
            logging.error(f"Error reloading geo index: {e}")
            await event.respond(f"❌ Error: {e}")
    
    @client.on(events.NewMessage(pattern=r'^/clearall$'))
    async def cmd_clear_all(event):
        """Clear ALL caches - Quick reset for testing."""
        if event.sender_id != config.ADMIN_ID:
            await event.respond("❌ فقط برای ادمین")
            return
        
        try:
            msg = await event.respond("🔄 پاک کردن همه کش‌ها...")
            
            redis_client = await redis_manager.get_client()
            if not redis_client:
                await msg.edit("❌ Redis غیرفعال است!")
                return
            
            redis_count = 0
            postgres_count = 0
            
            # Clear all Redis patterns
            for pattern in ["route:*", "weather:*", "places:*", "geospatial:*"]:
                keys = await redis_client.keys(pattern)
                if keys:
                    redis_count += await redis_client.delete(*keys)
            
            # Clear PostgreSQL routes
            from core.graph_database import graph_db
            async with graph_db.acquire() as conn:
                try:
                    result = await conn.execute("DELETE FROM routes")
                    postgres_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                except:
                    pass
            
            # Reset stats
            redis_route_cache.stats = {"redis_hits": 0, "redis_misses": 0, "postgres_fallbacks": 0, "cache_errors": 0}
            redis_weather_cache.stats = {"cache_hits": 0, "cache_misses": 0, "stale_serves": 0}
            redis_geo_cache.stats = {"redis_hits": 0, "postgres_fallbacks": 0, "nodes_loaded": 0}
            
            await msg.edit(
                f"✅ **همه کش‌ها پاک شد!**\n\n"
                f"🗑️ Redis: {redis_count} keys\n"
                f"🗑️ PostgreSQL: {postgres_count} routes\n"
                f"📊 Stats: Reset\n\n"
                f"💡 تست بعدی cold cache خواهد بود"
            )
            
            logging.info(f"🧹 Cleared all caches: Redis={redis_count}, PG={postgres_count}")
            
        except Exception as e:
            logging.error(f"Clear all error: {e}")
            await event.respond(f"❌ خطا: {e}")
    
    logging.info("✅ Cache admin handlers registered")
