import os
import asyncpg
import datetime


async def connect_db():
    return await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


async def ensure_user_exists(conn, chat_id, user_id, user_name):
    result = await conn.fetchrow("SELECT 1 FROM streaks WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
    if not result:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, count_today)
            VALUES ($1, $2, $3, 0, 0)
        """, chat_id, user_id, user_name)


async def update_streak(conn, chat_id, user_id, user_name):
    today = datetime.date.today()
    row = await conn.fetchrow("SELECT streak, last_date, count_today FROM streaks WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)

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
            UPDATE streaks SET streak=$1, last_date=$2, user_name=$3, count_today=$4
            WHERE chat_id=$5 AND user_id=$6
        """, streak, today, user_name, count_today, chat_id, user_id)
    else:
        await conn.execute("""
            INSERT INTO streaks (chat_id, user_id, user_name, streak, last_date, count_today)
            VALUES ($1, $2, $3, 1, $4, 1)
        """, chat_id, user_id, user_name, today)

    return True


async def get_streaks(conn, chat_id):
    return await conn.fetch("SELECT user_name, streak FROM streaks WHERE chat_id=$1 ORDER BY streak DESC", chat_id)