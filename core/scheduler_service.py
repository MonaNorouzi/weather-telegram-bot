# core/scheduler_service.py
"""Weather scheduler service - manages scheduled jobs"""

import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telethon import TelegramClient
from pytz import utc, timezone as pytz_timezone

from core.database_manager import db_manager
from core.scheduler_jobs import send_weather_job


class WeatherScheduler:
    def __init__(self, client: TelegramClient, loop):
        self.client = client
        self.scheduler = AsyncIOScheduler(event_loop=loop, timezone=utc)
        self.job_prefix = "job_"

    async def start(self):
        """Start scheduler with heartbeat and load existing jobs"""
        self.scheduler.add_job(
            self._heartbeat,
            trigger=IntervalTrigger(seconds=30),
            id="heartbeat_job",
            replace_existing=True
        )
        
        self.scheduler.start()
        logging.info("⏳ [Scheduler] Started with X-Ray Monitor.")
        
        all_subs = await db_manager.get_all_subscriptions()
        for sub in all_subs:
            try:
                await self._add_job_to_scheduler(sub)
            except Exception as e:
                logging.error(f"Failed to load job {sub['id']}: {e}")

    async def _heartbeat(self):
        """Log current time and upcoming jobs"""
        tehran = pytz_timezone('Asia/Tehran')
        now_str = datetime.now(tehran).strftime('%H:%M:%S')
        
        jobs = [j for j in self.scheduler.get_jobs() if j.id != 'heartbeat_job']
        
        if not jobs:
            logging.warning(f"💓 Heartbeat {now_str} | ⚠️ NO JOBS!")
        else:
            summary = []
            for j in jobs[:3]:
                if j.next_run_time:
                    rt = j.next_run_time.astimezone(tehran).strftime('%H:%M:%S')
                    summary.append(f"[{j.id} -> {rt}]")
            logging.info(f"💓 Heartbeat {now_str} | Pending: {', '.join(summary)}")

    async def add_new_subscription(self, sub_id, user_id, city_name, lat, lon, time_str, tz_name):
        """Add a new subscription job"""
        sub = {
            'id': sub_id, 'user_id': user_id, 'city_name': city_name,
            'latitude': lat, 'longitude': lon, 'schedule_time': time_str,
            'timezone': tz_name
        }
        await self._add_job_to_scheduler(sub)

    async def _add_job_to_scheduler(self, sub):
        """Schedule a job for subscription"""
        job_id = f"{self.job_prefix}{sub['id']}"
        
        try:
            hour, minute = map(int, sub['schedule_time'].split(':'))
        except ValueError:
            return

        try:
            tz = sub['timezone'] or 'Asia/Tehran'
            user_tz = pytz_timezone(tz) if tz != 'UTC' else pytz_timezone("Asia/Tehran")
        except Exception:
            user_tz = utc

        trigger = CronTrigger(hour=hour, minute=minute, second=0, timezone=user_tz)
        
        self.scheduler.add_job(
            lambda uid=sub['user_id'], cn=sub['city_name'], lat=sub['latitude'], lon=sub['longitude']: 
                send_weather_job(self.client, uid, cn, lat, lon),
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=120
        )
        logging.info(f"📅 Scheduled Job {sub['id']} for {hour}:{minute} ({user_tz})")

    async def remove_job(self, sub_id: int):
        """Remove a scheduled job"""
        job_id = f"{self.job_prefix}{sub_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)