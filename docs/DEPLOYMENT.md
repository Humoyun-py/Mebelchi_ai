# Deployment

## 1. Configure

```bash
cp .env.example .env
python -c "import secrets;print(secrets.token_urlsafe(64))"   # use as DJANGO_SECRET_KEY
```

Edit every `CHANGE` value. Set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL` to your public origin, and configure real SMTP (password-reset emails depend on it). The backend refuses to start without `DJANGO_SECRET_KEY` unless `DJANGO_DEBUG=true`.

## 2. Start and deploy

First start and every later deploy use one script. It stops at the first failure and never migrates without a verified backup:

```bash
deploy/deploy.sh --dry-run     # validates docker-compose.yml and prints the plan, changes nothing
deploy/deploy.sh               # asks you to type DEPLOY, then: build -> db up -> verified backup -> release -> start everything
docker compose exec backend python manage.py createsuperuser   # first administrator only
```

Services: `db` (PostgreSQL 16), `redis`, `release` (one-shot: migrations and `collectstatic`), `backend` (gunicorn), `worker` and `beat` (Celery: nightly pruning of old system logs and expired refresh tokens, daily audit-size check), `telegram-bot`, `web` (Nginx serving the built SPA, proxying `/api/` and `/django-admin/`), `backup`.

### Migrations are a separate, gated step

The backend no longer migrates when it starts (`RUN_MIGRATIONS` is ignored). Only the `release` service changes the schema, and `backend`, `worker` and `beat` wait for it (`depends_on: service_completed_successfully`), so a failed release stops the deploy while the old containers keep running.

| Situation | What `release` does |
|---|---|
| nothing pending | `collectstatic` only; the database is not touched |
| pending migrations, **empty** database (first install) | applies them |
| pending migrations, **existing** database | requires `/backups/LATEST_OK`: written by a backup that passed `pg_restore --list` and checksum verification, at most `BACKUP_MAX_AGE_MINUTES` old (default 120), files matching their SHA-256. Otherwise it exits 1 and prints `REFUSED: ...` |
| database unreachable / migration fails | exits 1; the log names the failing migration |

By hand: `docker compose run --rm backup once && docker compose run --rm release`. If a migration fails half-way, restore from the backup that the release step just verified (section 5) before retrying.

## 3. TLS

The stack listens on plain HTTP (`WEB_PORT`). Terminate TLS in front of it and forward `X-Forwarded-Proto: https`. With `SECURE_SSL_REDIRECT=true` (default in production) Django redirects HTTP to HTTPS and enables HSTS and secure cookies. Set `SECURE_SSL_REDIRECT=false` only for a local HTTP test.

**Decide where TLS terminates before changing nginx.** What is safe depends on it:

| Where TLS ends | Needed | Why |
|---|---|---|
| a proxy/load balancer in front of this stack (Caddy, Traefik, Cloudflare, a cloud LB) | the proxy must **overwrite** `X-Forwarded-Proto` and `X-Forwarded-For` (not append client-supplied values), and nginx here should trust only the proxy's address range (`set_real_ip_from <range>; real_ip_header X-Forwarded-For;`) | `frontend/nginx.conf` currently forwards the client's `X-Forwarded-Proto` unchanged and sets `X-Real-IP` to the peer address, which behind a proxy is the proxy: audit-log IPs would all be the proxy's |
| nginx in this stack (add a `listen 443 ssl` server) | certificates mounted, `proxy_set_header X-Forwarded-Proto $scheme;` and a port 80 -> 443 redirect | then nothing client-supplied reaches Django |
| a host-level nginx in front of the `web` container | same as the first row | |

Already in place and verified: the database and Redis publish no ports (only `web` does), the backend is reachable only through nginx, `SECURE_PROXY_SSL_HEADER` is set only outside DEBUG, secure session/CSRF cookies, HSTS for one year, `CORS_ALLOW_CREDENTIALS=False` (JWT in the `Authorization` header), CORS/CSRF origins come from the environment, and a strict CSP is sent by nginx. `HSTS_PRELOAD` is intentionally off. Redis has no password: keep it on the internal compose network.

## 4. Private files

Uploaded images, documents and avatars live in the `media` volume. Nginx deliberately does **not** serve `/media`; the API returns signed 15-minute links and streams the file after verifying the signature. Do not add a public `/media` location.

## 5. Backups and restore

The `backup` service runs `deploy/backup.sh` once a day (and `backup.sh once` on demand). Each successful run writes, in the `backups` volume:

- `mebelchi-<stamp>.dump`: `pg_dump -Fc`, checked with `pg_restore --list`;
- `mebelchi-<stamp>.media.tar.gz`: the uploaded files (the `media` volume, mounted read-only), checked with `tar -t`;
- `mebelchi-<stamp>.sha256`: checksums of both, re-verified right after writing;
- `LATEST_OK`: the marker the release step demands. A failed run never touches it; it writes `LAST_FAILURE` instead.

Settings (`.env`): `BACKUP_RETENTION_DAYS` (default 14; the newest `BACKUP_KEEP_MIN` sets, default 3, are never pruned), `BACKUP_INTERVAL_SECONDS`, `BACKUP_MAX_AGE_MINUTES` (release guard).

**Off-host copy.** A backup on the same machine is not a backup. Mount remote storage into the `backup` service (add a volume such as `- /mnt/offsite:/offsite` in `docker-compose.yml`, from NFS, an rclone mount, ...) and set `BACKUP_OFFSITE_DIR=/offsite`; each backup is copied and its checksum verified there. For other tools set `BACKUP_POST_HOOK` (a shell command; it sees `BACKUP_DB_FILE`, `BACKUP_MEDIA_FILE`, `BACKUP_SHA_FILE`).

**Alerts.** A failed backup, off-site copy or hook is written to the container log and, if configured, sent to `BACKUP_ALERT_WEBHOOK_URL` or Telegram (`BACKUP_ALERT_TELEGRAM_BOT_TOKEN` + `BACKUP_ALERT_TELEGRAM_CHAT_ID`). The message contains no user data. The `backup` container is also `unhealthy` in `docker compose ps` when there has been no verified backup for 25 hours (`BACKUP_HEALTH_MAX_MIN`).

**Restore** always goes into a *separate* database first, and refuses to touch the live one without `--allow-production-target --force`:

```bash
docker compose cp backup:/backups/mebelchi-<stamp>.dump .     # also the .sha256 and .media.tar.gz
deploy/restore.sh --db-file mebelchi-<stamp>.dump --target-db mebelchi_restore_check \
                  --media-file mebelchi-<stamp>.media.tar.gz --media-dir ./media_restored
```

It verifies the checksum, restores, then prints table, migration, user and audit-row counts plus the number of audit triggers, and compares the number of restored media files with the archive. To go live from a restored database, point `POSTGRES_DB` at it (or restore into the live name after stopping the backend, with the two flags above). Rehearse this once before you need it: `deploy/tests/test_backup_restore.sh` does it end to end against a throwaway PostgreSQL.

## 6. Upgrades

```bash
git pull && deploy/deploy.sh      # backup -> release (gated migrations) -> restart
```

## 7. Operations notes

- Scale the API by raising gunicorn `--workers` in `backend/Dockerfile` or running more `backend` replicas behind Nginx. Throttle counters use the Redis cache, so they are shared between workers when `REDIS_URL` is set.
- Plan limits and prices are rows in the `Plan` table (editable in `/django-admin/` or the Administration page via subscriptions). Feature flags (`registration`, `chat`, `optimizer`, `exports`, `interior_designer`) are managed in Administration → Features. Only `registration` is enforced server-side today; the others are exposed to the client for gating.
- Server errors (5xx) are stored in `SystemLog` and shown in Administration → Logs. Add an external monitor for uptime.
- Payments: no gateway is integrated. Confirm incoming payments in Administration → Billing to activate plans.
- Security checks: `docker compose exec backend python manage.py check --deploy`.

## 8. Database selection and SQLite fallback

Selection happens once per process at start (`backend/config/database.py`):

1. `DB_ENGINE=postgresql` (default when `POSTGRES_DB` is set) connects to PostgreSQL with a 3-second timeout.
2. If PostgreSQL is reachable, it is used. The active engine is logged at startup and shown in the admin system status (`GET /api/v1/admin-api/system/`).
3. If it is unreachable and `DATABASE_FALLBACK_ENABLED=true`, Django uses SQLite at `SQLITE_PATH`. A WARNING is logged on every start.
4. If it is unreachable and fallback is disabled (the production default), the process refuses to start with a message that names the reason. Nothing is switched silently.
5. Data is never copied or merged between the two databases. A process that ran on SQLite writes its rows to SQLite only. Moving them requires a deliberate export and import (below).

Operational rules:

- Keep `DATABASE_FALLBACK_ENABLED=false` in production. Turn it on only as a deliberate, announced decision.
- If the system ran on the fallback, stop the service, restore PostgreSQL, and decide what to do with the SQLite rows before restarting.
- Run the test suite on both engines before each release:

```bash
cd backend
POSTGRES_DB=mebelchi_db POSTGRES_USER=mebelchi_user POSTGRES_PASSWORD=... POSTGRES_HOST=localhost python manage.py test apps
env -u POSTGRES_DB python manage.py test apps        # SQLite
```

Migrations are the same for both engines: `python manage.py migrate`. Back up SQLite with `sqlite3 db.sqlite3 ".backup backup.sqlite3"` (safe while the server runs); back up PostgreSQL with `deploy/backup.sh`.

## 9. Database connections

Measured on the running stack (40 parallel requests): 3 PostgreSQL connections, one per gunicorn worker (`CONN_MAX_AGE=60`, sync workers). Budget at default settings:

| Consumer | Connections |
|---|---|
| gunicorn, 3 sync workers per `backend` container | 3 |
| Celery worker (prefork, default concurrency = CPU count, e.g. 12) | up to 12, only while tasks use the database |
| Celery beat, telegram-bot | 0 (beat only schedules; the bot talks to the API) |
| backup, release, `manage.py` shells | 1 each, short-lived |
| **Total on one 12-core host** | **about 20 of the 100 allowed by `max_connections`** |

PgBouncer is **not needed** today. Revisit it when `replicas x 3 + Celery concurrency` approaches 60, or if gunicorn is changed to threaded/async workers. Until then, cap Celery with `--concurrency=N` on very large hosts.

## 10. Audit log retention

The audit table is append-only (model layer, and a PostgreSQL trigger that refuses UPDATE, DELETE and TRUNCATE even for raw SQL). It is never trimmed by the application. Retention therefore means **copying** old rows out and, optionally, a deliberate operator-run shrink.

```bash
docker compose exec backend python manage.py audit_archive --report                 # rows, size, oldest/newest; exit 1 with --fail-on-warn
docker compose exec backend python manage.py audit_archive --archive --out-dir /app/media/audit-archive --older-than-days 365
docker compose exec backend python manage.py audit_archive --verify  --out-dir /app/media/audit-archive
```

`--archive` writes gzip JSON-lines files plus a manifest (row count, id range, SHA-256), continues after the highest archived id, never overwrites, and **deletes nothing**. `--verify` re-checks every file and that archived rows still match the table. Copy the archive directory off the host together with the backups. A daily Celery task logs a WARNING when the table exceeds `AUDIT_TABLE_WARN_MB` (default 2048).

**Dedicated roles (recommended, once).** `deploy/sql/audit_roles.sql`, run by a superuser, creates the read-only `mebelchi_audit_archiver` role (set `AUDIT_ARCHIVER_USER` / `AUDIT_ARCHIVER_PASSWORD` so `audit_archive` reads through it) and moves the table, its sequence and the `public` schema to a NOLOGIN owner role. The application role then keeps only SELECT and INSERT: it cannot UPDATE, DELETE, TRUNCATE, ALTER or DROP the table, or drop its triggers (tested). Consequence: a future migration that alters `audit_auditlog` must be run by a superuser. Shrinking the table (after `--verify` and an off-host copy) is likewise a superuser decision, for example a partition drop; there is intentionally no code path for it.
