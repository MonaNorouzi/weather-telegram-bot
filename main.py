# main.py

import sys
import logging
import asyncio
from telethon import TelegramClient
import config
from handlers.message_handler import register_handlers

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

def main():
    # 1. Create Loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 2. Create Client
    client = TelegramClient(
        'bot_session', 
        config.API_ID, 
        config.API_HASH, 
        loop=loop
    )

    async def runner():
        # --- Connecting Handlers ---
        print("🔌 Connecting handlers...")
        register_handlers(client)
        
        print("🚀 Starting client...")
        await client.start(bot_token=config.BOT_TOKEN)
        
        me = await client.get_me()
        print(f"\n✅✅✅ BOT IS READY: @{me.username} ✅✅✅\n")
        
        await client.run_until_disconnected()

    try:
        loop.run_until_complete(runner())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
    finally:
        loop.close()

if __name__ == '__main__':
    main()