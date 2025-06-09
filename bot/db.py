import asyncpg
import os
from typing import Any, Coroutine


async def connect_db() -> Coroutine:
    """Connect to the PostgreSQL database using environment variables"""

    return await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


async def ensure_user_exists(conn, chat_id: Any, user_id: Any, user_name: Any):
    """Ensure a user is registered in the streaks table"""

    result = await conn.fetchrow("""
        SELECT 1 FROM streaks WHERE chat_id=$1 AND user_id=$2
    """, chat_id, user_id)
    if not result:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES ($1, $2, $3, 0, 0)
        """, chat_id, user_id, user_name)


async def update_streak(conn, chat_id: Any, user_id: Any, user_name: Any):
    """Update streak count for a user"""

    from datetime import date
    today = date.today()
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
            return False  # Max streaks for today

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


async def get_streaks(conn, chat_id: Any):
    """Get all streaks in a chat"""

    return await conn.fetch("""
        SELECT user_name, streak FROM streaks
        WHERE chat_id=$1
        ORDER BY streak DESC
    """, chat_id)


async def has_completed_quest_today(conn, chat_id: Any, user_id: Any):
    """Check if the user completed today's quest"""

    from datetime import date
    today = date.today()
    row = await conn.fetchrow("""
        SELECT 1 FROM quest_completions
        WHERE chat_id=$1 AND user_id=$2 AND date=$3
    """, chat_id, user_id, today)
    return row is not None


async def update_quest_completion(conn, chat_id: Any, user_id: Any, user_name: Any):
    """Log quest completion"""

    from datetime import date
    today = date.today()
    await conn.execute("""
        INSERT INTO quest_completions (chat_id, user_id, user_name, date)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT DO NOTHING
    """, chat_id, user_id, user_name, today)


async def get_quest_scores(conn, chat_id: Any):
    """Get quest leaderboard"""

    return await conn.fetch("""
        SELECT user_name, COUNT(*) as quests
        FROM quest_completions
        WHERE chat_id=$1
        GROUP BY user_name
        ORDER BY quests DESC
    """, chat_id)


async def store_daily_quest(conn, chat_id: Any, description: Any, tag: Any, date: Any):
    """Store the daily quest persistently"""

    await conn.execute("""
        INSERT INTO daily_quests (chat_id, description, tag, date)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (chat_id, date) DO NOTHING
    """, chat_id, description, tag, date)


async def fetch_daily_quest(conn, chat_id: Any, date: Any):
    """Retrieve todays quest"""

    return await conn.fetchrow("""
        SELECT description, tag FROM daily_quests
        WHERE chat_id=$1 AND date=$2
    """, chat_id, date)
