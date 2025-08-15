# scheduler_service.py
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram_client import TelegramClient
from database import DatabaseManager
from config import settings

logger = logging.getLogger(__name__)


class PortfolioScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db_manager = DatabaseManager()
        self.telegram_client = TelegramClient(
            settings.telegram_bot_url,
            settings.telegram_chat_id
        )
        self.running = False

    async def take_daily_snapshot(self, manual):
        """Take daily portfolio snapshot
        :param manual:
        """
        try:
            current_date = datetime.now(timezone.utc).date()
            if manual is False:
                current_date = current_date - timedelta(days=1)
            logger.info(f"📸 Taking daily snapshot for {current_date}")

            # Get portfolio total from telegram bot
            total_value = await self.telegram_client.get_portfolio_total()

            if total_value is None:
                logger.error("❌ Failed to get portfolio total from telegram bot")
                return False

            if total_value <= 0:
                logger.warning("⚠️ Portfolio value is zero, skipping snapshot")
                return False

            # Save to database
            success = self.db_manager.save_total_value(current_date, total_value)

            if success:
                logger.info(f"✅ Daily snapshot completed: {current_date} = ${total_value:.2f}")
            else:
                logger.error("❌ Failed to save snapshot to database")

            return success

        except Exception as e:
            logger.error(f"❌ Error taking daily snapshot: {e}")
            return False

    async def manual_snapshot(self):
        """Take manual snapshot (for testing)"""
        logger.info("🔧 Taking manual snapshot")
        return await self.take_daily_snapshot(manual=True)

    def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("⚠️ Scheduler is already running")
            return

        try:
            # Schedule daily snapshot at 00:00 GMT
            self.scheduler.add_job(
                self.take_daily_snapshot,
                CronTrigger(hour=0, minute=00, timezone='UTC'),
                [False],
                id='daily_snapshot',
                name='Daily Portfolio Snapshot',
                replace_existing=True
            )

            self.scheduler.start()
            self.running = True
            logger.info("🚀 Portfolio scheduler started - daily snapshots at 00:00 GMT")

        except Exception as e:
            logger.error(f"❌ Error starting scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return

        self.scheduler.shutdown()
        self.running = False
        logger.info("🛑 Portfolio scheduler stopped")

    async def cleanup(self):
        """Cleanup resources"""
        await self.telegram_client.close()

