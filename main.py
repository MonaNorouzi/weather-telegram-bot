# main.py

import sys
import logging
import asyncio
from telethon import TelegramClient
import config
from handlers.message_handler import register_handlers
from handlers.button_handler import register_button_handlers
from handlers.admin_reload import register_admin_handlers
from core.database_manager import db_manager
from core.scheduler_service import WeatherScheduler
from core.user_permission_service import UserPermissionService # Keep original import
from core.button_factory import ButtonFactory # New import
from core.graph_database import graph_db # New import
from core.redis_manager import init_redis, close_redis, redis_manager # Redis imports
from core.redis_geospatial_cache import redis_geo_cache # Geospatial cache

# --- Logging setup ---
logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(message)s', level=logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

async def on_startup(client: TelegramClient, loop: asyncio.AbstractEventLoop):
    """
    Executes startup tasks: DB init, Handler registration, Scheduler start, and Admin notification.
    """
    # Step 2: Initialize databases
    logging.info("🗄 Initializing SQLite Database...")
    await db_manager.init_db()
    
    # Initialize Graph Database (PostgreSQL)
    try:
        logging.info("🗄 Initializing Graph Database...")
        await graph_db.initialize(min_size=2, max_size=10)
        stats = await graph_db.get_graph_stats()
        logging.info(f"  Graph: {stats.get('total_places', 0)} places, "
                     f"{stats.get('total_nodes', 0)} nodes, "
                     f"{stats.get('total_edges', 0)} edges")
    except Exception as e:
        logging.warning(f"⚠️ Graph database not available: {e}")
        logging.warning("  Route caching will use file-based fallback")
    
    # Initialize Redis Cache
    try:
        logging.info("🔴 Initializing Redis Cache...")
        redis_connected = await init_redis()
        if redis_connected:
            # Load geospatial index (all graph nodes)
            node_count = await redis_geo_cache.load_all_nodes()
            logging.info(f"  ✅ Redis connected! Loaded {node_count} nodes into geospatial index")
        else:
            logging.warning("  ⚠️ Redis not available - caching will fall back to PostgreSQL")
    except Exception as e:
        logging.warning(f"⚠️ Redis initialization failed: {e}")
        logging.warning("  Caching will fall back to PostgreSQL")

    logging.info("🔐 Initializing Permission Service...")
    permission_service = UserPermissionService(config.PREMIUM_USER_IDS, config.ADMIN_ID)
    client.permission_service = permission_service
    logging.info(f"🌟 Premium users: {len(config.PREMIUM_USER_IDS)}")

    logging.info("🔌 Connecting handlers...")
    # IMPORTANT: Route handlers FIRST (so they can intercept during wizard)
    from handlers.unified_route_handler import register_smart_route_handlers
    from handlers.cache_admin_handler import register_cache_admin_handlers
    register_smart_route_handlers(client)  # Smart unified handler
    register_handlers(client)
    register_button_handlers(client)
    register_admin_handlers(client)
    register_cache_admin_handlers(client)  # Cache admin commands

    logging.info("⏰ Starting Scheduler Service...")
    scheduler = WeatherScheduler(client, loop)
    await scheduler.start()
    
    client.weather_scheduler = scheduler
    
    try:
        me = await client.get_me()
        logging.info(f"\n✅✅✅ BOT STARTED: @{me.username} ✅✅✅\n")
        
        await client.send_message(config.ADMIN_ID, 
            f"🚀 **System Online**\n"
            f"⏰ Server Time: {config._get_env_variable('TZ', False) or 'UTC'}\n"
            f"🛡 Proxy: {'✅ On' if config.PROXY_URL else '❌ Off'}"
        )
    except Exception as e:
        logging.warning(f"⚠️ Could not send startup message to Admin: {e}")

def main():
    # Create explicit event loop for Python 3.10+ compatibility
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    proxy_params = config.get_telethon_proxy_params()
    if proxy_params:
        logging.info(f" Proxy Configured: {proxy_params['addr']}:{proxy_params['port']}")
    
    client = TelegramClient(
        'bot_session', 
        config.API_ID, 
        config.API_HASH,
        loop=loop,
        proxy=proxy_params,
        connection_retries=None, 
        auto_reconnect=True,
        retry_delay=5
    )

    try:
        print("⏳ Connecting to Telegram servers...")
        client.start(bot_token=config.BOT_TOKEN)
        
        loop.run_until_complete(on_startup(client, loop))
        
        logging.info("--- 📡 Listening for updates (Ctrl+C to stop) ---")
        client.run_until_disconnected()

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
    except Exception as e:
        logging.error(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logging.info("--- Shutting down... ---")
        if hasattr(client, 'weather_scheduler'):
             try:
                 client.weather_scheduler.scheduler.shutdown()
             except:
                 pass
        
        # Close Redis connection
        try:
            logging.info("Closing Redis connection...")
            loop.run_until_complete(close_redis())
        except Exception as e:
            logging.warning(f"⚠️ Error closing Redis: {e}")
        
        # Close graph database pool
        try:
            loop.run_until_complete(graph_db.close()) # Ensure graph_db.close() is awaited
        except Exception as e:
            logging.warning(f"⚠️ Error closing graph database: {e}")
        
        if client.is_connected():
            # client.disconnect() is a coroutine, need to await it
            loop.run_until_complete(client.disconnect())
            
        loop.close()
        print("Goodbye.")

if __name__ == '__main__':
    main()
