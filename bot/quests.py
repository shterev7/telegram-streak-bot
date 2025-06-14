import datetime
import random
from .db import connect_db


async def generate_daily_quests(chat_id: str):
    """
    Select 2 unique random quests and store them in daily_quests table,
    excluding any used in the past 2 days.
    """
    today = datetime.date.today()
    one_day_ago = today - datetime.timedelta(days=1)
    two_days_ago = today - datetime.timedelta(days=2)

    conn = await connect_db()

    # Skip if today's quests already exist
    existing = await conn.fetch(
        "SELECT tag FROM daily_quests WHERE chat_id=$1 AND date=$2",
        chat_id, today
    )
    if len(existing) >= 2:
        await conn.close()
        return

    # Get used tags from past 2 days
    recent_tags = await conn.fetch(
        "SELECT tag FROM daily_quests WHERE chat_id=$1 AND date IN ($2, $3)",
        chat_id, one_day_ago, two_days_ago
    )
    recent_tags = set(row['tag'] for row in recent_tags)

    # Get all templates
    templates = await conn.fetch("SELECT description, tag FROM quest_templates")
    candidates = [t for t in templates if t['tag'] not in recent_tags]

    # Fallback if not enough unique candidates
    if len(candidates) < 2:
        candidates = templates

    selected = random.sample(candidates, 2)
    for quest in selected:
        await conn.execute(
            """
            INSERT INTO daily_quests (chat_id, description, tag, date)
            VALUES ($1, $2, $3, $4)
            """,
            chat_id, quest['description'], quest['tag'], today
        )

    await conn.close()


async def fetch_daily_quests(conn, chat_id: str, date: datetime.date):
    """
    Return all quests for a given chat and date.
    """
    return await conn.fetch(
        "SELECT description, tag FROM daily_quests WHERE chat_id=$1 AND date=$2",
        chat_id, date
    )
