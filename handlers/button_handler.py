# handlers/button_handler.py
"""Button handler registration and routing"""

from telethon import events, TelegramClient
from core.button_factory import ButtonFactory
import logging


async def button_click_handler(event, client: TelegramClient):
    """Route button clicks to appropriate handlers"""
    from handlers.button_actions import (
        handle_add_city, handle_delete_city, 
        handle_upgrade_premium, handle_premium_support, show_settings
    )
    
    user_id = event.sender_id
    data = event.data.decode('utf-8')

    if data == 'open_settings':
        await show_settings(event, user_id, client)

    elif data == 'add_city_start':
        await handle_add_city(event, client, user_id)
    
    elif data.startswith('del_'):
        sub_id = int(data.split('_')[1])
        await handle_delete_city(event, client, user_id, sub_id)

    elif data == 'upgrade_premium':
        await handle_upgrade_premium(event, user_id)
    
    elif data == 'premium_support':
        await handle_premium_support(event, client, user_id)

    elif data == 'start_route_finder':
        from handlers.unified_route_handler import start_smart_route_wizard
        await event.delete()  # Close settings menu
        await start_smart_route_wizard(client, user_id)
    
    elif data == 'admin_clear_cache':
        # Clear all caches - Available for all users for testing
        await event.answer("🔄 در حال پاک کردن کش‌ها...", alert=False)
        
        from core.redis_manager import redis_manager
        from core.redis_route_cache import redis_route_cache
        from core.redis_weather_cache import redis_weather_cache
        from core.redis_geospatial_cache import redis_geo_cache
        
        try:
            redis_client = await redis_manager.get_client()
            if not redis_client:
                await event.edit("❌ Redis در دسترس نیست!")
                return
            
            redis_count = 0
            postgres_count = 0
            
            # Clear all Redis cache patterns
            patterns = ["route:*", "weather:*", "places:*", "geospatial:*"]
            for pattern in patterns:
                keys = await redis_client.keys(pattern)
                if keys:
                    deleted = await redis_client.delete(*keys)
                    redis_count += deleted
                    logging.info(f"Cleared {deleted} keys for pattern '{pattern}'")
            
            # Clear PostgreSQL routes table
            from core.graph_database import graph_db
            async with graph_db.acquire() as conn:
                try:
                    result = await conn.execute("DELETE FROM routes")
                    # Extract count from result "DELETE N"
                    if result and len(result.split()) > 1:
                        postgres_count = int(result.split()[-1]) if result.split()[-1].isdigit() else 0
                    logging.info(f"Cleared {postgres_count} routes from PostgreSQL")
                except Exception as pg_error:
                    logging.warning(f"PostgreSQL routes clear failed: {pg_error}")
            
            # Reset all statistics to zero
            redis_route_cache.stats = {
                "redis_hits": 0, 
                "redis_misses": 0, 
                "postgres_fallbacks": 0, 
                "cache_errors": 0
            }
            redis_weather_cache.stats = {
                "cache_hits": 0, 
                "cache_misses": 0, 
                "stale_serves": 0
            }
            redis_geo_cache.stats = {
                "redis_hits": 0, 
                "postgres_fallbacks": 0, 
                "nodes_loaded": 0
            }
            
            # Send success message
            await event.edit(
                f"✅ **همه کش‌ها با موفقیت پاک شدند!**\n\n"
                f"🗑️ Redis: {redis_count} کلید\n"
                f"🗑️ PostgreSQL: {postgres_count} مسیر\n"
                f"📊 آمارها: صفر شد\n\n"
                f"💡 درخواست بعدی مثل اولین بار خواهد بود (cold cache)\n"
                f"💡 این به شما امکان می‌دهد سیستم کشینگ را از اول تست کنید"
            )
            
            logging.info(f"🧹 All caches cleared by user {user_id}: Redis={redis_count}, PostgreSQL={postgres_count}")
            
        except Exception as e:
            logging.error(f"Clear cache button error: {e}")
            import traceback
            traceback.print_exc()
            await event.edit(f"❌ خطا در پاک کردن کش‌ها:\n{str(e)}")
    
    elif data == 'ignore':
        pass

    elif data == 'cancel_action':
        await event.delete()
        
    elif data == 'cancel_conv':
        await event.delete()
        await client.send_message(user_id, "❌ Cancelled.")


# Re-export for backward compatibility
def send_settings_to_user(client, user_id):
    """Wrapper for backward compatibility"""
    from handlers.button_actions import send_settings_to_user as _send
    return _send(client, user_id)


def register_button_handlers(client: TelegramClient):
    """Register button event handlers"""
    if hasattr(client, 'permission_service'):
        logging.info("✅ Button handlers initialized")
    else:
        logging.error("❌ Permission service not found!")
    
    @client.on(events.CallbackQuery)
    async def handler(event):
        await button_click_handler(event, client)