# handlers/admin_handler.py

from telethon import events, TelegramClient
import config
import logging

async def handle_add_premium(event, client: TelegramClient):
    """Add a user to premium list without restart"""
    if event.sender_id != config.ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        # Import here to avoid circular import
        from handlers.button_handler import send_settings_to_user
        
        # Parse user ID from command: /addpremium 123456789
        parts = event.message.text.split()
        if len(parts) != 2:
            await event.reply("⚠️ Usage: `/addpremium USER_ID`\nExample: `/addpremium 123456789`")
            return
        
        user_id = int(parts[1])
        
        # Add to runtime set
        if hasattr(client, 'permission_service'):
            if user_id in client.permission_service.premium_user_ids:
                await event.reply(f"ℹ️ User `{user_id}` is already premium!")
                return
            
            client.permission_service.premium_user_ids.add(user_id)
            config.PREMIUM_USER_IDS.add(user_id)  # Update config too
            
            # Get user info and send notification
            try:
                user = await client.get_entity(user_id)
                username = f"@{user.username}" if user.username else "No username"
                name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                
                # Send premium welcome notification to the user
                try:
                    await client.send_message(
                        user_id,
                        f"🌟 **Congratulations!**\n\n"
                        f"You've been upgraded to **Premium** 🎉\n\n"
                        f"**Premium Benefits:**\n"
                        f"✅ Unlimited city subscriptions\n"
                        f"✅ Priority support\n"
                        f"✅ No limitations\n\n"
                        f"Check your updated settings menu below! 👇"
                    )
                    
                    # Send updated settings menu immediately
                    await send_settings_to_user(client, user_id)
                    
                    notification_sent = "✅ User notified + settings updated"
                except Exception as notify_err:
                    logging.warning(f"Could not notify user {user_id}: {notify_err}")
                    notification_sent = "⚠️ Could not notify user"
                
                # Confirm to admin
                await event.reply(
                    f"✅ **Premium Added**\n"
                    f"👤 User: {name}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"📱 Username: {username}\n"
                    f"🌟 Total Premium: {len(client.permission_service.premium_user_ids)}\n"
                    f"📬 {notification_sent}"
                )
            except Exception as e:
                # User entity not found, add anyway
                try:
                    await client.send_message(
                        user_id,
                        f"🌟 **Congratulations!**\n\n"
                        f"You've been upgraded to **Premium** 🎉\n\n"
                        f"**Premium Benefits:**\n"
                        f"✅ Unlimited city subscriptions\n"
                        f"✅ Priority support\n"
                        f"✅ No limitations\n\n"
                        f"Open /start or ⚙️ Settings to see your new features!"
                    )
                    notification_sent = "✅ User notified"
                except:
                    notification_sent = "⚠️ Could not notify user (not started bot yet)"
                
                await event.reply(
                    f"✅ **Premium Added**\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"🌟 Total Premium: {len(client.permission_service.premium_user_ids)}\n"
                    f"📬 {notification_sent}\n\n"
                    f"⚠️ Note: Changes persist until restart. Add to `.env` for persistence."
                )
            
            logging.info(f"🌟 Admin added premium user: {user_id}")
        else:
            await event.reply("❌ Permission service not initialized!")
    
    except ValueError:
        await event.reply("❌ Invalid user ID. Must be a number!")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        logging.error(f"Error adding premium user: {e}")

async def handle_remove_premium(event, client: TelegramClient):
    """Remove a user from premium list without restart"""
    if event.sender_id != config.ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        # Import here to avoid circular import
        from handlers.button_handler import send_settings_to_user
        
        parts = event.message.text.split()
        if len(parts) != 2:
            await event.reply("⚠️ Usage: `/removepremium USER_ID`\nExample: `/removepremium 123456789`")
            return
        
        user_id = int(parts[1])
        
        if hasattr(client, 'permission_service'):
            if user_id not in client.permission_service.premium_user_ids:
                await event.reply(f"ℹ️ User `{user_id}` is not premium!")
                return
            
            client.permission_service.premium_user_ids.discard(user_id)
            config.PREMIUM_USER_IDS.discard(user_id)
            
            # Notify the user about downgrade
            try:
                await client.send_message(
                    user_id,
                    f"ℹ️ **Premium Status Update**\n\n"
                    f"Your premium subscription has ended.\n\n"
                    f"**Free Tier Limits:**\n"
                    f"• Maximum 3 city subscriptions\n"
                    f"• Standard support\n\n"
                    f"Contact admin to renew premium access.\n"
                    f"Your existing cities remain active.\n\n"
                    f"Check your updated settings menu below! 👇"
                )
                
                # Send updated settings menu immediately
                await send_settings_to_user(client, user_id)
                
                notification_sent = "✅ User notified + settings updated"
            except Exception as notify_err:
                logging.warning(f"Could not notify user {user_id}: {notify_err}")
                notification_sent = "⚠️ Could not notify user"
            
            await event.reply(
                f"✅ **Premium Removed**\n"
                f"🆔 ID: `{user_id}`\n"
                f"🌟 Remaining Premium: {len(client.permission_service.premium_user_ids)}\n"
                f"📬 {notification_sent}\n\n"
                f"⚠️ Note: Changes persist until restart. Remove from `.env` for persistence."
            )
            
            logging.info(f"🌟 Admin removed premium user: {user_id}")
        else:
            await event.reply("❌ Permission service not initialized!")
    
    except ValueError:
        await event.reply("❌ Invalid user ID. Must be a number!")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)}")
        logging.error(f"Error removing premium user: {e}")

async def handle_list_premium(event, client: TelegramClient):
    """List all premium users"""
    if event.sender_id != config.ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    if not hasattr(client, 'permission_service'):
        await event.reply("❌ Permission service not initialized!")
        return
    
    premium_ids = client.permission_service.premium_user_ids
    
    if not premium_ids:
        await event.reply("📭 No premium users configured.")
        return
    
    # Build list with user details
    user_list = []
    for uid in premium_ids:
        try:
            user = await client.get_entity(uid)
            username = f"@{user.username}" if user.username else "No username"
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
            user_list.append(f"• {name} ({username}) - `{uid}`")
        except:
            user_list.append(f"• Unknown User - `{uid}`")
    
    message = f"🌟 **Premium Users ({len(premium_ids)})**\n\n" + "\n".join(user_list)
    await event.reply(message)

async def handle_reload_premium(event, client: TelegramClient):
    """Reload premium users from .env file"""
    if event.sender_id != config.ADMIN_ID:
        await event.reply("❌ Admin only command!")
        return
    
    try:
        import os
        from dotenv import load_dotenv
        
        # Reload .env file
        load_dotenv(override=True)
        
        # Parse premium users
        premium_ids_str = os.getenv("PREMIUM_USER_IDS", "")
        new_premium_ids = set()
        if premium_ids_str:
            new_premium_ids = {int(uid.strip()) for uid in premium_ids_str.split(",") if uid.strip()}
        
        # Update service and config
        if hasattr(client, 'permission_service'):
            old_count = len(client.permission_service.premium_user_ids)
            client.permission_service.premium_user_ids = new_premium_ids
            config.PREMIUM_USER_IDS = new_premium_ids
            new_count = len(new_premium_ids)
            
            await event.reply(
                f"✅ **Premium Users Reloaded**\n"
                f"📊 Before: {old_count} users\n"
                f"📊 After: {new_count} users\n"
                f"🔄 Changes applied from `.env`"
            )
            
            logging.info(f"🔄 Admin reloaded premium users: {old_count} -> {new_count}")
        else:
            await event.reply("❌ Permission service not initialized!")
    
    except Exception as e:
        await event.reply(f"❌ Error reloading: {str(e)}")
        logging.error(f"Error reloading premium users: {e}")

def register_admin_handlers(client: TelegramClient):
    """Register admin command handlers"""
    
    @client.on(events.NewMessage(pattern=r'^/addpremium'))
    async def add_premium_handler(event):
        await handle_add_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/removepremium'))
    async def remove_premium_handler(event):
        await handle_remove_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/listpremium'))
    async def list_premium_handler(event):
        await handle_list_premium(event, client)
    
    @client.on(events.NewMessage(pattern=r'^/reloadpremium'))
    async def reload_premium_handler(event):
        await handle_reload_premium(event, client)
    
    logging.info("✅ Admin handlers registered")
