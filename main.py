import os
import logging
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_all_text
from bot.reminders import send_daily_reminder, send_daily_quest

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# --- Bot Setup ---
def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise Exception("BOT_TOKEN environment variable not set")

    app = ApplicationBuilder().token(token).build()

    # Register handler for all text/caption messages
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, handle_all_text))

    # Scheduler for reminders and daily quests
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_quest, "cron", hour=10, minute=0, args=[app])
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.start()

    logging.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
