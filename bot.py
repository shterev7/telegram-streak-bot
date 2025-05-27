import os
import logging
import sqlite3
import datetime
import httpx

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Database setup ---
DB_NAME = "streaks.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            chat_id TEXT,
            user_id TEXT,
            user_name TEXT,
            streak INTEGER,
            last_date TEXT,
            count_today INTEGER,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    try:
        c.execute("ALTER TABLE streaks ADD COLUMN count_today INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def update_streak(chat_id, user_id, user_name):
    today = str(datetime.date.today())
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT streak, last_date, count_today FROM streaks WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()

    if row:
        current_streak, last_date, count_today = row

        if last_date != today:
            current_streak += 1
            count_today = 1
            c.execute("""
                UPDATE streaks
                SET streak=?, last_date=?, user_name=?, count_today=?
                WHERE chat_id=? AND user_id=?
            """, (current_streak, today, user_name, count_today, chat_id, user_id))
            streak_incremented = True

        elif count_today < 2:
            current_streak += 1
            count_today += 1
            c.execute("""
                UPDATE streaks
                SET streak=?, count_today=?, user_name=?
                WHERE chat_id=? AND user_id=?
            """, (current_streak, count_today, user_name, chat_id, user_id))
            streak_incremented = True

        else:
            logging.info(f"{user_name} already reached max streaks today")
            streak_incremented = False
    else:
        c.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, user_id, user_name, 1, today, 1))
        streak_incremented = True

    conn.commit()
    conn.close()
    return streak_incremented

def get_streaks(chat_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_name, streak FROM streaks WHERE chat_id=? ORDER BY streak DESC", (chat_id,))
    results = c.fetchall()
    conn.close()
    return results

# --- Helper: Send emoji reaction via Telegram HTTP API ---
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

# --- Message Handler ---
async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    user_name = update.message.from_user.full_name
    chat_id = str(update.message.chat.id)
    user_id = str(update.message.from_user.id)
    message_id = update.message.message_id

    logging.info(f"Received message: {text} from {user_name}")

    # Match + or ++ anywhere in the message as a separate word
    if any(token in ['+', '++'] for token in text.split()):
        streak_incremented = update_streak(chat_id, user_id, user_name)
        if streak_incremented:
            bot_token = context.bot.token
            await send_fire_reaction(bot_token, chat_id, message_id)
        return

    # Manually check for /streaks
    if text.startswith("/streaks"):
        logging.info("Manual /streaks handler triggered")
        results = get_streaks(chat_id)

        if not results:
            try:
                await context.bot.send_message(chat_id=chat_id, text="No streaks yet.")
            except Exception as e:
                logging.error("Failed to send streaks message", exc_info=True)
            return

        msg = "🔥 *Current Streaks:*\n"
        for name, streak in results:
            msg += f"{name}: {streak}\n"

        try:
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logging.error("Failed to send streaks message", exc_info=True)

# --- Main Bot Setup ---
if __name__ == '__main__':
    init_db()

    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise Exception("BOT_TOKEN environment variable is not set!")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_all_text))

    print("Bot is running...")
    app.run_polling()
