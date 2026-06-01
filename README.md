# Telegram Giveaway Comment Viewer

Fetch all comments from a public Telegram channel post and format them for giveaways:

```text
no.1 @username - "comment text"
no.2 @username - "comment text"
```

Stack: **HTML/CSS/JS** frontend · **FastAPI** backend · **Telethon** (MTProto, user session)

## Folder structure

```text
telethon/
├── README.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── config.py
│   ├── formatters.py          # (optional) server-side formatting helpers
│   ├── link_parser.py
│   ├── main.py                # FastAPI + rate limit
│   ├── rate_limit.py
│   ├── requirements.txt
│   ├── telegram_service.py    # Telethon + pagination
│   └── scripts/
│       └── login.py           # Phone login (NOT bot)
└── frontend/
    ├── index.html
    ├── styles.css
    ├── app.js
    └── filters.js             # Client-side filters + formatting
```

## Prerequisites

- Python 3.10+
- Telegram **user** account (phone login)
- API credentials from [https://my.telegram.org/apps](https://my.telegram.org/apps)

**Do not use a bot token** — bots cannot call `GetRepliesRequest`.

## Step-by-step: run locally

### 1. Backend setup

```bash
cd backend
python -m venv .venv
```

**Git Bash:**

```bash
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
```

**PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```env
API_ID=your_id
API_HASH=your_hash
RATE_LIMIT_MAX_REQUESTS=15
RATE_LIMIT_WINDOW_SECONDS=60
```

### 2. Telegram session (phone login)

```bash
python scripts/login.py
```

Use your **phone number** and the code from Telegram. Do not paste a @BotFather bot token.

If you logged in as a bot before:

```bash
rm -f telegram_session.session telegram_session.session-journal
python scripts/login.py
```

### 3. Start server

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 4. Use the app

1. Paste a link: `https://t.me/channelname/123`
2. Click **Fetch Comments**
3. Click **Fetch Comments** (loads all comments, unfiltered)
4. Toggle filters as needed, then **Copy All** for the filtered list

## API

**GET** `/comments?link=https://t.me/channelname/123`

**Success (200):**

```json
{
  "total_fetched": 2,
  "comments": [
    {
      "user_id": 123,
      "username": "alice",
      "display": "@alice",
      "text": "Great giveaway!",
      "has_media": false,
      "has_text": true
    }
  ]
}
```

Formatting (`no.1 @user - "text"`) is done in the browser when filters are applied.

**No comments (200):**

```json
{
  "total_fetched": 0,
  "comments": [],
  "message": "No comments found for this post."
}
```

**Errors:** `error`, `total_fetched: 0`, `comments: []` with HTTP 400 / 403 / 404 / 429 / 502 / 503

**Health:** `GET /health`

## How it works

1. Parse `t.me/<channel>/<message_id>` (public links only).
2. On startup, connect Telethon with your saved user session.
3. For broadcast channels: `GetDiscussionMessage` → linked group → paginated `GetRepliesRequest`.
4. Return raw comments with `user_id`, `has_media`, `has_text` for UI filters.
5. Frontend applies optional filters and formats `no.1 @user - "text"` lines.
6. Rate limit: 15 requests per IP per 60 seconds (configurable in `.env`).

## Troubleshooting

| Issue | Fix |
|--------|-----|
| `BotMethodInvalidError` | Delete session, login with **phone** via `login.py` |
| `502` / discussion errors | Join the channel in Telegram with the same account |
| `429` from this app | Wait for rate limit window |
| `429` from Telegram | Wait `FloodWait` seconds shown in the error |
| Broken venv | Delete `.venv`, recreate, `pip install -r requirements.txt` |

## Notes

- No database; live fetch only.
- Public channels with comment threads (linked discussion group).
- Pagination: 100 comments per Telegram API page until exhausted.
