# 🌦 Telegram Weather Scheduler Bot

A professional, fully asynchronous Telegram bot that sends automated daily weather reports to users based on their local time and location. Features a **premium tier system** with dynamic UI and admin controls.

---

## ✨ Features

### 🌍 Core Features (All Users)
- **Smart Location Detection** — Send city name, coordinates, or Google Maps link
- **Auto Timezone** — Automatically detects timezone from location
- **Daily Weather Reports** — Scheduled messages at your preferred local time
- **Multiple Cities** — Track weather for multiple locations
- **Beautiful Reports** — Detailed weather info with emoji indicators

### 🌟 Premium Features
- **Unlimited Cities** — No subscription limits (free users: max 3)
- **Premium Support** — Priority support button in settings
- **VIP Badge** — Shows premium status in settings panel

### 👑 Admin Features
- `/addpremium <user_id>` — Grant premium access instantly
- `/removepremium <user_id>` — Revoke premium access
- `/listpremium` — View all premium users
- `/reloadpremium` — Reload from .env without restart
- **Auto-Notification** — Users are notified when status changes

---

## 🚀 Technical Highlights

| Feature | Description |
|---------|-------------|
| **AsyncIO** | Non-blocking event loop for high performance |
| **Smart Timezone** | Coordinates → IANA timezone (e.g., `Asia/Tehran`) |
| **Network Resilience** | Auto-reconnect & keep-alive logic |
| **Proxy Support** | Full SOCKS5/HTTP proxy integration |
| **Modular Design** | All files under 100 lines, clean architecture |
| **Strategy Pattern** | Dynamic permissions based on user tier |
| **Factory Pattern** | Dynamic UI generation per user |

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- [Telegram API Credentials](https://my.telegram.org) (`API_ID`, `API_HASH`)
- [Bot Token](https://t.me/BotFather) from @BotFather
- [OpenWeatherMap API Key](https://openweathermap.org/api)

### Quick Start

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/weather-scheduler-bot.git
cd weather-scheduler-bot

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the bot
python main.py
```

---

## ⚙️ Configuration

Create a `.env` file with the following:

```ini
# Telegram Credentials
API_ID=1234567
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here

# Weather API
OPENWEATHER_API_KEY=your_weather_api_key_here

# Admin (Your Telegram User ID)
ADMIN_ID=123456789

# Premium Users (comma-separated IDs)
PREMIUM_USER_IDS=111111111,222222222

# Proxy (Optional)
PROXY_URL=socks5://127.0.0.1:10808
```

> 💡 **Tip**: Get your User ID from [@userinfobot](https://t.me/userinfobot)

---

## 🎮 User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot and see main menu |
| `/weather` | Get current weather for a location |
| `/settings` | Manage your scheduled cities |
| `/help` | Show help message |

---

## 👑 Admin Commands

| Command | Description |
|---------|-------------|
| `/addpremium <id>` | Add user to premium (instant) |
| `/removepremium <id>` | Remove premium access |
| `/listpremium` | List all premium users |
| `/reloadpremium` | Reload from .env file |

**Example:**
```
/addpremium 123456789
→ ✅ Premium Added
→ 📬 User notified + settings updated
```

---

## 🏗 Project Structure

```
weather-scheduler-bot/
├── main.py                 # Entry point
├── config.py               # Environment configuration
├── handlers/
│   ├── message_handler.py      # Text message handling
│   ├── button_handler.py       # Button click routing
│   ├── button_actions.py       # Button action logic
│   ├── conversation_handler.py # Multi-step wizards
│   ├── admin_handler.py        # Admin commands
│   ├── admin_reload.py         # Reload & registration
│   └── premium_notifications.py # Premium messages
└── core/
    ├── database_manager.py     # SQLite operations
    ├── weather_api.py          # OpenWeatherMap API
    ├── scheduler_service.py    # Job scheduling
    ├── scheduler_jobs.py       # Job execution
    ├── user_permission_service.py # Permission logic
    ├── button_factory.py       # Dynamic UI factory
    ├── location_parser.py      # Location parsing
    ├── timezone_helper.py      # Timezone detection
    └── validators.py           # Input validation
```

---

## 🔐 Premium System Architecture

```
┌─────────────────────────────────────────────────┐
│                   User Action                    │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│           UserPermissionService                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │  FREE   │  │ PREMIUM │  │  ADMIN  │         │
│  │ 3 cities│  │Unlimited│  │Unlimited│         │
│  └─────────┘  └─────────┘  └─────────┘         │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│              ButtonFactory                       │
│  Generates dynamic UI based on user tier         │
└─────────────────────────────────────────────────┘
```

---

## 📊 Free vs Premium Comparison

| Feature | Free | Premium |
|---------|------|---------|
| City Subscriptions | 3 max | Unlimited |
| Premium Support | ❌ | ✅ |
| Upgrade Prompts | Shows | Hidden |
| Status Badge | Standard | 🌟 Premium |

---

## 🛠 Development

### Code Quality Rules
- ✅ All files under 100 lines
- ✅ Single Responsibility Principle
- ✅ Type hints throughout
- ✅ Comprehensive logging

### Testing
```bash
# Syntax check all files
python -m py_compile main.py handlers/*.py core/*.py
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


