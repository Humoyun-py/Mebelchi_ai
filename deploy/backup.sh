#!/bin/sh
# Daily PostgreSQL backup (custom format) with 14-day retention. Runs inside the `backup` compose service.
set -eu
mkdir -p /backups
while true; do
  f="/backups/mebelchi-$(date +%F-%H%M).dump"
  if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$f.tmp"; then
    mv "$f.tmp" "$f"; echo "backup ok: $f"
  else
    rm -f "$f.tmp"; echo "backup FAILED" >&2
  fi
  find /backups -name 'mebelchi-*.dump' -mtime +14 -delete
  sleep 86400
done
