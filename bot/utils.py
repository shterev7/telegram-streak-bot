import random
import httpx
import datetime
import pytz
import os


motivational_quotes = [
    "❗️ Don’t wish for it. Work for it.",
    "❗️ Sweat now, shine later.",
    "❗️ The only bad workout is the one you didn’t do.",
    "❗️ One more rep. One more step. Let’s go!",
    "❗️ Progress starts with showing up!",
    "❗️ Discipline = freedom. Hit your streak!"
]


def get_random_quote():
    return random.choice(motivational_quotes)


def get_current_hour():
    tz = pytz.timezone("Europe/Sofia")
    return datetime.datetime.now(tz).hour


async def send_fire_reaction(bot_token: str, chat_id: str, message_id: int):
    url = f"https://api.telegram.org/bot{bot_token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": "🔥"}]
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                print(f"Failed to set 🔥 reaction: {r.status_code} - {r.text}")
    except Exception as e:
        print("HTTP request to set 🔥 reaction failed:", str(e))
