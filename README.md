# 🎬 Telegram Movie Bot

A production-ready Telegram bot that delivers movies from a private channel to users via unique codes. Built with **Python 3.12+, Aiogram 3, and SQLite**.

---

## Features

| Feature | Details |
|---|---|
| 🔑 Movie lookup by code | Numeric or alphanumeric codes |
| 🎭 Category browsing | Action, Comedy, Drama, Horror, Sci-Fi, Animation, Uzbek |
| 🔥 Popular movies | Ranked by total requests |
| 🛠 Full admin panel | Add / edit / delete movies, broadcast, stats |
| 🔒 Admin protection | IsAdmin filter + ADMIN_IDS env var |
| ⚡ Efficient delivery | `copy_message` — no server-side file downloads |
| 📊 Statistics | Users, requests, top movies |

---

## Project Structure

```
movie_bot/
├── bot.py              ← Entry point
├── config.py           ← Environment / validation
├── database.py         ← Async SQLite (aiosqlite)
├── requirements.txt
├── .env.example
├── .gitignore
├── handlers/
│   ├── start.py        ← /start + main-menu callbacks
│   ├── movies.py       ← Movie lookup + category browsing
│   └── admin.py        ← Admin panel (FSM workflows)
├── keyboards/
│   ├── user.py         ← User-facing inline keyboards
│   └── admin.py        ← Admin inline keyboards
├── states/
│   └── admin.py        ← FSM state groups
└── utils/
    └── validators.py   ← Input validation helpers
```

---

## Prerequisites

- Python 3.12 or newer
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A private Telegram channel where the bot is an **administrator**

---

## Installation (Windows PowerShell)

```powershell
# 1. Navigate to the project folder
cd C:\Users\user\.gemini\antigravity\scratch\movie_bot

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file
Copy-Item .env.example .env
```

Then open `.env` in your editor and fill in the values:

```env
BOT_TOKEN=1234567890:ABCdefGhIjKlmNoPQRsTUVwxyz
ADMIN_IDS=123456789
CHANNEL_ID=-1001234567890
```

---

## BotFather Setup

1. Open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Follow the prompts to choose a name and username.
3. Copy the **API token** into `BOT_TOKEN` in your `.env`.
4. (Optional) Set bot commands:

```
start - Botni boshlash
admin - Admin paneli
addmovie - Kino qo'shish
deletemovie - Kino o'chirish
editmovie - Kino tahrirlash
movies - Kinolar ro'yxati
stats - Statistika
broadcast - Xabar yuborish
```

---

## Private Channel Configuration

### Step 1 — Create or choose a private channel

Create a **private** Telegram channel. This channel will store the video files.

### Step 2 — Add the bot as administrator

1. Open the channel → **Manage Channel** → **Administrators**.
2. Add your bot and grant it at least **Post Messages** and **Copy Messages** permissions.

### Step 3 — Get the channel ID

Forward any message from the channel to [@userinfobot](https://t.me/userinfobot) or use the Telegram API to retrieve the numeric channel ID (it starts with `-100`). Set it as `CHANNEL_ID` in `.env`.

---

## Adding Movies (Admin Workflow)

1. **Upload the video** to your private channel (post it there directly).
2. Note the **message ID** — right-click the message in the Telegram desktop app → *Copy Message Link*. The number after the last `/` is the message ID.
3. In your bot chat (as admin), send `/addmovie` or open `/admin` and tap **➕ Kino qo'shish**.
4. Follow the prompts:
   - Enter the movie code (e.g. `101`)
   - Enter the title
   - Enter the description (or send `/skip`)
   - Select the category
   - **Either** forward the channel post directly to the bot, **or** type the message ID manually.
5. The bot verifies it can access the message and saves it to the database.

> **Tip:** Forwarding the channel post is the easiest and most reliable method — the bot reads the channel ID and message ID automatically.

---

## Running the Bot

```powershell
# Make sure the venv is active
.\venv\Scripts\Activate.ps1

python bot.py
```

Logs are written to both stdout and `bot.log`.

---

## Admin Commands Reference

| Command | Description |
|---|---|
| `/admin` | Open the admin panel |
| `/addmovie` | Add a new movie (FSM wizard) |
| `/deletemovie` | Delete a movie by code (with confirmation) |
| `/editmovie` | Edit title, description, or category |
| `/movies` | List all registered movies |
| `/stats` | View bot statistics |
| `/broadcast` | Send an announcement to all users |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram Bot API token |
| `ADMIN_IDS` | ✅ | Comma-separated list of admin Telegram IDs |
| `CHANNEL_ID` | ✅ | Private channel ID (negative integer) |
| `DB_PATH` | ❌ | SQLite file path (default: `bot.db`) |

---

## Security Notes

- The `.env` file is listed in `.gitignore` — **never commit it**.
- Admin operations are protected by an `IsAdmin` filter that checks `ADMIN_IDS`.
- All SQL queries use parameterised statements.
- Private channel links and internal IDs are never exposed to regular users.
- Telegram API errors (`TelegramBadRequest`, `TelegramForbiddenError`, `TelegramRetryAfter`) are handled gracefully.
