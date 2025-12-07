# main.py

import sys
import logging
import asyncio
from telethon import TelegramClient
import config
from handlers.message_handler import register_handlers
from handlers.button_handler import register_button_handlers
from handlers.admin_reload import register_admin_handlers
from handlers.route_handler import register_route_handlers
from core.database_manager import db_manager
from core.scheduler_service import WeatherScheduler
from core.user_permission_service import UserPermissionService

# --- Logging setup ---
logging.basicConfig(format='[%(levelname)s] %(asctime)s - %(message)s', level=logging.INFO)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

async def on_startup(client: TelegramClient, loop: asyncio.AbstractEventLoop):
    """
    Executes startup tasks: DB init, Handler registration, Scheduler start, and Admin notification.
    """
    logging.info("🗄 Initializing Database...")
    await db_manager.init_db()

    logging.info("🔐 Initializing Permission Service...")
    permission_service = UserPermissionService(config.PREMIUM_USER_IDS, config.ADMIN_ID)
    client.permission_service = permission_service
    logging.info(f"🌟 Premium users: {len(config.PREMIUM_USER_IDS)}")

    logging.info("🔌 Connecting handlers...")
    # IMPORTANT: Route handlers FIRST (so they can intercept during wizard)
    register_route_handlers(client)
    register_handlers(client)
    register_button_handlers(client)
    register_admin_handlers(client)

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
        
        if client.is_connected():
            # client.disconnect() is a coroutine, need to await it
            loop.run_until_complete(client.disconnect())
            
        loop.close()
        print("Goodbye.")

if __name__ == '__main__':
    main()