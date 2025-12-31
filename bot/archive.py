import datetime
from .db import connect_db

async def archive_and_reset_yearly_data(app):
    conn = await connect_db()
    year = datetime.datetime.now().year

    # Archive streaks
    streaks = await conn.fetch("""
        SELECT * FROM streaks
    """)
    for row in streaks:
        await conn.execute("""
            INSERT INTO streaks_archive (chat_id, user_id, user_name, streak, year)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
        """, row['chat_id'], row['user_id'], row['user_name'], row['streak'], year)

    # Reset streaks
    await conn.execute("UPDATE streaks SET streak = 0, last_date = NULL, count_today = 0")

    # Archive quest completions
    completions = await conn.fetch("""
        SELECT chat_id, user_id, user_name, COUNT(*) as completions
        FROM quest_completions
        GROUP BY chat_id, user_id, user_name
    """)
    for row in completions:
        await conn.execute("""
            INSERT INTO quest_completions_archive (chat_id, user_id, user_name, completions, year)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING
        """, row['chat_id'], row['user_id'], row['user_name'], row['completions'], year)

    # Clear quest completions
    await conn.execute("DELETE FROM quest_completions")

    await conn.close()
