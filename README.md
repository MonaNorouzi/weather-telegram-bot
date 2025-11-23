# 🌦️ Smart Weather Bot (Telegram)

A modular, high-performance Telegram bot built with **Python** and **Telethon**.
This bot provides real-time weather information by intelligently parsing various location formats, including complex Google Maps links.

## ✨ Key Features

- **🧠 Smart Location Parsing:**
  - Detects **Google Maps Short URLs** (e.g., `goo.gl`, `googleusercontent`).
  - Extracts coordinates from standard links (`@lat,lon`).
  - Extracts **City Names** from links (e.g., `/place/Tehran`).
  - Supports Telegram's native **Location** attachment.
  - Parses raw text coordinates (e.g., `35.7, 51.4`).
- **⚡ Asynchronous Core:** Built on `Telethon` and `aiohttp` for non-blocking, fast responses.
- **🛡️ Robust & Secure:** Handles timeouts, network errors, and keeps secrets in `.env`.
- **🌍 Hyper-Local & City Fallback:** Uses Reverse Geocoding to display accurate city names instead of obscure neighborhood names.
- **🧱 Modular Architecture:** Clean separation of concerns (`Core` logic vs `Handlers`).

## 📂 Project Structure

```text
WeatherBot/
├── core/
│   ├── location_parser.py   # The "Brain": Regex & Logic to extract location
│   └── weather_api.py       # The "Worker": Fetches data from OpenWeatherMap
├── handlers/
│   └── message_handler.py   # Telegram event listeners
├── main.py                  # Entry point & Event Loop management
├── config.py                # Configuration loader
├── .env.example             # Template for environment variables
└── requirements.txt         # Dependencies
```

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/REPO_NAME.git
   cd REPO_NAME
   ```

2. **Set up Virtual Environment:**
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration:**
   Rename `.env.example` to `.env` and fill in your credentials:
   ```ini
   API_ID=YOUR_APP_ID
   API_HASH=YOUR_APP_HASH
   BOT_TOKEN=YOUR_BOT_TOKEN
   OPENWEATHER_API_KEY=YOUR_OWM_KEY
   ```

## ▶️ Usage

Run the bot using:
```bash
python main.py
```
Then send `/start` to your bot in Telegram!

## 🛠 Technologies

- [Telethon](https://docs.telethon.dev/) - Telegram MTProto API Client
- [OpenWeatherMap API](https://openweathermap.org/) - Weather Data Provider
- [aiohttp](https://docs.aiohttp.org/) - Asynchronous HTTP Client

---
Made with ❤️ by Mona
