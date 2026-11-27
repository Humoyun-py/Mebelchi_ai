#!/bin/sh
# Render (free tier) start command: free plans have no pre-deploy step, so the schema is applied here, then gunicorn starts.
# Use only for the free demo deployment. docker-compose/production keep using release.sh with its backup rule.
set -eu
python manage.py migrate --noinput
python manage.py collectstatic --noinput > /dev/null
python manage.py ensure_admin
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2 --timeout 60 --access-logfile -
