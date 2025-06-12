# Telegram Streak Bot

A Telegram bot that helps groups stay accountable by tracking daily workout streaks using `+` or `++` messages and daily quests completions using unique hashtag for each quest. It motivates users, reacts to their streak updates and quest completions, and reminds inactive members with daily motivational quotes.

---

## 🚀 Features

### Streak tracking
- Reacts to messages containing `+` or `++` (even in captions)
- Tracks daily streaks per user
- Accepts `+` or `++` embedded in text (e.g. `++training`, `get+fit`)
- `/streaks` command shows current streak leaderboard
- Sends daily motivational reminders to users who haven't logged a streak
  
### Daily quests
- A random quest (e.g., "Drink 2L of water") is announced every day at **10:00 AM EET**.
- Each quest includes a unique hashtag (e.g. `#hydrated`).
- Users complete a quest by using the correct hashtag in any message **before 10:00 PM EET**.
- Each user can only complete the quest once per day.
- Bot reacts with 🔥 and tracks completions.
- Use `/questscore` to view the quest leaderboard.
- Use `/quest` to view today’s active quest and its hashtag.

---

## 🧱 Project Structure

```text
telegram-streak-bot/
├── bot/
│   ├── __init__.py
│   ├── db.py            # PostgreSQL interaction
│   ├── handlers.py      # Telegram message handling
│   ├── reminders.py     # Daily reminder logic
│   ├── quests.py        # Quest selection and retrieval
│   └── utils.py         # Emoji reactions and motivational quotes
├── main.py              # Entry point for the bot
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```
---

## 💬 Contribute

Have ideas to enhance the bot? Feel free to open issues or submit PRs!

