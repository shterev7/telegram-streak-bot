import re
from telegram import Update
from telegram.ext import ContextTypes
from .db import connect_db, ensure_user_exists, update_streak, get_streaks
from .utils import send_fire_reaction


async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    user_name = user.full_name
    user_id = str(user.id)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id
    text = (update.message.text or update.message.caption or "").strip()

    conn = await connect_db()
    await ensure_user_exists(conn, chat_id, user_id, user_name)

    if re.search(r'(?<![-])\+{1,2}(?![-])', text):
        updated = await update_streak(conn, chat_id, user_id, user_name)
        if updated:
            await send_fire_reaction(context.bot.token, chat_id, message_id)
        await conn.close()
        return

    if text.startswith("/streaks"):
        results = await get_streaks(conn, chat_id)
        if not results:
            await context.bot.send_message(chat_id=chat_id, text="No users tracked yet.")
        else:
            msg = "🔥 *Current Streaks:*\n"
            for row in results:
                msg += f"{row['user_name']}: {row['streak']}\n"
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        await conn.close()
