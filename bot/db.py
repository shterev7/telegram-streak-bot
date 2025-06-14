import asyncpg
import os


async def connect_db():
    """
    Establish and return a connection to the PostgreSQL database using environment variables.
    """
    return await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


async def ensure_user_exists(conn, chat_id: str, user_id: str, user_name: str):
    """
    Ensure that a user exists in the 'streaks' table. If not, insert them with default values.
    """
    result = await conn.fetchrow("""
        SELECT 1 FROM streaks WHERE chat_id=$1 AND user_id=$2
    """, chat_id, user_id)
    if not result:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES ($1, $2, $3, 0, 0)
        """, chat_id, user_id, user_name)


async def update_streak(conn, chat_id: str, user_id: str, user_name: str) -> bool:
    """
    Update the streak count for a user. Increment the streak if a new day,
    and allow a maximum of 2 increments per day.
    Returns True if streak was incremented, otherwise False.
    """
    import datetime
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
            return False  # Already maxed today
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


async def get_streaks(conn, chat_id: str):
    """
    Retrieve all streaks for users in a given chat, sorted by highest streak.
    """
    return await conn.fetch("""
        SELECT user_name, streak FROM streaks
        WHERE chat_id=$1
        ORDER BY streak DESC
    """, chat_id)


async def record_quest_completion(conn, chat_id: str, user_id: str, user_name: str, tag: str, date):
    """
    Record a user's completion of a quest for a specific date.
    """
    await conn.execute("""
        INSERT INTO quest_completions (chat_id, user_id, user_name, tag, date)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT DO NOTHING
    """, chat_id, user_id, user_name, tag, date)


async def has_completed_quest(conn, chat_id: str, user_id: str, tag: str, date) -> bool:
    """
    Check if a user has already completed a quest with the given tag on a specific date.
    """
    result = await conn.fetchrow("""
        SELECT 1 FROM quest_completions
        WHERE chat_id=$1 AND user_id=$2 AND tag=$3 AND date=$4
    """, chat_id, user_id, tag, date)
    return result is not None


async def get_quest_scoreboard(conn, chat_id: str):
    """
    Return a leaderboard showing how many quests each user has completed in a given chat.
    """
    return await conn.fetch("""
        SELECT user_name, COUNT(*) as total
        FROM quest_completions
        WHERE chat_id=$1
        GROUP BY user_name
        ORDER BY total DESC
    """, chat_id)
