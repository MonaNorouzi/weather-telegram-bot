# handlers/message_handler.py

from telethon import events, TelegramClient
from core.location_parser import parse_input
from core.weather_api import get_weather

def register_handlers(client: TelegramClient):
    """
    Main function to attach event listeners to the Telegram client.
    """
    print("✅ [System] Loading Handlers...")

    # --- Handler: All Incoming Messages ---
    @client.on(events.NewMessage)
    async def root_handler(event):
        # Debug: Print immediately when a message arrives
        # We slice [:20] to avoid flooding terminal with long texts
        print(f"⚡️ [Event] Message received: {str(event.text)[:20]}...")
        
        # 1. Check for the /start command
        if event.text and event.text.lower() == '/start':
            await event.reply(
                "👋 Hello! I am ready.\n"
                "📍 Send me a: Location, Google Maps Link, or City Name."
            )
            return

        # 2. Extract User Input (Text or Geo Object)
        user_input = None
        if event.message.geo:
            user_input = event.message.geo
        elif event.message.text:
            user_input = event.message.text
        
        # If message is empty or media without caption, ignore it
        if not user_input:
            return

        # 3. Send a temporary 'Thinking' message to improve UX
        loading_msg = await event.reply("⏳ Analyzing...")

        try:
            # 4. Parse the Input (using core/location_parser.py)
            print("   > Parsing input...")
            parsed_data = await parse_input(user_input)
            
            # If the parser couldn't find coordinates or a city name
            if parsed_data is None:
                print("   > Parser returned None (Invalid Input).")
                await loading_msg.edit("⛔️ Invalid Input! Please send a valid location or link.")
                return

            # 5. Fetch Weather Data (using core/weather_api.py)
            print(f"   > Fetching weather for: {parsed_data}")
            weather_report = await get_weather(parsed_data)
            
            # 6. Update the message with the final report
            await loading_msg.edit(weather_report)
            print("   > ✅ Result sent successfully.")

        except Exception as e:
            # Error Handling: Log to terminal and notify user
            print(f"❌ ERROR in Handler: {e}")
            await loading_msg.edit(f"⚠️ Internal Error: {e}")