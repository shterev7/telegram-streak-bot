import os
import datetime
from .db import connect_db
from .utils import get_random_quote
from .quests import generate_daily_quests, fetch_daily_quests


async def send_daily_reminder(app):
    conn = await connect_db()
    today = datetime.date.today()

    # Get all unique group chat IDs from streaks table
    chat_ids = await conn.fetch("SELECT DISTINCT chat_id FROM streaks")

    for row in chat_ids:
        chat_id = row['chat_id']
        rows = await conn.fetch("""
            SELECT user_id, user_name, last_date FROM streaks
            WHERE chat_id=$1
        """, chat_id)

        inactive = [(r['user_id'], r['user_name']) for r in rows if r['last_date'] != today]

        if not inactive:
            continue

        quote = get_random_quote()
        mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive])
        message = f"❗️{quote}\n\nThese champions haven’t hit their streak today:\n{mentions}"

        try:
            await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send reminder to {chat_id}: {e}")

    await conn.close()


async def send_daily_quest(app):
    conn = await connect_db()
    today = datetime.date.today()

    # Get all unique chat IDs from streaks table
    chat_ids = await conn.fetch("SELECT DISTINCT chat_id FROM streaks")

    for row in chat_ids:
        chat_id = row['chat_id']

        # Check if quests already exist
        quests = await fetch_daily_quests(conn, chat_id)
        if quests:
            continue

        # Generate and announce
        generated = await generate_daily_quests(chat_id)
        if not generated:
            continue

        message = "📢 *Today's Quests:*\n"
        for q in generated:
            message += f"- {q['description']} (Use #{q['tag']} to complete the quest)\n"

        try:
            await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send daily quests to {chat_id}: {e}")

    await conn.close()
