# 🌦 Telegram Weather Scheduler Bot

A professional, fully asynchronous Telegram bot that sends automated daily weather reports to users based on their local time and location.

## ❓ What does this bot do?

This bot solves the problem of checking weather apps manually.
1.  **Collects Location:** The user sends a city name or location.
2.  **Detects Timezone:** It automatically calculates the correct timezone for that city (no math required for the user).
3.  **Schedules Reminder:** The user sets a preferred time (e.g., "08:00 AM"), and the bot sends a detailed weather report **at that exact local time**, every single day.

It is designed to be **"set and forget"**—running reliably in the background with auto-reconnection capabilities.

---

## 🚀 Technical Highlights (Engineering)

Built with **Python 3.10+**, **Telethon**, and **APScheduler**, this project emphasizes stability and architecture:

* **⚡ AsyncIO Architecture:** Uses a non-blocking event loop for high performance.
* **🌍 Smart Timezone Conversion:** Converts user coordinates to IANA timezones (e.g., `Asia/Tehran`) to ensure 08:00 AM means 08:00 AM for *the user*, regardless of server time.
* **🛡️ Network Resilience:** Implements "Keep-Alive" and "Auto-Reconnect" logic to handle unstable networks or proxy fluctuations without crashing.
* **🥷 Proxy Support:** Full SOCKS5/HTTP proxy integration for restricted network environments.
* **🔄 Self-Healing Identity:** Automatically resolves user entities (via `Force Fetch`) upon restart, preventing "InputEntityNotFound" errors common in Telethon bots.

## 🛠 Prerequisites

* **Python 3.10+**
* **Telegram API Credentials** (`API_ID`, `API_HASH`) from [my.telegram.org](https://my.telegram.org)
* **Bot Token** from [@BotFather](https://t.me/BotFather)
* **OpenWeatherMap API Key** from [openweathermap.org](https://openweathermap.org)

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/weather-scheduler-bot.git](https://github.com/YOUR_USERNAME/weather-scheduler-bot.git)
    cd weather-scheduler-bot
    ```

2.  **Set up Virtual Environment:**
    ```bash
    # Windows
    python -m venv venv
    venv\Scripts\activate

    # Linux/macOS
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

1.  Create a `.env` file in the root directory:
    ```bash
    cp .env.example .env
    ```

2.  **Configure your credentials in `.env`:**

    ```ini
    # --- Telegram App Credentials ---
    API_ID=1234567
    API_HASH=your_api_hash_here

    # --- Bot Token ---
    BOT_TOKEN=your_bot_token_here

    # --- Weather Provider ---
    OPENWEATHER_API_KEY=your_weather_api_key_here

    # --- Admin Configuration ---
    # REQUIRED: Your numeric User ID (Get it from @userinfobot)
    # The bot sends startup health checks to this ID.
    ADMIN_ID=123456789

    # --- Network / Proxy (Optional) ---
    # Leave empty if not needed.
    # Example: socks5://127.0.0.1:10808
    PROXY_URL=socks5://127.0.0.1:10808
    ```

## ▶️ Usage

1.  **Start the bot:**
    ```bash
    python main.py
    ```

2.  **Bot Workflow:**
    * `/start` -> Introduction.
    * **Add City** -> Send "Tehran" or a Location.
    * **Set Time** -> Enter "07:30".
    * ✅ Done! The bot will message you daily at 07:30 Tehran time.

## 🏗 Project Structure

* `main.py`: Entry point. Initializes the Event Loop, Client, and Scheduler integration.
* `config.py`: Secure environment variable management.
* `core/`:
    * `scheduler_service.py`: Advanced job management with Heartbeat monitoring.
    * `database_manager.py`: Async SQLite operations.
    * `weather_api.py`: External API communication.
    * `timezone_helper.py`: Coordinate-to-Timezone logic.
* `handlers/`: User interaction logic (Messages & Inline Buttons).

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
