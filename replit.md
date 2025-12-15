# WABeta News Telegram Bot

## Overview
A Telegram bot that fetches WhatsApp news from WABetaInfo RSS feed and posts updates to a Telegram channel. Includes user management, bookmarks, subscriptions, and admin features.

## Project Structure
```
/
├── bot/
│   ├── main.py       # Main bot logic with handlers
│   └── utils.py      # Utility functions for RSS, images, summaries
├── Procfile          # Heroku deployment config
├── runtime.txt       # Python version for Heroku
├── requirements.txt  # Python dependencies
└── .gitignore
```

## Configuration
Environment variables needed:
- `TELEGRAM_BOT_TOKEN` - Bot token from BotFather
- `TELEGRAM_CHANNEL_ID` - Target channel ID
- `TELEGRAM_CHANNEL_USERNAME` - Channel username without @
- `TELEGRAM_ADMIN_ID` - Admin user ID for admin features
- `HUGGINGFACE_TOKEN` (optional) - For article summarization

## Features
- RSS feed monitoring from WABetaInfo
- Auto-posting to Telegram channel
- User subscriptions by category
- Bookmark system
- Admin panel with stats
- Broadcast messages
- Article summarization

## Deployment (Heroku)
1. Create Heroku app
2. Set environment variables in Heroku dashboard
3. Push code to Heroku
4. Use worker dyno (not web)

## Running Locally
```bash
cd bot
python main.py
```
