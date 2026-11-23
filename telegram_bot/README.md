# MEBELCHI AI Telegram bot

aiogram 3.x companion to the web app. The bot has **no database**: every operation goes through the Django API,
authenticated with `TELEGRAM_BOT_API_SECRET` and acting on behalf of the account linked to the Telegram ID.

## Account linking

1. The user logs in on the web and opens **Telegram ulash** (the API: `POST /api/v1/telegram/link-code/`).
2. The web shows an 8-character code, valid 10 minutes, usable once. Only a keyed hash is stored on the server.
3. The user sends the code to the bot. The backend checks it, counts failed attempts per Telegram ID
   (5 attempts, then a 10-minute lock), and binds the Telegram chat to that account.

A Telegram ID on its own never proves ownership of a web account; the code is the proof.

## Features

| Area | Bot action |
|---|---|
| Menu | `/start`: inline main menu, different for linked and unlinked users |
| Profile | name, email, role |
| Projects | list, create (`Mebel yaratish` / `Yangi loyiha`), rename |
| Material calculator | 6 validated questions, backend engine result (panels, area, edge banding) |
| Cutting list | same questions, optional project, optimized layout summary, PDF and Excel download |
| Room design | `/room` (and a menu button): the guided room flow; state is kept on the server, so it continues after a restart. Doors, windows and furniture by buttons, sizes typed, openings by wall and distance, furniture added from the catalogue and nudged, rotated or removed. See `docs/ROOM_FLOW.md` |
| Files | send PDF, JPG/PNG/WEBP, DWG or DXF; validated (type, size, file signature) before upload |
| Notifications | unread list; the same messages are pushed to the chat by the backend |
| Admin | `/admin`, `/stats`, `/users`, `/system_status`, `/broadcast` (only for IDs in `ADMIN_TELEGRAM_IDS` and only if the linked account is staff) |

Languages: Uzbek (default), Russian, English. The language follows the Telegram client setting.

## Run locally

```bash
cd telegram_bot
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_API_SECRET (same value as the backend)
python main.py
```

The backend must run with the same `TELEGRAM_BOT_API_SECRET` and `API_BASE_URL` pointing at it.
Without `TELEGRAM_BOT_API_SECRET` every bot endpoint refuses requests (fail closed).

## Tests

```bash
cd telegram_bot && pytest -q          # 36 unit and handler tests, no network
```

The API client, FSM flows and validation are covered by unit tests. An end-to-end run of the same client against a
live Django server was verified separately (20 checks: linking, replay, calculation, projects, cutting list with
PDF/XLSX, upload, notifications, foreign-account isolation, admin gating, unlink).

## Security notes

- Secrets only from environment variables; `.env` is git-ignored.
- Bot-to-API calls use a constant-time secret comparison; the backend limits requests per Telegram user, not per IP.
- Uploads are checked in the bot and again in the backend; error messages to users never include internal details.
- Calculation output is marked for professional review, like the web app.
