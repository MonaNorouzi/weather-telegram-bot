# handlers/admin_reload.py
"""Admin reload and registration commands"""

from telethon import events, TelegramClient
import config
import logging
import os
from dotenv import load_dotenv


async def handle_reload_premium(event, client: TelegramClient):
    """Reload premium users from .env file"""
    if event.sender_id != config.ADMIN_ID:
        return await event.reply("❌ Admin only command!")
    
    try:
        load_dotenv(override=True)
        premium_str = os.getenv("PREMIUM_USER_IDS", "")
        new_ids = set()
        
        if premium_str:
            new_ids = {int(uid.strip()) for uid in premium_str.split(",") if uid.strip()}
        
        ps = client.permission_service
        old_count = len(ps.premium_user_ids)
        ps.premium_user_ids = new_ids
        config.PREMIUM_USER_IDS = new_ids
        
        await event.reply(
            f"✅ **Reloaded**\n📊 Before: {old_count}\n"
            f"📊 After: {len(new_ids)}\n🔄 Applied from `.env`"
        )
        logging.info(f"🔄 Reloaded premium: {old_count} -> {len(new_ids)}")
        
    except Exception as e:
        await event.reply(f"❌ Error: {e}")


def register_admin_handlers(client: TelegramClient):
    """Register all admin command handlers"""
    from handlers.admin_handler import (
        handle_add_premium, handle_remove_premium, handle_list_premium
    )
    
    @client.on(events.NewMessage(pattern=r'^/addpremium'))
    async def _(event):
        await handle_add_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/removepremium'))
    async def _(event):
        await handle_remove_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/listpremium'))
    async def _(event):
        await handle_list_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/reloadpremium'))
    async def _(event):
        await handle_reload_premium(event, client)
    
    logging.info("✅ Admin handlers registered")
