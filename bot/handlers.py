import re
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db
from .quests import (
    fetch_daily_quests,
    record_quest_completion,
    fetch_user_quest_completions,
    calculate_quest_scores
)
from .utils import get_current_hour, send_fire_reaction

QUEST_COMPLETION_DEADLINE = 22  # 22:00 EET


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


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id
    text = (update.message.text or update.message.caption or "").strip()

    if not text:
        return

    logging_text = f"[COMMAND] Received: {text} from {user_name} in chat {chat_id}"
    print(logging_text)

    conn = await connect_db()
    await conn.execute("""
        INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
        VALUES ($1, $2, $3, 0, 0)
        ON CONFLICT DO NOTHING
    """, chat_id, user_id, user_name)

    # Handle /streaks command
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
        await conn.close()
        return

    # Handle /quest command
    if text.startswith("/quest"):
        quests = await fetch_daily_quests(conn, chat_id)
        if not quests:
            await context.bot.send_message(chat_id=chat_id, text="No quest for today yet.")
        else:
            message = "📢 *Today's Quests:*\n"
            for q in quests:
                message += f"- {q['description']} (use #{q['tag']})\n"
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        await conn.close()
        return

    # Handle /questscore command
    if text.startswith("/questscore"):
        leaderboard = await calculate_quest_scores(conn, chat_id)
        if not leaderboard:
            await context.bot.send_message(chat_id=chat_id, text="No quest completions yet.")
        else:
            message = "🏆 *Quest Leaderboard:*\n"
            for row in leaderboard:
                message += f"{row['user_name']}: {row['count']}\n"
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
        await conn.close()
        return

    # Handle streak message + or ++ without special adjacent characters like -+
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    # Quest hashtag completion
    hashtags = set(part[1:].lower() for part in text.split() if part.startswith("#"))
    if not hashtags:
        await conn.close()
        return

    if get_current_hour() >= QUEST_COMPLETION_DEADLINE:
        await context.bot.send_message(chat_id=chat_id, text="⏰ Sorry, today's quest can no longer be completed. A "
                                                             "new one will come tomorrow!")
        await conn.close()
        return

    quests_today = await fetch_daily_quests(conn, chat_id)
    completed_tags = await fetch_user_quest_completions(conn, chat_id, user_id)
    new_completions = []

    for quest in quests_today:
        quest_tag = quest['tag'].lower()
        if quest_tag in hashtags and quest_tag not in completed_tags:
            await record_quest_completion(conn, chat_id, user_id, user_name, quest_tag)
            await send_fire_reaction(context.bot.token, chat_id, message_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ {user_name} completed the quest: *{quest['description']}*!",
                parse_mode="Markdown"
            )
            new_completions.append(quest_tag)

    await conn.close()
