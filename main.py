import os
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_all_text, handle_command
from bot.reminders import send_daily_reminder, send_daily_quest

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN not set in environment variables.")

    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(MessageHandler(filters.COMMAND, handle_command))

    # Text, captions
    app.add_handler(MessageHandler(filters.TEXT | filters.Caption, handle_all_text))

    # Daily jobs
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.add_job(send_daily_quest, "cron", hour=10, minute=0, args=[app])
    scheduler.start()

    print("Bot is running...")
    app.run_polling()
