import datetime
import random
from .db import connect_db


async def generate_daily_quests(chat_id):
    conn = await connect_db()

    # Fetch existing quests from past 2 days
    existing = await conn.fetch("""
        SELECT tag FROM daily_quests
        WHERE chat_id=$1 AND date >= $2
    """, chat_id, datetime.date.today() - datetime.timedelta(days=2))

    used_tags = {row['tag'] for row in existing}

    # Load available quests from quest_templates
    rows = await conn.fetch("SELECT description, tag FROM quest_templates")
    all_quests = [dict(row) for row in rows if row['tag'] not in used_tags]

    if len(all_quests) < 2:
        await conn.close()
        return []

    selected = random.sample(all_quests, 2)
    today = datetime.date.today()
    for quest in selected:
        await conn.execute("""
            INSERT INTO daily_quests (chat_id, description, tag, date)
            VALUES ($1, $2, $3, $4)
        """, chat_id, quest['description'], quest['tag'], today)

    await conn.close()
    return selected


async def fetch_daily_quests(conn, chat_id):
    today = datetime.date.today()
    return await conn.fetch("""
        SELECT description, tag FROM daily_quests
        WHERE chat_id=$1 AND date=$2
    """, chat_id, today)


async def record_quest_completion(conn, chat_id, user_id, user_name, tag):
    today = datetime.date.today()
    await conn.execute("""
        INSERT INTO quest_completions (chat_id, user_id, user_name, tag, date)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT DO NOTHING
    """, chat_id, user_id, user_name, tag, today)


async def fetch_user_quest_completions(conn, chat_id, user_id):
    today = datetime.date.today()
    rows = await conn.fetch("""
        SELECT tag FROM quest_completions
        WHERE chat_id=$1 AND user_id=$2 AND date=$3
    """, chat_id, user_id, today)
    return {row["tag"] for row in rows}


async def calculate_quest_scores(conn, chat_id):
    return await conn.fetch("""
        SELECT user_name, COUNT(*) as count FROM quest_completions
        WHERE chat_id=$1
        GROUP BY user_name
        ORDER BY count DESC
    """, chat_id)
