import os
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_all_text
from bot.reminders import send_daily_reminder


# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )

if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN not set!")

    app = ApplicationBuilder().token(TOKEN).build()
    message_filters = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.DOCUMENT | filters.CAPTION
    app.add_handler(MessageHandler(message_filters, handle_all_text))

    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.start()

    app.run_polling()