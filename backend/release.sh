#!/bin/sh
# Release step: the ONLY place that changes the production schema. Runs as its own one-shot compose service (`release`) before the
# backend, worker and beat start; they wait for it with `depends_on: service_completed_successfully`, so a failure here stops the
# deploy and the old containers keep running.
#
# Rules
#  1. Nothing pending                         -> collectstatic only; the database is not touched.
#  2. Pending migrations on a NEW database    -> apply (there is nothing to lose).
#  3. Pending migrations on an EXISTING one   -> require a verified backup: /backups/LATEST_OK written by deploy/backup.sh no
#                                               longer than BACKUP_MAX_AGE_MINUTES ago (default 120), with matching checksums.
#                                               No backup, no migration, exit 1.
#  4. A failing migration exits non-zero; the log shows which one.
set -eu
log() { echo "[release] $*"; }

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MAX_AGE_MIN="${BACKUP_MAX_AGE_MINUTES:-120}"
case "$MAX_AGE_MIN" in ''|*[!0-9]*) log "BACKUP_MAX_AGE_MINUTES must be a whole number"; exit 2 ;; esac

log "reading migration state"
plan="$(python manage.py showmigrations --plan 2>&1)" || { log "cannot read the migration state: $(echo "$plan" | tail -n 3)"; exit 1; }
pending="$(echo "$plan" | grep -c '^\[ \]' || true)"
applied="$(echo "$plan" | grep -c '^\[X\]' || true)"
log "applied=$applied pending=$pending"

if [ "$pending" -gt 0 ]; then
  echo "$plan" | grep '^\[ \]' | sed 's/^/[release]   pending: /'
  if [ "$applied" -gt 0 ]; then
    log "existing database: checking for a verified backup in $BACKUP_DIR"
    marker="$BACKUP_DIR/LATEST_OK"
    [ -s "$marker" ] || { log "REFUSED: no backup marker ($marker). Run: docker compose run --rm backup once"; exit 1; }
    epoch="$(sed -n 's/^epoch=//p' "$marker")"; shaname="$(sed -n 's/^sha=//p' "$marker")"
    case "$epoch" in ''|*[!0-9]*) log "REFUSED: backup marker is unreadable"; exit 1 ;; esac
    age_min="$(( ($(date -u +%s) - epoch) / 60 ))"
    [ "$age_min" -le "$MAX_AGE_MIN" ] || { log "REFUSED: newest verified backup is $age_min min old (limit $MAX_AGE_MIN). Run: docker compose run --rm backup once"; exit 1; }
    ( cd "$BACKUP_DIR" && sha256sum -c "$shaname" > /dev/null 2>&1 ) || { log "REFUSED: backup files do not match their checksums"; exit 1; }
    log "backup ok: $(sed -n 's/^name=//p' "$marker") ($age_min min old, checksums match)"
  else
    log "empty database: no backup needed"
  fi
  log "applying migrations"
  python manage.py migrate --noinput || { log "MIGRATION FAILED. The deploy stops here; restore from the backup if the schema is half-applied (docs/DEPLOYMENT.md)."; exit 1; }
  log "migrations applied"
fi

python manage.py collectstatic --noinput > /dev/null
log "done"
