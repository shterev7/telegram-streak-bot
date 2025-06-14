import os
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_all_text, handle_command
from bot.reminders import send_daily_reminder, send_daily_quest

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    app.add_handler(MessageHandler(filters.ALL, handle_all_text))

    # Commands
    app.add_handler(MessageHandler(filters.COMMAND, handle_command))

    # Scheduler for reminders and daily quest announcements
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.add_job(send_daily_quest, "cron", hour=10, minute=0, args=[app])
    scheduler.start()

    app.run_polling()
