import logging
import datetime
import re
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db, ensure_user_exists
from .quests import fetch_daily_quests, fetch_user_quest_completions, record_quest_completion, calculate_quest_scores
from .utils import get_current_hour, send_fire_reaction


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text or update.message.caption or ""
    text = text.strip()
    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    logging.info(f"[MESSAGE] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()
    await ensure_user_exists(conn, chat_id, user_id, user_name)

    # Handle + or ++ (no adjacent hyphens)
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
        await update_streak(conn, chat_id, user_id, user_name)
        await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    # Handle quest completion
    quests_today = await fetch_daily_quests(conn, chat_id)
    current_hour = get_current_hour()
    if current_hour >= 22:
        await context.bot.send_message(
            chat_id=chat_id,
            text="⏰ Sorry, today's quest can no longer be completed. A new one will come tomorrow!"
        )
        await conn.close()
        return

    completed_tags = [row['tag'] for row in await fetch_user_quest_completions(conn, chat_id, user_id)]
    for quest in quests_today:
        tag = quest['tag']
        if tag in completed_tags:
            continue
        if f"#{tag}" in text:
            await record_quest_completion(conn, chat_id, user_id, user_name, tag)
            await context.bot.send_message(chat_id=chat_id, text=f"🔥 Quest completed for #{tag}!")
            await send_fire_reaction(context.bot.token, chat_id, message_id)
            break

    await conn.close()


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)

    logging.info(f"[COMMAND] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()
    await ensure_user_exists(conn, chat_id, user_id, user_name)

    if text.startswith("/streaks"):
        rows = await conn.fetch("""
            SELECT user_name, streak FROM streaks
            WHERE chat_id=$1
            ORDER BY streak DESC
        """, chat_id)

        if not rows:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
        else:
            msg = "🔥 *Current Streaks:*\n"
            for row in rows:
                msg += f"{row['user_name']}: {row['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    elif text.startswith("/quest"):
        quests = await fetch_daily_quests(conn, chat_id)
        if not quests:
            await context.bot.send_message(chat_id=chat_id, text="No quest assigned today.")
        else:
            msg = "📢 *Today's Quests:*\n"
            for quest in quests:
                msg += f"- {quest['description']} (Use #{quest['tag']})\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    elif text.startswith("/questscore"):
        leaderboard = await calculate_quest_scores(conn, chat_id)
        if not leaderboard:
            await context.bot.send_message(chat_id=chat_id, text="No quests completed yet.")
        else:
            msg = "🏆 *Quest Leaderboard:*\n"
            for row in leaderboard:
                msg += f"{row['user_name']}: {row['count']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    await conn.close()


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
            return  # Max reached today
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
