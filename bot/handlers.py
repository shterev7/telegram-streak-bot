import logging
import re
import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from .db import connect_db
from .utils import send_fire_reaction, get_current_hour
from .quests import fetch_daily_quests, fetch_user_quest_completions,  record_quest_completion, calculate_quest_scores


# Regex pattern to detect + or ++ without adjacent hyphens
PLUS_PATTERN = re.compile(r'(?<![\w\d\-])\+{1,2}(?![\w\d\-])')


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    text = update.message.text.strip()
    message_id = update.message.message_id

    logging.info(f"[TEXT] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()
    await ensure_user_in_streaks(conn, chat_id, user_id, user_name)

    # Check for + or ++ for streaks
    if PLUS_PATTERN.search(text):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    # Check for quest completion via valid hashtag
    if '#' in text:
        current_hour = get_current_hour()
        if current_hour >= 22:
            await context.bot.send_message(chat_id=chat_id, text="⏰ Sorry, today's quest can no longer be completed. "
                                                                 "A new one will come tomorrow!")
            await conn.close()
            return

        quests = await fetch_daily_quests(conn, chat_id)
        completions = await fetch_user_quest_completions(conn, chat_id, user_id)
        completed_tags = {r['tag'] for r in completions}

        for quest in quests:
            if f"#{quest['tag']}" in text and quest['tag'] not in completed_tags:
                await record_quest_completion(conn, chat_id, user_id, user_name, quest['tag'])
                await context.bot.send_message(chat_id=chat_id, text=f"🔥 {user_name} completed the quest: {quest['description']}")
                await send_fire_reaction(context.bot.token, chat_id, message_id)
                break

    await conn.close()


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    text = update.message.text.strip()

    logging.info(f"[COMMAND] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()

    if text.startswith("/streaks"):
        rows = await conn.fetch("SELECT user_name, streak FROM streaks WHERE chat_id=$1 ORDER BY streak DESC", chat_id)
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
            await context.bot.send_message(chat_id=chat_id, text="No quests announced today.")
        else:
            msg = "📢 *Today's Quests:*\n"
            for q in quests:
                msg += f"{q['description']} (use #{q['tag']})\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    elif text.startswith("/questscore"):
        scores = await calculate_quest_scores(conn, chat_id)
        if not scores:
            await context.bot.send_message(chat_id=chat_id, text="No quest completions yet.")
        else:
            msg = "🏆 *Quest Leaderboard:*\n"
            for row in scores:
                msg += f"{row['user_name']}: {row['count']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    await conn.close()


async def ensure_user_in_streaks(conn, chat_id, user_id, user_name):
    row = await conn.fetchrow("SELECT 1 FROM streaks WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
    if not row:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES ($1, $2, $3, 0, 0)
        """, chat_id, user_id, user_name)


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
            return False

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
