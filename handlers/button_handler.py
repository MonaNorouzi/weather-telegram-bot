# handlers/button_handler.py

from telethon import events, Button, TelegramClient
from core.database_manager import db_manager
from handlers.conversation_handler import add_city_wizard
from core.user_permission_service import UserPermissionService
from core.button_factory import ButtonFactory
import logging

# Module-level instances (will be initialized when handlers are registered)
permission_service: UserPermissionService = None
button_factory: ButtonFactory = None 

async def button_click_handler(event, client: TelegramClient):
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    # IMPORTANT: Always use client's current permission_service for real-time checks
    # This ensures premium status changes take effect immediately without restart
    current_perm_service = client.permission_service

    if data == 'open_settings':
        await show_settings_menu(event, user_id, client)

    elif data == 'add_city_start':
        # Check subscription limit before starting wizard
        subs = await db_manager.get_user_subscriptions(user_id)
        current_count = len(subs)
        
        if not current_perm_service.can_add_subscription(user_id, current_count):
            limit = current_perm_service.get_subscription_limit(user_id)
            await event.answer(
                f"⚠️ You've reached your limit ({limit} cities). Upgrade to Premium for unlimited!",
                alert=True
            )
            return
        
        await event.delete() 
        await add_city_wizard(event, client)
    
    elif data.startswith('del_'):
        sub_id = int(data.split('_')[1])
        await db_manager.delete_subscription(sub_id)
        if hasattr(client, 'weather_scheduler'):
            await client.weather_scheduler.remove_job(sub_id)
        
        await event.answer("✅ Deleted!", alert=False)
        await show_settings_menu(event, user_id, client)

    elif data == 'upgrade_premium':
        tier = current_perm_service.get_user_tier(user_id)
        await event.answer(
            f"💎 Premium Features:\n"
            f"✅ Unlimited city subscriptions\n"
            f"✅ Priority updates\n"
            f"✅ Premium support\n\n"
            f"Contact admin to upgrade!",
            alert=True
        )
    
    elif data == 'premium_support':
        if current_perm_service.can_access_feature(user_id, "premium_support"):
            admin_username = "@admin"  # Replace with actual admin contact
            await event.answer(
                f"🌟 Premium Support\n"
                f"Contact: {admin_username}\n"
                f"Priority response within 24h!",
                alert=True
            )
        else:
            await event.answer("❌ Premium feature only!", alert=True)
    
    elif data == 'ignore':
        # Placeholder button, do nothing
        pass

    elif data == 'cancel_action':
        await event.delete()
        
    elif data == 'cancel_conv':
        await event.delete()
        await client.send_message(user_id, "❌ Cancelled.")

async def send_settings_to_user(client: TelegramClient, user_id: int):
    """Send settings menu to a user (used when premium status changes)"""
    subs = await db_manager.get_user_subscriptions(user_id)
    
    # IMPORTANT: Create fresh ButtonFactory from client's current permission_service
    # This ensures we use the LATEST premium user list after /addpremium or /removepremium
    current_permission_service = client.permission_service
    fresh_button_factory = ButtonFactory(current_permission_service)
    
    # Use fresh button factory to generate dynamic buttons
    buttons = fresh_button_factory.create_settings_buttons(user_id, subs)
    
    # Add subscription limit info for user
    limit_info = fresh_button_factory.get_limit_info_text(user_id, len(subs))
    
    await client.send_message(
        user_id,
        f"⚙️ **Settings Panel**\n"
        f"{limit_info}\n\n"
        f"Manage your scheduled weather reports:",
        buttons=buttons
    )

async def show_settings_menu(event, user_id, client: TelegramClient):
    """Display settings menu with dynamic buttons based on user permissions"""
    subs = await db_manager.get_user_subscriptions(user_id)
    
    # IMPORTANT: Create fresh ButtonFactory from client's current permission_service
    # This ensures we use the LATEST premium user list after /addpremium or /removepremium
    current_permission_service = client.permission_service
    fresh_button_factory = ButtonFactory(current_permission_service)
    
    # Use fresh button factory to generate dynamic buttons
    buttons = fresh_button_factory.create_settings_buttons(user_id, subs)
    
    # Add subscription limit info for user
    limit_info = fresh_button_factory.get_limit_info_text(user_id, len(subs))
    
    await event.edit(
        f"⚙️ **Settings Panel**\n"
        f"{limit_info}\n\n"
        f"Manage your scheduled weather reports:",
        buttons=buttons
    )

def register_button_handlers(client: TelegramClient):
    """Register button event handlers and initialize services"""
    global permission_service, button_factory
    
    # Initialize services from client (attached in main.py)
    if hasattr(client, 'permission_service'):
        permission_service = client.permission_service
        button_factory = ButtonFactory(permission_service)
        logging.info("✅ Button handlers initialized with permission service")
    else:
        logging.error("❌ Permission service not found on client!")
    
    @client.on(events.CallbackQuery)
    async def handler(event):
        await button_click_handler(event, client)