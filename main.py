import os
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_all_text
from bot.reminders import send_daily_reminder, send_daily_quest

# Logging config
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Main bot launcher
if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    app.add_handler(MessageHandler(filters.ALL, handle_all_text))

    # Scheduler setup
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.add_job(send_daily_quest, "cron", hour=10, minute=0, args=[app])
    scheduler.start()

    logging.info("Bot is running...")
    app.run_polling()
