import datetime
import random
from .db import connect_db


async def generate_daily_quest(chat_id: str):
    """Insert a random quest from quest_templates into daily_quests, excluding yesterday’s."""

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    conn = await connect_db()

    # Skip if today's quest is already set
    existing = await conn.fetchrow(
        "SELECT 1 FROM daily_quests WHERE chat_id=$1 AND date=$2",
        chat_id, today
    )
    if existing:
        await conn.close()
        return

    # Get yesterday's quest (to avoid repetition)
    yesterday_row = await conn.fetchrow(
        "SELECT tag FROM daily_quests WHERE chat_id=$1 AND date=$2",
        chat_id, yesterday
    )
    yesterday_tag = yesterday_row['tag'] if yesterday_row else None

    # Fetch all quest templates
    templates = await conn.fetch("SELECT description, tag FROM quest_templates")
    if not templates:
        await conn.close()
        return

    # Filter out yesterday’s quest if possible
    filtered = [q for q in templates if q['tag'] != yesterday_tag] if len(templates) > 1 else templates
    selected = random.choice(filtered)

    await conn.execute("""
        INSERT INTO daily_quests (chat_id, description, tag, date)
        VALUES ($1, $2, $3, $4)
    """, chat_id, selected["description"], selected["tag"], today)

    await conn.close()


async def fetch_daily_quest(conn, chat_id: str, date: datetime.date):
    """Return the daily quest for a given chat and date."""

    return await conn.fetchrow(
        "SELECT description, tag FROM daily_quests WHERE chat_id=$1 AND date=$2",
        chat_id, date
    )
