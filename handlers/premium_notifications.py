# handlers/premium_notifications.py
"""Premium user notification messages and helpers"""

from telethon import TelegramClient
import logging


# Message templates
PREMIUM_ADDED_MSG = (
    "🌟 **Congratulations!**\n\n"
    "You've been upgraded to **Premium** 🎉\n\n"
    "**Premium Benefits:**\n"
    "✅ Unlimited city subscriptions\n"
    "✅ Priority support\n"
    "✅ No limitations\n\n"
    "Check your updated settings menu below! 👇"
)

PREMIUM_REMOVED_MSG = (
    "ℹ️ **Premium Status Update**\n\n"
    "Your premium subscription has ended.\n\n"
    "**Free Tier Limits:**\n"
    "• Maximum 3 city subscriptions\n"
    "• Standard support\n\n"
    "Contact admin to renew premium access.\n"
    "Your existing cities remain active.\n\n"
    "Check your updated settings menu below! 👇"
)


async def notify_premium_added(client: TelegramClient, user_id: int) -> str:
    """Send premium upgrade notification to user"""
    try:
        from handlers.button_actions import send_settings_to_user
        await client.send_message(user_id, PREMIUM_ADDED_MSG)
        await send_settings_to_user(client, user_id)
        return "✅ User notified + settings updated"
    except Exception as e:
        logging.warning(f"Could not notify user {user_id}: {e}")
        return "⚠️ Could not notify user"


async def notify_premium_removed(client: TelegramClient, user_id: int) -> str:
    """Send premium removal notification to user"""
    try:
        from handlers.button_actions import send_settings_to_user
        await client.send_message(user_id, PREMIUM_REMOVED_MSG)
        await send_settings_to_user(client, user_id)
        return "✅ User notified + settings updated"
    except Exception as e:
        logging.warning(f"Could not notify user {user_id}: {e}")
        return "⚠️ Could not notify user"


async def get_user_info(client: TelegramClient, user_id: int) -> tuple:
    """Get user name and username"""
    try:
        user = await client.get_entity(user_id)
        username = f"@{user.username}" if user.username else "No username"
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
        return name, username
    except:
        return None, None
