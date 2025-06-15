import re
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db
from .quests import (
    fetch_daily_quests,
    fetch_user_quest_completions,
    record_quest_completion,
    calculate_quest_scores
)
from .utils import get_current_hour, send_fire_reaction


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text.strip()
    chat_id = str(update.message.chat.id)
    user_name = update.message.from_user.full_name
    logging.info(f"[COMMAND] Received: {text} from {user_name} in chat {chat_id}")

    if text.startswith("/streaks"):
        await handle_streaks(update, context)
    elif text.startswith("/quest"):
        await handle_quest(update, context)
    elif text.startswith("/questscore"):
        await handle_quest_score(update, context)


async def handle_streaks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await connect_db()
    chat_id = str(update.message.chat.id)
    rows = await conn.fetch("SELECT user_name, streak FROM streaks WHERE chat_id=$1 ORDER BY streak DESC", chat_id)

    if not rows:
        await update.message.reply_text("No users tracked yet.")
    else:
        msg = "🔥 *Current Streaks:*\n"
        for row in rows:
            msg += f"{row['user_name']}: {row['streak']}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    await conn.close()


async def handle_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await connect_db()
    chat_id = str(update.message.chat.id)
    quests = await fetch_daily_quests(conn, chat_id)
    if not quests:
        await update.message.reply_text("No quests found for today.")
    else:
        quest_list = "\n".join([f"- {q['description']} (use #{q['tag']})" for q in quests])
        await update.message.reply_text(f"📢 *Today's Quests:*\n{quest_list}", parse_mode="Markdown")
    await conn.close()


async def handle_quest_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await connect_db()
    chat_id = str(update.message.chat.id)
    leaderboard = await calculate_quest_scores(conn, chat_id)

    if not leaderboard:
        await update.message.reply_text("No quest completions yet.")
    else:
        msg = "🏆 *Quest Leaderboard:*\n"
        for row in leaderboard:
            msg += f"{row['user_name']}: {row['count']}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    await conn.close()


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id
    text = update.message.text.strip()
    hour = get_current_hour()

    logging.info(f"Received message: {text} from {user_name} ({user_id})")

    conn = await connect_db()

    # --- STREAK detection ---
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
        await update_streak(conn, chat_id, user_id, user_name, update, context)

    # --- QUEST detection ---
    hashtags = re.findall(r"#\w+", text)
    if hashtags:
        quests = await fetch_daily_quests(conn, chat_id)
        tags_today = [q['tag'] for q in quests]
        completed_tags = await fetch_user_quest_completions(conn, chat_id, user_id)

        for tag in hashtags:
            tag_clean = tag.lstrip("#")
            if tag_clean in tags_today:
                if tag_clean in [t['tag'] for t in completed_tags]:
                    logging.info(f"{user_name} already completed quest {tag_clean} today.")
                    continue

                if hour >= 22:
                    await update.message.reply_text("⏰ Sorry, today's quest can no longer be completed. A new one will come tomorrow!")
                    continue

                await record_quest_completion(conn, chat_id, user_id, user_name, tag_clean)
                await update.message.reply_text(f"✅ {user_name} completed the quest for #{tag_clean}! 🔥")
                await send_fire_reaction(context.bot.token, chat_id, message_id)

    await conn.close()


async def update_streak(conn, chat_id, user_id, user_name, update, context):
    today = datetime.today().date()
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
            return

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

    await send_fire_reaction(context.bot.token, chat_id, update.message.message_id)
