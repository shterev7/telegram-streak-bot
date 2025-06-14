import datetime
import re
import os
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db
from .quests import fetch_daily_quests
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
    text = (update.message.text or update.message.caption or "").strip()

    conn = await connect_db()

    # Track group chats
    if update.message.chat.type in ["group", "supergroup"]:
        await conn.execute("""
            INSERT INTO group_chats (chat_id, title)
            VALUES ($1, $2)
            ON CONFLICT (chat_id) DO UPDATE SET title = EXCLUDED.title
        """, chat_id, update.message.chat.title)

    # Ensure user is registered
    await conn.execute("""
        INSERT INTO streaks (chat_id, user_id, user_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (chat_id, user_id) DO UPDATE SET user_name = EXCLUDED.user_name
    """, chat_id, user_id, user_name)

    today = datetime.date.today()

    # Streak check
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
        streak_row = await conn.fetchrow("""
            SELECT last_date, count_today, streak FROM streaks
            WHERE chat_id=$1 AND user_id=$2
        """, chat_id, user_id)

        if streak_row:
            last_date = streak_row['last_date']
            count_today = streak_row['count_today']
            streak = streak_row['streak']

            if last_date != today:
                streak += 1
                count_today = 1
            elif count_today < 2:
                streak += 1
                count_today += 1
            else:
                await conn.close()
                return

            await conn.execute("""
                UPDATE streaks SET last_date=$1, count_today=$2, streak=$3
                WHERE chat_id=$4 AND user_id=$5
            """, today, count_today, streak, chat_id, user_id)

            await send_fire_reaction(context.bot.token, chat_id, message_id)

    # Quest completion
    quests = await fetch_daily_quests(conn, chat_id, today)
    current_hour = datetime.datetime.now().hour

    for quest in quests:
        if quest['tag'] in text.lower():
            if current_hour >= 22:
                await context.bot.send_message(
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text="⏰ Sorry, quest completions are only accepted before 22:00 EET."
                )
                continue

            existing = await conn.fetchrow("""
                SELECT 1 FROM quest_completions
                WHERE chat_id=$1 AND user_id=$2 AND tag=$3 AND date=$4
            """, chat_id, user_id, quest['tag'], today)

            if not existing:
                await conn.execute("""
                    INSERT INTO quest_completions (chat_id, user_id, user_name, tag, date)
                    VALUES ($1, $2, $3, $4, $5)
                """, chat_id, user_id, user_name, quest['tag'], today)
                await send_fire_reaction(context.bot.token, chat_id, message_id)

    await conn.close()


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Functionality handler for commands"""
    if not update.message:
        return

    chat_id = str(update.message.chat.id)
    text = update.message.text.strip()

    conn = await connect_db()

    if text.startswith("/streaks"):
        results = await conn.fetch("""
            SELECT user_name, streak FROM streaks
            WHERE chat_id=$1 ORDER BY streak DESC
        """, chat_id)

        if results:
            message = "🔥 *Current Streaks:*\n"
            for row in results:
                message += f"{row['user_name']}: {row['streak']}\n"
        else:
            message = "No streaks found."

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    elif text.startswith("/questscore"):
        results = await conn.fetch("""
            SELECT user_name, COUNT(*) as points FROM quest_completions
            WHERE chat_id=$1 GROUP BY user_name ORDER BY points DESC
        """, chat_id)

        if results:
            message = "🏆 *Quest Leaderboard:*\n"
            for row in results:
                message += f"{row['user_name']}: {row['points']}\n"
        else:
            message = "No completed quests yet."

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    elif text.startswith("/quest"):
        today = datetime.date.today()
        quests = await fetch_daily_quests(conn, chat_id, today)
        if quests:
            message = "📢 *Today's Quests:*\n"
            for q in quests:
                message += f"- {q['description']}  \\#{q['tag']}\n"
        else:
            message = "No quests announced yet."

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")

    await conn.close()
