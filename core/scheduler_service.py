# core/scheduler_service.py

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telethon import TelegramClient
from pytz import utc, timezone as pytz_timezone

from core.database_manager import db_manager
from core.weather_api import get_weather

class WeatherScheduler:
    def __init__(self, client: TelegramClient, loop):
        self.client = client
        # Initialize AsyncIO Scheduler compatible with Telethon
        self.scheduler = AsyncIOScheduler(event_loop=loop, timezone=utc)
        self.job_prefix = "job_"

    async def start(self):
        """
        Starts the scheduler and adds a monitoring job (Heartbeat).
        """
        # 1. Add Heartbeat Job (Every 30 seconds)
        # This will LOG the next scheduled jobs so we are not blind.
        self.scheduler.add_job(
            self._heartbeat,
            trigger=IntervalTrigger(seconds=30),
            id="heartbeat_job",
            replace_existing=True
        )
        
        self.scheduler.start()
        logging.info("⏳ [Scheduler] Started with X-Ray Monitor.")
        
        # 2. Load existing jobs
        all_subs = await db_manager.get_all_subscriptions()
        for sub in all_subs:
            try:
                await self._add_job_to_scheduler(sub)
            except Exception as e:
                logging.error(f"Failed to load job {sub['id']}: {e}")

    async def _heartbeat(self):
        """
        X-RAY: Logs current time AND the next upcoming jobs.
        This proves if the job is actually scheduled correctly.
        """
        tehran = pytz_timezone('Asia/Tehran')
        now = datetime.now(tehran)
        now_str = now.strftime('%H:%M:%S')
        
        # Get all jobs
        jobs = self.scheduler.get_jobs()
        user_jobs = [j for j in jobs if j.id != 'heartbeat_job']
        
        if not user_jobs:
            logging.warning(f"💓 Heartbeat {now_str} | ⚠️ NO JOBS FOUND! Please add a city.")
        else:
            summary = []
            for j in user_jobs:
                if j.next_run_time:
                    # Show when it will run in TEHRAN time
                    run_time = j.next_run_time.astimezone(tehran).strftime('%H:%M:%S')
                    summary.append(f"[City_ID:{j.id} -> {run_time}]")
                else:
                    summary.append(f"[{j.id} -> PAUSED]")
            
            # Log the status
            logging.info(f"💓 Heartbeat {now_str} | Pending: {', '.join(summary[:3])}")

    async def add_new_subscription(self, sub_id, user_id, city_name, lat, lon, time_str, tz_name):
        sub = {
            'id': sub_id, 'user_id': user_id, 'city_name': city_name,
            'latitude': lat, 'longitude': lon, 'schedule_time': time_str,
            'timezone': tz_name
        }
        await self._add_job_to_scheduler(sub)

    async def _add_job_to_scheduler(self, sub):
        job_id = f"{self.job_prefix}{sub['id']}"
        
        try:
            hour, minute = map(int, sub['schedule_time'].split(':'))
        except ValueError:
             return

        # Handle Timezone
        try:
            if sub['timezone'] and sub['timezone'] != 'UTC':
                user_tz = pytz_timezone(sub['timezone'])
            else:
                user_tz = pytz_timezone("Asia/Tehran") 
        except Exception:
            user_tz = utc

        trigger = CronTrigger(hour=hour, minute=minute, second=0, timezone=user_tz)
        
        # Add job with explicit grace time
        self.scheduler.add_job(
            self._send_weather_job,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=120, # 2 minutes grace time
            args=[sub['user_id'], sub['city_name'], sub['latitude'], sub['longitude']]
        )
        
        logging.info(f"📅 Scheduled Job {sub['id']} for {hour}:{minute} ({user_tz})")

    async def remove_job(self, sub_id: int):
        job_id = f"{self.job_prefix}{sub_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def _send_weather_job(self, user_id, city_name, lat, lon):
        """
        Sends the weather message. Fixes 'Entity not found' by forcing lookup.
        """
        logging.info(f"🚀 EXECUTION STARTED: User {user_id} | City {city_name}")
        
        try:
            # 1. Get Weather
            weather_data = {'type': 'city' if lat == 0 else 'coords', 'name': city_name, 'lat': lat, 'lon': lon}
            report = await get_weather(weather_data)
            
            # 2. Send Message (Robust Method)
            try:
                # Try standard send
                await self.client.send_message(user_id, f"🔔 **Daily Report:**\n\n{report}")
            except Exception:
                logging.warning(f"⚠️ Direct send failed for {user_id}. Trying to fetch entity...")
                # Try to resolve entity from network
                try:
                    user = await self.client.get_input_entity(user_id)
                    await self.client.send_message(user, f"🔔 **Daily Report:**\n\n{report}")
                except Exception as final_e:
                    logging.error(f"❌ FATAL: Could not resolve user {user_id}: {final_e}")
                    return

            logging.info(f"✅ SUCCESS: Message delivered to {user_id}")

        except Exception as e:
            logging.error(f"❌ JOB FAILED: {e}", exc_info=True)