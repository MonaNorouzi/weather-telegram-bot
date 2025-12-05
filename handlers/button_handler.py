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