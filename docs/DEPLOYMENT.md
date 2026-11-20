# Deployment

## 1. Configure

```bash
cp .env.example .env
python -c "import secrets;print(secrets.token_urlsafe(64))"   # use as DJANGO_SECRET_KEY
```

Edit every `CHANGE` value. Set `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL` to your public origin, and configure real SMTP (password-reset emails depend on it). The backend refuses to start without `DJANGO_SECRET_KEY` unless `DJANGO_DEBUG=true`.

## 2. Start

```bash
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser   # first administrator
```

Services: `db` (PostgreSQL 16), `redis`, `backend` (gunicorn; runs migrations and `collectstatic` on start), `worker` and `beat` (Celery: nightly pruning of old system logs and expired refresh tokens), `web` (Nginx serving the built SPA, proxying `/api/` and `/django-admin/`), `backup`.

## 3. TLS

The stack listens on plain HTTP (`WEB_PORT`). Terminate TLS in front of it (a load balancer, Caddy, Traefik, Cloudflare...) and forward `X-Forwarded-Proto: https`. With `SECURE_SSL_REDIRECT=true` (default in production) Django redirects HTTP to HTTPS and enables HSTS and secure cookies. Set `SECURE_SSL_REDIRECT=false` only for a local HTTP test.

## 4. Private files

Uploaded images, documents and avatars live in the `media` volume. Nginx deliberately does **not** serve `/media`; the API returns signed 15-minute links and streams the file after verifying the signature. Do not add a public `/media` location.

## 5. Backups and restore

The `backup` service writes `pg_dump -Fc` files to the `backups` volume daily and removes those older than 14 days. Also back up the `media` volume (uploaded files) with your usual volume snapshot tool, and copy both off the host.

```bash
# list
docker compose run --rm --entrypoint ls backup /backups
# restore into an empty database
docker compose cp backup:/backups/mebelchi-YYYY-MM-DD-HHMM.dump ./restore.dump   # or from the volume
docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < restore.dump
```

Test a restore before you need it.

## 6. Upgrades

```bash
git pull && docker compose up -d --build   # migrations run automatically on backend start
```

## 7. Operations notes

- Scale the API by raising gunicorn `--workers` in `backend/Dockerfile` or running more `backend` replicas behind Nginx. Throttle counters use the Redis cache, so they are shared between workers when `REDIS_URL` is set.
- Plan limits and prices are rows in the `Plan` table (editable in `/django-admin/` or the Administration page via subscriptions). Feature flags (`registration`, `chat`, `optimizer`, `exports`, `interior_designer`) are managed in Administration → Features. Only `registration` is enforced server-side today; the others are exposed to the client for gating.
- Server errors (5xx) are stored in `SystemLog` and shown in Administration → Logs. Add an external monitor for uptime.
- Payments: no gateway is integrated. Confirm incoming payments in Administration → Billing to activate plans.
- Security checks: `docker compose exec backend python manage.py check --deploy`.
