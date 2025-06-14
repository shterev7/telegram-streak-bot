import os
import datetime
from .db import connect_db
from .utils import get_random_quote
from .quests import generate_daily_quests, fetch_daily_quests


async def send_daily_reminder(app):
    """Notify users who haven’t submitted their streak today."""
    conn = await connect_db()
    today = datetime.date.today()

    groups = await conn.fetch("SELECT chat_id FROM group_chats")
    for group in groups:
        chat_id = group['chat_id']
        rows = await conn.fetch("""
            SELECT user_id, user_name, last_date FROM streaks
            WHERE chat_id=$1
        """, chat_id)

        inactive = [(r['user_id'], r['user_name']) for r in rows if r['last_date'] != today]
        if not inactive:
            continue

        quote = get_random_quote()
        mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive])
        message = f"❗️ {quote}\n\nThese champions haven’t hit their streak today:\n{mentions}"

        await app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    await conn.close()


async def send_daily_quest(app):
    """Generate and send the daily quest announcement at 10:00 EET."""
    conn = await connect_db()
    today = datetime.date.today()

    groups = await conn.fetch("SELECT chat_id FROM group_chats")
    for group in groups:
        chat_id = group['chat_id']

        quests = await generate_daily_quests(conn, chat_id, today)
        if not quests:
            continue

        quest_text = "\n".join([f"- {q['description']}  \\#{q['tag']}" for q in quests])
        await app.bot.send_message(
            chat_id=chat_id,
            text=f"📢 *Today's Quests:*\n{quest_text}",
            parse_mode="Markdown"
        )

    await conn.close()
