import os
import datetime
from .db import connect_db
from .utils import get_random_quote


async def send_daily_reminder(app):
    group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not group_chat_id:
        return

    conn = await connect_db()
    today = datetime.date.today()
    rows = await conn.fetch("SELECT user_id, user_name, last_date FROM streaks WHERE chat_id=$1", group_chat_id)

    inactive = [(r['user_id'], r['user_name']) for r in rows if r['last_date'] != today]

    if not inactive:
        await conn.close()
        return

    quote = get_random_quote()
    mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive])
    message = f"{quote}\n\nThese champions haven’t hit their streak today:\n{mentions}"

    await app.bot.send_message(chat_id=group_chat_id, text=message, parse_mode="Markdown")
    await conn.close()
