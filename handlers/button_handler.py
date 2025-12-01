# handlers/button_handler.py

from telethon import events, Button, TelegramClient
from core.database_manager import db_manager
from handlers.conversation_handler import add_city_wizard 

async def button_click_handler(event, client: TelegramClient):
    user_id = event.sender_id
    data = event.data.decode('utf-8') 

    if data == 'open_settings':
        await show_settings_menu(event, user_id)

    elif data == 'add_city_start':
        await event.delete() 
        await add_city_wizard(event, client)
    
    elif data.startswith('del_'):
        sub_id = int(data.split('_')[1])
        await db_manager.delete_subscription(sub_id)
        if hasattr(client, 'weather_scheduler'):
            await client.weather_scheduler.remove_job(sub_id)
        
        await event.answer("Deleted!", alert=False)
        await show_settings_menu(event, user_id)

    elif data == 'cancel_action':
        await event.delete()
        
    elif data == 'cancel_conv':
        await event.delete()
        await client.send_message(user_id, "Cancelled.")

async def show_settings_menu(event, user_id):
    subs = await db_manager.get_user_subscriptions(user_id)
    
    buttons = []
    if subs:
        for sub in subs:
            btn_text = f"🗑 {sub['city_name']} ({sub['schedule_time']})"
            btn_data = f"del_{sub['id']}".encode()
            buttons.append([Button.inline(btn_text, btn_data)])
    else:
        buttons.append([Button.inline("(Your list is empty)", b"ignore")])

    buttons.append([Button.inline("➕ Add New City", b"add_city_start")])
    buttons.append([Button.inline("❌ Close Menu", b"cancel_action")])

    await event.edit(
        "⚙️ **Settings Panel**\nHere are your scheduled weather reports:",
        buttons=buttons
    )

def register_button_handlers(client: TelegramClient):
    @client.on(events.CallbackQuery)
    async def handler(event):
        await button_click_handler(event, client)