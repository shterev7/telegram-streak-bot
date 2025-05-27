import os
import logging
import datetime
import httpx
import asyncpg
from random import choice

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Database connection ---
async def connect_db():
    return await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# --- Ensure user exists in DB ---
async def ensure_user_exists(conn, chat_id, user_id, user_name):
    result = await conn.fetchrow("""
        SELECT 1 FROM streaks WHERE chat_id=$1 AND user_id=$2
    """, chat_id, user_id)
    if not result:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES ($1, $2, $3, 0, 0)
        """, chat_id, user_id, user_name)

# --- Update streak ---
async def update_streak(conn, chat_id, user_id, user_name):
    today = datetime.date.today()
    row = await conn.fetchrow("""
        SELECT streak, last_date, count_today FROM streaks
        WHERE chat_id=$1 AND user_id=$2
    """, chat_id, user_id)

    if row:
        streak, last_date, count_today = row['streak'], row['last_date'], row['count_today']
        if last_date != today:
            streak += 1
            count_today = 1
        elif count_today < 2:
            streak += 1
            count_today += 1
        else:
            return False  # Max streaks reached

        await conn.execute("""
            UPDATE streaks
            SET streak=$1, last_date=$2, user_name=$3, count_today=$4
            WHERE chat_id=$5 AND user_id=$6
        """, streak, today, user_name, count_today, chat_id, user_id)
    else:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
            VALUES ($1, $2, $3, 1, $4, 1)
        """, chat_id, user_id, user_name, today)

    return True

# --- Get all streaks for a chat ---
async def get_streaks(conn, chat_id):
    return await conn.fetch("""
        SELECT user_name, streak FROM streaks
        WHERE chat_id=$1
        ORDER BY streak DESC
    """, chat_id)

# --- Motivational Quotes ---
motivational_quotes = [
    "🏋️‍♂️ Don’t wish for it. Work for it.",
    "🔥 Sweat now, shine later.",
    "💪 The only bad workout is the one you didn’t do.",
    "🚀 One more rep. One more step. Let’s go!",
    "📈 Progress starts with showing up!",
    "⚡ Discipline = freedom. Hit your streak!"
]

def get_random_quote():
    return choice(motivational_quotes)

# --- Send 🔥 emoji reaction via Bot API ---
async def send_fire_reaction(bot_token: str, chat_id: str, message_id: int):
    url = f"https://api.telegram.org/bot{bot_token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": "🔥"}]
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                logging.error(f"Failed to set 🔥 reaction: {r.status_code} - {r.text}")
    except Exception as e:
        logging.error("HTTP request to set reaction failed", exc_info=True)

# --- Daily Reminder Job ---
async def send_daily_reminder(app):
    logging.info("Running daily reminder job...")
    group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not group_chat_id:
        logging.warning("GROUP_CHAT_ID not set.")
        return

    conn = await connect_db()
    today = datetime.date.today()
    rows = await conn.fetch("""
        SELECT user_id, user_name, last_date FROM streaks
        WHERE chat_id=$1
    """, group_chat_id)

    inactive = [
        (r['user_id'], r['user_name']) for r in rows
        if r['last_date'] != today
    ]

    if not inactive:
        logging.info("All users submitted at least 1 streak today.")
        await conn.close()
        return

    quote = get_random_quote()
    mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive])
    message = f"{quote}\n\nThese champions haven’t hit their streak today:\n{mentions}"

    try:
        await app.bot.send_message(
            chat_id=group_chat_id,
            text=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error("Failed to send reminder", exc_info=True)

    await conn.close()

# --- Message Handler ---
async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id
    text = update.message.text.strip()

    logging.info(f"Received message: {text} from {user_name} ({user_id})")

    conn = await connect_db()
    await ensure_user_exists(conn, chat_id, user_id, user_name)

    # Handle + or ++
    if any(token in ['+', '++'] for token in text.split()):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    # Handle /streaks
    if text.startswith("/streaks"):
        results = await get_streaks(conn, chat_id)
        if not results:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
        else:
            msg = "🔥 *Current Streaks:*\n"
            for row in results:
                msg += f"{row['user_name']}: {row['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        await conn.close()

# --- Main ---
if __name__ == '__main__':
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN not set!")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_all_text))

    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=25, args=[app])
    scheduler.start()

    print("Bot is running with Supabase backend...")
    app.run_polling()
