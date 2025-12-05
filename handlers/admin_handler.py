# handlers/admin_handler.py
"""Admin commands for premium user management"""

from telethon import events, TelegramClient
import config
import logging
from handlers.premium_notifications import (
    notify_premium_added, notify_premium_removed, get_user_info
)


async def handle_add_premium(event, client: TelegramClient):
    """Add a user to premium list"""
    if event.sender_id != config.ADMIN_ID:
        return await event.reply("❌ Admin only command!")
    
    try:
        parts = event.message.text.split()
        if len(parts) != 2:
            return await event.reply("⚠️ Usage: `/addpremium USER_ID`")
        
        user_id = int(parts[1])
        ps = client.permission_service
        
        if user_id in ps.premium_user_ids:
            return await event.reply(f"ℹ️ User `{user_id}` is already premium!")
        
        ps.premium_user_ids.add(user_id)
        config.PREMIUM_USER_IDS.add(user_id)
        
        name, username = await get_user_info(client, user_id)
        notification = await notify_premium_added(client, user_id)
        
        if name:
            await event.reply(
                f"✅ **Premium Added**\n👤 {name}\n🆔 `{user_id}`\n"
                f"📱 {username}\n🌟 Total: {len(ps.premium_user_ids)}\n📬 {notification}"
            )
        else:
            await event.reply(
                f"✅ **Premium Added**\n🆔 `{user_id}`\n"
                f"🌟 Total: {len(ps.premium_user_ids)}\n📬 {notification}"
            )
        logging.info(f"🌟 Admin added premium: {user_id}")
        
    except ValueError:
        await event.reply("❌ Invalid user ID!")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")


async def handle_remove_premium(event, client: TelegramClient):
    """Remove a user from premium list"""
    if event.sender_id != config.ADMIN_ID:
        return await event.reply("❌ Admin only command!")
    
    try:
        parts = event.message.text.split()
        if len(parts) != 2:
            return await event.reply("⚠️ Usage: `/removepremium USER_ID`")
        
        user_id = int(parts[1])
        ps = client.permission_service
        
        if user_id not in ps.premium_user_ids:
            return await event.reply(f"ℹ️ User `{user_id}` is not premium!")
        
        ps.premium_user_ids.discard(user_id)
        config.PREMIUM_USER_IDS.discard(user_id)
        
        notification = await notify_premium_removed(client, user_id)
        await event.reply(
            f"✅ **Premium Removed**\n🆔 `{user_id}`\n"
            f"🌟 Remaining: {len(ps.premium_user_ids)}\n📬 {notification}"
        )
        logging.info(f"🌟 Admin removed premium: {user_id}")
        
    except ValueError:
        await event.reply("❌ Invalid user ID!")
    except Exception as e:
        await event.reply(f"❌ Error: {e}")


async def handle_list_premium(event, client: TelegramClient):
    """List all premium users"""
    if event.sender_id != config.ADMIN_ID:
        return await event.reply("❌ Admin only command!")
    
    premium_ids = client.permission_service.premium_user_ids
    if not premium_ids:
        return await event.reply("📭 No premium users configured.")
    
    user_list = []
    for uid in premium_ids:
        name, username = await get_user_info(client, uid)
        if name:
            user_list.append(f"• {name} ({username}) - `{uid}`")
        else:
            user_list.append(f"• Unknown - `{uid}`")
    
    await event.reply(f"🌟 **Premium Users ({len(premium_ids)})**\n\n" + "\n".join(user_list))
