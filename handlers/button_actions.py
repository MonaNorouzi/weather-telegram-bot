# handlers/button_actions.py
"""Button click action handlers"""

from telethon import TelegramClient
from core.database_manager import db_manager
from core.button_factory import ButtonFactory


async def handle_add_city(event, client: TelegramClient, user_id: int):
    """Handle add city button click"""
    from handlers.conversation_handler import add_city_wizard
    
    subs = await db_manager.get_user_subscriptions(user_id)
    ps = client.permission_service
    
    if not ps.can_add_subscription(user_id, len(subs)):
        limit = ps.get_subscription_limit(user_id)
        await event.answer(
            f"⚠️ Limit reached ({limit} cities). Upgrade to Premium!",
            alert=True
        )
        return
    
    await event.delete()
    await add_city_wizard(event, client)


async def handle_delete_city(event, client: TelegramClient, user_id: int, sub_id: int):
    """Handle delete city button click"""
    await db_manager.delete_subscription(sub_id)
    if hasattr(client, 'weather_scheduler'):
        await client.weather_scheduler.remove_job(sub_id)
    
    await event.answer("✅ Deleted!", alert=False)
    await show_settings(event, user_id, client)


async def handle_upgrade_premium(event, user_id: int):
    """Handle upgrade button click"""
    await event.answer(
        "💎 Premium Features:\n"
        "✅ Unlimited cities\n"
        "✅ Priority support\n\n"
        "Contact admin to upgrade!",
        alert=True
    )


async def handle_premium_support(event, client: TelegramClient, user_id: int):
    """Handle premium support button click"""
    if client.permission_service.can_access_feature(user_id, "premium_support"):
        await event.answer(
            "🌟 Premium Support\nContact: @admin\nPriority response!",
            alert=True
        )
    else:
        await event.answer("❌ Premium feature only!", alert=True)


async def show_settings(event, user_id: int, client: TelegramClient):
    """Display settings menu with dynamic buttons"""
    subs = await db_manager.get_user_subscriptions(user_id)
    factory = ButtonFactory(client.permission_service)
    buttons = factory.create_settings_buttons(user_id, subs)
    limit_info = factory.get_limit_info_text(user_id, len(subs))
    
    await event.edit(
        f"⚙️ **Settings Panel**\n{limit_info}\n\nManage weather reports:",
        buttons=buttons
    )


async def send_settings_to_user(client: TelegramClient, user_id: int):
    """Send settings menu to a user (used when premium status changes)"""
    subs = await db_manager.get_user_subscriptions(user_id)
    factory = ButtonFactory(client.permission_service)
    buttons = factory.create_settings_buttons(user_id, subs)
    limit_info = factory.get_limit_info_text(user_id, len(subs))
    
    await client.send_message(
        user_id,
        f"⚙️ **Settings Panel**\n{limit_info}\n\nManage weather reports:",
        buttons=buttons
    )
