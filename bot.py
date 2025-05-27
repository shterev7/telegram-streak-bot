import os
import logging
import sqlite3
import datetime
import httpx
from random import choice

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DB_NAME = "streaks.db"

# --- Database setup ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            chat_id TEXT,
            user_id TEXT,
            user_name TEXT,
            streak INTEGER DEFAULT 0,
            last_date TEXT,
            count_today INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    conn.close()

# --- Track user if not already in DB ---
def ensure_user_exists(chat_id, user_id, user_name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM streaks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    if not c.fetchone():
        c.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES (?, ?, ?, 0, 0)
        """, (chat_id, user_id, user_name))
        logging.info(f"Added new user to DB: {user_name}")
    conn.commit()
    conn.close()

# --- Update streak on + or ++ ---
def update_streak(chat_id, user_id, user_name):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT streak, last_date, count_today FROM streaks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()

    if row:
        streak, last_date, count_today = row
        if last_date != today:
            streak += 1
            count_today = 1
        elif count_today < 2:
            streak += 1
            count_today += 1
        else:
            logging.info(f"{user_name} already reached max streaks today")
            conn.close()
            return False

        c.execute("""
            UPDATE streaks
            SET streak=?, last_date=?, user_name=?, count_today=?
            WHERE chat_id=? AND user_id=?
        """, (streak, today, user_name, count_today, chat_id, user_id))

    else:
        c.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
            VALUES (?, ?, ?, 1, ?, 1)
        """, (chat_id, user_id, user_name, today))

    conn.commit()
    conn.close()
    return True

# --- Get all streaks for group ---
def get_streaks(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT user_name, streak FROM streaks
        WHERE chat_id=?
        ORDER BY streak DESC
    """, (chat_id,))
    results = c.fetchall()
    conn.close()
    return results

# --- Motivational quotes ---
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

# --- Send 🔥 emoji reaction ---
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
            else:
                logging.info("🔥 reaction set successfully")
    except Exception as e:
        logging.error("HTTP request to set reaction failed", exc_info=True)

# --- Daily reminder job ---
async def send_daily_reminder(app):
    logging.info("Running daily reminder job...")

    group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not group_chat_id:
        logging.warning("GROUP_CHAT_ID not set. Skipping reminder.")
        return

    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, user_name, last_date FROM streaks WHERE chat_id=?", (group_chat_id,))
    users = c.fetchall()
    conn.close()

    inactive_users = [
        (uid, name) for uid, name, last_date in users
        if last_date != today
    ]

    if not inactive_users:
        logging.info("All users submitted at least 1 streak today.")
        return

    quote = get_random_quote()
    mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive_users])
    message = f"{quote}\n\nThese champions haven’t hit their streak today:\n{mentions}"

    try:
        await app.bot.send_message(
            chat_id=group_chat_id,
            text=message,
            parse_mode="Markdown"
        )
        logging.info("Reminder message sent.")
    except Exception as e:
        logging.error("Failed to send reminder message", exc_info=True)

# --- Message handler ---
async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    logging.info(f"Received message: {text} from {user_name} ({chat_id})")

    # Track user if not known yet
    ensure_user_exists(chat_id, user_id, user_name)

    # Handle streak increment
    if any(token in ['+', '++'] for token in text.split()):
        streak_incremented = update_streak(chat_id, user_id, user_name)
        if streak_incremented:
            await send_fire_reaction(context.bot.token, chat_id, message_id)
        return

    # Handle /streaks
    if text.startswith("/streaks"):
        logging.info("/streaks command triggered")
        results = get_streaks(chat_id)

        if not results:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
            return

        msg = "🔥 *Current Streaks:*\n"
        for name, streak in results:
            msg += f"{name}: {streak}\n"

        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

# --- App startup ---
if __name__ == '__main__':
    init_db()

    TOKEN = os.getenv("BOT_TOKEN")
    GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

    if not TOKEN:
        raise Exception("BOT_TOKEN is not set!")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_all_text))

    scheduler = AsyncIOScheduler(timezone="Europe/Sofia")
    scheduler.add_job(send_daily_reminder, "cron", hour=21, minute=0, args=[app])
    scheduler.start()

    print("Bot is running...")
    app.run_polling()
