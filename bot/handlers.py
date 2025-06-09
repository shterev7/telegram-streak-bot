import re
import datetime
from pytz import timezone
from telegram import Update
from telegram.ext import ContextTypes
from .db import (
    connect_db,
    ensure_user_exists,
    update_streak,
    get_streaks,
    has_completed_quest_today,
    update_quest_completion,
    get_quest_scores,
    fetch_daily_quest,
)
from .utils import send_fire_reaction


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Functionality handler of streaks and quests"""

    if not update.message:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id
    text = update.message.text or update.message.caption or ""
    text = text.strip()

    conn = await connect_db()
    await ensure_user_exists(conn, chat_id, user_id, user_name)

    # Streak Handling
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)

    # Quest Completion
    tz = timezone("Europe/Sofia")
    now = datetime.datetime.now(tz)
    today = now.date()
    cutoff = tz.localize(datetime.datetime.combine(today, datetime.time(22, 0)))

    quest_row = await fetch_daily_quest(conn, chat_id, today)

    if quest_row:
        quest_tag = f"#{quest_row['tag'].lower()}"

        if quest_tag in text.lower():
            if now > cutoff:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ Sorry {user_name}, today's quest deadline has passed. Try again tomorrow!"
                )
            elif not await has_completed_quest_today(conn, chat_id, user_id):
                await update_quest_completion(conn, chat_id, user_id, user_name)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ {user_name} completed today's quest!"
                )
                await send_fire_reaction(context.bot.token, chat_id, message_id)

    # /streaks command
    if text.startswith("/streaks"):
        results = await get_streaks(conn, chat_id)
        if not results:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
        else:
            msg = "🔥 *Current Streaks:*\n"
            for row in results:
                msg += f"{row['user_name']}: {row['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # /questscore leaderboard command
    if text.startswith("/questscore"):
        scores = await get_quest_scores(conn, chat_id)
        if not scores:
            await context.bot.send_message(chat_id=chat_id, text="No quest completions yet.")
        else:
            msg = "🏆 *Quest Leaderboard:*\n"
            for row in scores:
                msg += f"{row['user_name']}: {row['quests']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # /quest today command
    if text.startswith("/quest"):
        quest_row = await fetch_daily_quest(conn, chat_id, today)
        if not quest_row:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ No quest has been announced for today yet."
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❗️ *Today's Quest* ❗️\n"
                    f"{quest_row['description']}\n\n"
                    f"Use `#{quest_row['tag']}` to complete it!"
                ),
                parse_mode="Markdown"
            )

    await conn.close()
