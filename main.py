import os
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bot.handlers import handle_text_message, handle_streaks, handle_quest, handle_quest_score
from bot.reminders import send_daily_reminder, send_daily_quest

if __name__ == "__main__":
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN not set in environment variables.")

    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("streaks", handle_streaks))
    app.add_handler(CommandHandler("quest", handle_quest))
    app.add_handler(CommandHandler("questscore", handle_quest_score))

    # Text & caption handler
    app.add_handler(MessageHandler(filters.ALL, handle_text_message))

    # Scheduler for daily tasks
    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, trigger="cron", hour=21, minute=0, args=[app])
    scheduler.add_job(send_daily_quest, trigger="cron", hour=10, minute=0, args=[app])
    scheduler.start()

    print("Bot is running...")
    app.run_polling()
