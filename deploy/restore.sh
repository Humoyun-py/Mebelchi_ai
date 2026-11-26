#!/bin/sh
# Restore a MEBELCHI AI backup into a SEPARATE database (and optionally a separate media directory) and verify the result.
# It never touches the production database unless you say so twice.
#
#   restore.sh --db-file mebelchi-<stamp>.dump --target-db mebelchi_restore_test [--media-file mebelchi-<stamp>.media.tar.gz --media-dir /tmp/media_restore]
#
# Connection comes from the usual libpq variables (PGHOST, PGPORT, PGUSER, PGPASSWORD) or POSTGRES_HOST/PORT/USER/PASSWORD.
# Options:
#   --force                    restore into a non-empty database / media directory (drops what is there)
#   --allow-production-target  required when --target-db equals $POSTGRES_DB (the live database)
# A <stamp>.sha256 file next to the dump is verified first when it exists.
set -eu

DB_FILE=""; MEDIA_FILE=""; TARGET=""; MEDIA_DIR=""; FORCE=0; PROD_OK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --db-file) DB_FILE="$2"; shift 2 ;;
    --media-file) MEDIA_FILE="$2"; shift 2 ;;
    --target-db) TARGET="$2"; shift 2 ;;
    --media-dir) MEDIA_DIR="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --allow-production-target) PROD_OK=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[ -n "$DB_FILE" ] && [ -n "$TARGET" ] || { echo "usage: restore.sh --db-file FILE --target-db NAME [--media-file FILE --media-dir DIR] [--force]" >&2; exit 2; }
[ -f "$DB_FILE" ] || { echo "restore: $DB_FILE not found" >&2; exit 2; }
[ -z "$MEDIA_FILE" ] || [ -n "$MEDIA_DIR" ] || { echo "restore: --media-file needs --media-dir" >&2; exit 2; }

export PGHOST="${PGHOST:-${POSTGRES_HOST:-localhost}}" PGPORT="${PGPORT:-${POSTGRES_PORT:-5432}}"
export PGUSER="${PGUSER:-${POSTGRES_USER:-mebelchi}}" PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"

if [ "$TARGET" = "${POSTGRES_DB:-}" ] && [ "$PROD_OK" != 1 ]; then
  echo "restore: refusing to restore into the live database '$TARGET'. Use another --target-db, or add --allow-production-target (and --force)." >&2
  exit 3
fi

echo "restore: verifying files"
dir="$(dirname "$DB_FILE")"; sha="${DB_FILE%.dump}.sha256"
if [ -f "$sha" ]; then
  ( cd "$dir" && sha256sum -c "$(basename "$sha")" ) || { echo "restore: CHECKSUM MISMATCH, backup is damaged" >&2; exit 4; }
else
  echo "restore: no .sha256 next to the dump, skipping checksum"
fi
pg_restore --list "$DB_FILE" > /dev/null || { echo "restore: dump is not readable" >&2; exit 4; }

exists="$(psql -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$TARGET'")"
if [ -z "$exists" ]; then
  createdb "$TARGET"; echo "restore: created database $TARGET"
else
  n="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
  if [ "$n" != 0 ] && [ "$FORCE" != 1 ]; then
    echo "restore: database '$TARGET' already has $n tables; use --force to overwrite it" >&2; exit 3
  fi
fi

echo "restore: restoring database into $TARGET"
pg_restore --no-owner --no-privileges --clean --if-exists --exit-on-error -d "$TARGET" "$DB_FILE"

tables="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
migrations="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM django_migrations" 2>/dev/null || echo 0)"
users="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM users_user" 2>/dev/null || echo n/a)"
audit="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM audit_auditlog" 2>/dev/null || echo n/a)"
trigger="$(psql -d "$TARGET" -Atc "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'audit_auditlog_no_%'")"
[ "$tables" -gt 0 ] && [ "$migrations" -gt 0 ] || { echo "restore: restored database looks empty or has no django_migrations table" >&2; exit 5; }
echo "restore: database ok  tables=$tables migrations=$migrations users=$users audit_rows=$audit audit_triggers=$trigger"

if [ -n "$MEDIA_FILE" ]; then
  [ -f "$MEDIA_FILE" ] || { echo "restore: $MEDIA_FILE not found" >&2; exit 2; }
  mkdir -p "$MEDIA_DIR"
  if [ -n "$(ls -A "$MEDIA_DIR" 2>/dev/null)" ] && [ "$FORCE" != 1 ]; then
    echo "restore: $MEDIA_DIR is not empty; use --force" >&2; exit 3
  fi
  tar -xzf "$MEDIA_FILE" -C "$MEDIA_DIR"
  expected="$(tar -tzf "$MEDIA_FILE" | grep -vc '/$' || true)"
  restored="$(find "$MEDIA_DIR" -type f | wc -l)"
  [ "$expected" = "$restored" ] || { echo "restore: media mismatch: archive has $expected files, restored $restored" >&2; exit 5; }
  echo "restore: media ok  files=$restored"
fi
echo "restore: DONE"
