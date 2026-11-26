#!/bin/sh
# MEBELCHI AI backup: PostgreSQL (pg_dump -Fc) + media files, verified, optionally copied off the host.
# Runs inside the `backup` compose service (postgres:16-alpine) in a loop, or once with `backup.sh once`.
#
# Every successful run produces three files in $BACKUP_DIR sharing one timestamp:
#   mebelchi-<stamp>.dump          database (custom format)
#   mebelchi-<stamp>.media.tar.gz  uploaded files (only when $MEDIA_DIR exists)
#   mebelchi-<stamp>.sha256        checksums of the two files above
# and then atomically rewrites $BACKUP_DIR/LATEST_OK, the marker that the release step (backend/release.sh) requires
# before it applies migrations. A failed run never touches LATEST_OK and writes $BACKUP_DIR/LAST_FAILURE instead.
#
# Settings (all optional except the POSTGRES_* ones):
#   BACKUP_DIR (/backups)  MEDIA_DIR (/media)  BACKUP_RETENTION_DAYS (14)  BACKUP_KEEP_MIN (3, newest sets never pruned)
#   BACKUP_INTERVAL_SECONDS (86400)  BACKUP_OFFSITE_DIR (a mounted path outside this host: NFS, rclone mount, ...)
#   BACKUP_POST_HOOK (shell command run after a good backup; sees BACKUP_DB_FILE, BACKUP_MEDIA_FILE, BACKUP_SHA_FILE)
#   BACKUP_ALERT_WEBHOOK_URL / BACKUP_ALERT_TELEGRAM_BOT_TOKEN + BACKUP_ALERT_TELEGRAM_CHAT_ID (failure alerts, opt-in; the
#   message never contains user data)
set -u

BACKUP_DIR="${BACKUP_DIR:-/backups}"
MEDIA_DIR="${MEDIA_DIR:-/media}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
KEEP_MIN="${BACKUP_KEEP_MIN:-3}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
export PGHOST="${POSTGRES_HOST:-db}" PGPORT="${POSTGRES_PORT:-5432}" PGUSER="${POSTGRES_USER:-mebelchi}"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
DB="${POSTGRES_DB:?POSTGRES_DB is required}"

case "$RETENTION_DAYS$KEEP_MIN$INTERVAL" in *[!0-9]*) echo "backup: BACKUP_RETENTION_DAYS, BACKUP_KEEP_MIN and BACKUP_INTERVAL_SECONDS must be whole numbers" >&2; exit 2 ;; esac

alert() {  # best effort, never fails the script
  msg="MEBELCHI backup FAILED: $1"
  echo "backup: $msg" >&2
  if [ -n "${BACKUP_ALERT_WEBHOOK_URL:-}" ]; then
    wget -q -T 10 -O /dev/null --header 'Content-Type: application/json' --post-data "{\"text\":\"$msg\"}" "$BACKUP_ALERT_WEBHOOK_URL" || true
  fi
  if [ -n "${BACKUP_ALERT_TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${BACKUP_ALERT_TELEGRAM_CHAT_ID:-}" ]; then
    wget -q -T 10 -O /dev/null --post-data "chat_id=$BACKUP_ALERT_TELEGRAM_CHAT_ID&text=$msg" \
      "https://api.telegram.org/bot$BACKUP_ALERT_TELEGRAM_BOT_TOKEN/sendMessage" || true
  fi
}

fail() {
  date -u +"%Y-%m-%dT%H:%M:%SZ $1" > "$BACKUP_DIR/LAST_FAILURE" 2>/dev/null || true
  alert "$1"
  return 1
}

prune() {
  # newest KEEP_MIN sets are always kept; older ones go once they are more than RETENTION_DAYS old
  for f in $(ls -1t "$BACKUP_DIR"/mebelchi-*.dump 2>/dev/null | tail -n +"$((KEEP_MIN + 1))"); do
    if [ -n "$(find "$f" -mtime +"$RETENTION_DAYS" 2>/dev/null)" ]; then
      base="${f%.dump}"
      rm -f "$f" "$base.media.tar.gz" "$base.sha256"
      echo "backup: pruned $(basename "$base")"
    fi
  done
}

run_once() {
  mkdir -p "$BACKUP_DIR" || { echo "backup: cannot create $BACKUP_DIR" >&2; return 1; }
  stamp="$(date -u +%Y-%m-%d-%H%M%S)"
  base="$BACKUP_DIR/mebelchi-$stamp"
  name="mebelchi-$stamp"

  # 1. database
  if ! pg_dump -Fc "$DB" > "$base.dump.tmp" 2> "$base.dump.err"; then
    err="$(tail -n 2 "$base.dump.err" | tr '\n"' ' _')"; rm -f "$base.dump.tmp" "$base.dump.err"
    fail "pg_dump failed: $err"; return 1
  fi
  rm -f "$base.dump.err"
  if [ ! -s "$base.dump.tmp" ] || ! pg_restore --list "$base.dump.tmp" > /dev/null 2>&1; then
    rm -f "$base.dump.tmp"; fail "database dump is empty or unreadable"; return 1
  fi
  mv "$base.dump.tmp" "$base.dump"

  # 2. media (uploaded files)
  files="$name.dump"
  if [ -d "$MEDIA_DIR" ]; then
    if ! tar -C "$MEDIA_DIR" -czf "$base.media.tar.gz.tmp" . 2>/dev/null || ! tar -tzf "$base.media.tar.gz.tmp" > /dev/null 2>&1; then
      rm -f "$base.media.tar.gz.tmp" "$base.dump"; fail "media archive failed verification"; return 1
    fi
    mv "$base.media.tar.gz.tmp" "$base.media.tar.gz"
    files="$files $name.media.tar.gz"
  else
    echo "backup: $MEDIA_DIR not mounted, media is NOT part of this backup" >&2
  fi

  # 3. checksums, then the marker
  ( cd "$BACKUP_DIR" && sha256sum $files > "$name.sha256" && sha256sum -c "$name.sha256" > /dev/null ) \
    || { fail "checksum verification failed"; return 1; }
  {
    echo "name=$name"
    echo "epoch=$(date -u +%s)"
    echo "sha=$name.sha256"
  } > "$BACKUP_DIR/LATEST_OK.tmp" && mv "$BACKUP_DIR/LATEST_OK.tmp" "$BACKUP_DIR/LATEST_OK"
  rm -f "$BACKUP_DIR/LAST_FAILURE"
  echo "backup ok: $name ($(du -h "$base.dump" | cut -f1) database$( [ -f "$base.media.tar.gz" ] && echo ", $(du -h "$base.media.tar.gz" | cut -f1) media"))"

  # 4. off-host copy and hook (a failure here is reported but does not invalidate the local backup)
  rc=0
  if [ -n "${BACKUP_OFFSITE_DIR:-}" ]; then
    if mkdir -p "$BACKUP_OFFSITE_DIR" && cp "$BACKUP_DIR/$name".* "$BACKUP_OFFSITE_DIR"/ \
       && ( cd "$BACKUP_OFFSITE_DIR" && sha256sum -c "$name.sha256" > /dev/null ); then
      echo "backup: copied and verified in $BACKUP_OFFSITE_DIR"
    else
      alert "off-site copy to BACKUP_OFFSITE_DIR failed (local backup $name is fine)"; rc=1
    fi
  fi
  if [ -n "${BACKUP_POST_HOOK:-}" ]; then
    if ! BACKUP_DB_FILE="$base.dump" BACKUP_MEDIA_FILE="$base.media.tar.gz" BACKUP_SHA_FILE="$base.sha256" sh -c "$BACKUP_POST_HOOK"; then
      alert "BACKUP_POST_HOOK failed (local backup $name is fine)"; rc=1
    fi
  fi

  prune
  return $rc
}

if [ "${1:-}" = "once" ]; then
  run_once
  exit $?
fi

while true; do
  run_once || echo "backup: run failed, will retry in ${INTERVAL}s" >&2
  sleep "$INTERVAL"
done
