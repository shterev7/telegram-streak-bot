# Telegram Streak Bot

A Telegram bot that helps groups stay accountable by tracking daily workout streaks using `+` or `++` messages. It motivates users, reacts to their streak updates, and reminds inactive members with daily motivational quotes.

---

## 🚀 Features

- Reacts to messages containing `+` or `++` (even in captions)
- Tracks daily streaks per user
- Accepts `+` or `++` embedded in text (e.g. `++training`, `get+fit`)
- `/streaks` command shows current streak leaderboard
- Sends daily motivational reminders to users who haven't logged a streak

---

## 🧱 Project Structure

```text
telegram-streak-bot/
├── bot/
│   ├── __init__.py
│   ├── db.py            # PostgreSQL interaction
│   ├── handlers.py      # Telegram message handling
│   ├── reminders.py     # Daily reminder logic
│   └── utils.py         # Emoji reactions and motivational quotes
├── main.py              # Entry point for the bot
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```
---

## 💬 Contribute

Have ideas to enhance the bot? Feel free to open issues or submit PRs!

