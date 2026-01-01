import logging
import re
import datetime
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db
from .utils import get_current_hour, send_fire_reaction
from .quests import fetch_daily_quests, fetch_user_quest_completions, record_quest_completion, calculate_quest_scores

# Regex to match valid + or ++ but not combinations like +- or -+
PLUS_REGEX = re.compile(r'(?<!-)\+{1,2}(?!-)')
YEAR_STREAKS_REGEX = re.compile(r"^/streaks(\d{4})$")
YEAR_QUESTS_REGEX = re.compile(r"^/questscore(\d{4})$")


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


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text or update.message.caption or ""
    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    logging.info(f"[TEXT] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()

    # Ensure user is tracked
    await conn.execute("""
        INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
        VALUES ($1, $2, $3, 0, 0)
        ON CONFLICT (chat_id, user_id) DO NOTHING
    """, chat_id, user_id, user_name)

    # YEARLY STREAKS: /streaksYYYY
    match = YEAR_STREAKS_REGEX.match(text)
    if match:
        year = int(match.group(1))
        rows = await conn.fetch("""
            SELECT user_name, streak FROM streaks_archive
            WHERE chat_id=$1 AND year=$2
            ORDER BY streak DESC
        """, chat_id, year)
        if not rows:
            await context.bot.send_message(chat_id=chat_id, text=f"No streak data found for {year}.")
        else:
            msg = f"📅 *Streaks {year}:*\n"
            for r in rows:
                msg += f"{r['user_name']}: {r['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        await conn.close()
        return

    # YEARLY QUEST SCORES: /questscoreYYYY
    match = YEAR_QUESTS_REGEX.match(text)
    if match:
        year = int(match.group(1))
        scores = await conn.fetch("""
            SELECT user_name, completions FROM quest_completions_archive
            WHERE chat_id=$1 AND year=$2
            ORDER BY completions DESC
        """, chat_id, year)
        if not scores:
            await context.bot.send_message(chat_id=chat_id, text=f"No quest data found for {year}.")
        else:
            msg = f"🏆 *Quest Leaderboard {year}:*\n"
            for row in scores:
                msg += f"{row['user_name']}: {row['completions']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        await conn.close()
        return

    # Handle + or ++ for streaks
    if PLUS_REGEX.search(text):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)

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
            for r in rows:
                msg += f"{r['user_name']}: {r['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # Handle /questscore command
    elif text.startswith("/questscore"):
        scores = await calculate_quest_scores(conn, chat_id)
        if not scores:
            await context.bot.send_message(chat_id=chat_id, text="No quest completions yet.")
        else:
            msg = "🏆 *Quest Leaderboard:*\n"
            for row in scores:
                msg += f"{row['user_name']}: {row['count']} quest(s)\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # Handle /quest command
    elif text.startswith("/quest"):
        quests = await fetch_daily_quests(conn, chat_id)
        if not quests:
            await context.bot.send_message(chat_id=chat_id, text="No quests for today.")
        else:
            msg = "📢 *Today's Quests:*\n"
            for q in quests:
                msg += f"- {q['description']} (Use #{q['tag']} to complete the quest until 22:00)\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    # Hashtag detection for quest completions
    else:
        hashtags = set(re.findall(r'#(\w+)', text.lower()))
        if not hashtags:
            await conn.close()
            return

        current_hour = get_current_hour()
        if current_hour >= 22:
            await context.bot.send_message(chat_id=chat_id, text=f"⏰ Sorry {user_name}, today's quest can no longer be completed. "
                                                                     "A new one will come tomorrow!")
            await conn.close()
            return

        quests = await fetch_daily_quests(conn, chat_id)
        completed_tags = await fetch_user_quest_completions(conn, chat_id, user_id)
        new_completions = []

        for quest in quests:
            quest_tag = quest['tag'].lower()
            if quest_tag in hashtags and quest_tag not in completed_tags:
                inserted = await record_quest_completion(conn, chat_id, user_id, user_name, quest_tag)
                if inserted:
                    await send_fire_reaction(context.bot.token, chat_id, message_id)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ {user_name} completed the quest: *{quest['description']}*!",
                        parse_mode="Markdown"
                    )
                    new_completions.append(quest_tag)

    await conn.close()
