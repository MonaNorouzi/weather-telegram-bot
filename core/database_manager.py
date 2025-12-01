# core/database_manager.py

import aiosqlite
import logging

DB_NAME = "weather_bot.db"

class DatabaseManager:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name

    async def init_db(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    city_name TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    schedule_time TEXT NOT NULL,
                    timezone TEXT DEFAULT 'UTC' 
                )
            """)
            
            # --- MIGRATION: Check if timezone column exists (For existing users) ---
            try:
                await db.execute("SELECT timezone FROM subscriptions LIMIT 1")
            except aiosqlite.OperationalError:
                logging.warning("⚠️ Migrating Database: Adding 'timezone' column...")
                await db.execute("ALTER TABLE subscriptions ADD COLUMN timezone TEXT DEFAULT 'UTC'")
                logging.info("✅ Database updated successfully.")
            
            await db.commit()
            logging.info("✅ Database initialized.")

    async def add_subscription(self, user_id: int, city_name: str, lat: float, lon: float, time: str, timezone: str):
        """
        Stores the user's LOCAL time and their TIMEZONE separately.
        """
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute("""
                INSERT INTO subscriptions (user_id, city_name, latitude, longitude, schedule_time, timezone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, city_name, lat, lon, time, timezone))
            
            await db.commit()
            return cursor.lastrowid

    async def get_all_subscriptions(self):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM subscriptions")
            rows = await cursor.fetchall()
            return rows

    # ... Include get_user_subscriptions and delete_subscription as they were ...
    async def get_user_subscriptions(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
            return await cursor.fetchall()

    async def delete_subscription(self, sub_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
            await db.commit()

db_manager = DatabaseManager()