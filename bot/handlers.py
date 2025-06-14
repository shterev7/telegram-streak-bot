import re
import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from .db import connect_db
from .utils import send_fire_reaction, get_current_hour
from .quests import fetch_daily_quests, record_quest_completion, calculate_quest_scores


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message:
        return

    message = update.effective_message
    text = message.text or message.caption or ""
    user = message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(message.chat.id)
    message_id = message.message_id

    if not text:
        return

    print(f"[TEXT] {text} from {user_name} in {chat_id}")

    conn = await connect_db()

    # Ensure user tracked for streaks
    await conn.execute("""
        INSERT INTO streaks (chat_id, user_id, user_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (chat_id, user_id) DO UPDATE SET user_name = EXCLUDED.user_name
    """, chat_id, user_id, user_name)

    # Handle streaks via "+" or "++"
    if re.search(r'(?<!-)\+{1,2}(?!-)', text):
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
                await conn.close()
                return

            await conn.execute("""
                UPDATE streaks SET streak=$1, last_date=$2, count_today=$3
                WHERE chat_id=$4 AND user_id=$5
            """, streak, today, count_today, chat_id, user_id)
        else:
            await conn.execute("""
                INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
                VALUES ($1, $2, $3, 1, $4, 1)
            """, chat_id, user_id, user_name, today)

        await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    # Handle daily quest hashtag completion
    if text.startswith("#"):
        quests = await fetch_daily_quests(conn, chat_id)
        if not quests:
            await conn.close()
            return

        valid_tags = {q['tag']: q['description'] for q in quests}
        today = datetime.date.today()
        hour = get_current_hour()

        for tag in valid_tags:
            if f"#{tag}" in text.lower():
                # Check if already completed
                existing = await conn.fetchval("""
                    SELECT 1 FROM quest_completions
                    WHERE chat_id=$1 AND user_id=$2 AND tag=$3 AND date=$4
                """, chat_id, user_id, tag, today)

                if existing:
                    await conn.close()
                    return

                if hour >= 22:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="⏰ Sorry, today's quest can no longer be completed. A new one will come tomorrow!"
                    )
                    await conn.close()
                    return

                await record_quest_completion(conn, chat_id, user_id, user_name, tag, today)
                await send_fire_reaction(context.bot.token, chat_id, message_id)
                break

    await conn.close()


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    message = update.message
    text = message.text.strip()
    user_name = message.from_user.full_name
    chat_id = str(message.chat.id)

    print(f"[COMMAND] Received: {text} from {user_name} in chat {chat_id}")

    conn = await connect_db()

    if text.startswith("/streaks"):
        rows = await conn.fetch("""
            SELECT user_name, streak FROM streaks
            WHERE chat_id=$1 ORDER BY streak DESC
        """, chat_id)

        if not rows:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
        else:
            msg = "🔥 *Current Streaks:*\n"
            for row in rows:
                msg += f"{row['user_name']}: {row['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)

    elif text.startswith("/quest"):
        today = datetime.date.today()
        quests = await fetch_daily_quests(conn, chat_id)

        if not quests:
            await context.bot.send_message(chat_id=chat_id, text="No quest assigned yet today.")
        else:
            msg = "📢 *Today's Quests:*\n"
            for q in quests:
                msg += f"- {q['description']} (Use #{q['tag']})\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)

    elif text.startswith("/questscore"):
        scores = await calculate_quest_scores(conn, chat_id)
        if not scores:
            await context.bot.send_message(chat_id=chat_id, text="No quest completions yet.")
        else:
            msg = "🏆 *Quest Leaderboard:*\n"
            for row in scores:
                msg += f"{row['user_name']}: {row['count']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)

    await conn.close()


async def update_streak(chat_id, user_id, user_name):
    conn = await connect_db()
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
            await conn.close()
            return False

        await conn.execute("""
            UPDATE streaks SET streak=$1, last_date=$2, count_today=$3, user_name=$4
            WHERE chat_id=$5 AND user_id=$6
        """, streak, today, count_today, user_name, chat_id, user_id)
    else:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
            VALUES ($1, $2, $3, 1, $4, 1)
        """, chat_id, user_id, user_name, today)

    await conn.close()
    return True
