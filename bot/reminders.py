import os
import datetime
from pytz import timezone
from .db import connect_db
from .utils import get_random_quote
from .quests import generate_daily_quest, fetch_daily_quest


async def send_daily_reminder(app):
    """Notify users who haven’t submitted their streak today."""

    group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not group_chat_id:
        return

    conn = await connect_db()
    today = datetime.date.today()
    rows = await conn.fetch(
        "SELECT user_id, user_name, last_date FROM streaks WHERE chat_id=$1",
        group_chat_id
    )

    inactive = [
        (r['user_id'], r['user_name']) for r in rows if r['last_date'] != today
    ]

    if not inactive:
        await conn.close()
        return

    quote = get_random_quote()
    mentions = "\n".join([f"[{name}](tg://user?id={uid})" for uid, name in inactive])
    message = f"{quote}\n\n❗️These champions haven’t hit their streak today:\n{mentions}"

    await app.bot.send_message(chat_id=group_chat_id, text=message, parse_mode="Markdown")
    await conn.close()


async def send_daily_quest(app):
    """Generate and send the daily quest announcement at 10:00 EET."""

    group_chat_id = os.getenv("GROUP_CHAT_ID")
    if not group_chat_id:
        return

    await generate_daily_quest(group_chat_id)

    tz = timezone("Europe/Sofia")
    today = datetime.datetime.now(tz).date()

    conn = await connect_db()
    quest = await fetch_daily_quest(conn, group_chat_id, today)
    await conn.close()

    if quest:
        await app.bot.send_message(
            chat_id=group_chat_id,
            text=(
                f"❗️ *Today's Quest* ❗️\n"
                f"{quest['description']}\n\n"
                f"Use `#{quest['tag']}` to complete it before 22:00!"
            ),
            parse_mode="Markdown"
        )
