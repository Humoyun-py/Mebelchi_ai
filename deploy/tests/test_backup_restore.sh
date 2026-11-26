#!/bin/sh
# End-to-end test of deploy/backup.sh and deploy/restore.sh against a THROWAWAY PostgreSQL.
# Needs POSTGRES_HOST/PORT/USER/PASSWORD/DB for a database it may write to (a probe table is created and dropped) and the
# PostgreSQL 16 client tools on PATH. It refuses to run unless POSTGRES_DB looks like a test database.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
: "${POSTGRES_DB:?}"
case "$POSTGRES_DB" in *test*|*p4*|*ci*|*tmp*) ;; *) echo "refusing: POSTGRES_DB='$POSTGRES_DB' does not look like a test database" >&2; exit 2 ;; esac
export PGHOST="${POSTGRES_HOST:-localhost}" PGPORT="${POSTGRES_PORT:-5432}" PGUSER="${POSTGRES_USER:-mebelchi}" PGPASSWORD="${POSTGRES_PASSWORD:-}"

T="$(mktemp -d)"; PASS=0; FAILED=0
RDB="restore_check_$$"
cleanup() { dropdb --if-exists "$RDB" 2>/dev/null; psql -d "$POSTGRES_DB" -qAtc "DROP TABLE IF EXISTS backup_probe" 2>/dev/null; rm -rf "$T"; }
trap cleanup EXIT
ok()  { PASS=$((PASS + 1)); echo "  PASS  $1"; }
bad() { FAILED=$((FAILED + 1)); echo "  FAIL  $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

mkdir -p "$T/media/designs" "$T/backups"
printf 'sofa-model-bytes' > "$T/media/designs/a.glb"; printf 'logo' > "$T/media/logo.png"
psql -d "$POSTGRES_DB" -qAtc "DROP TABLE IF EXISTS backup_probe; CREATE TABLE backup_probe(id serial primary key, v text); INSERT INTO backup_probe(v) SELECT 'row'||g FROM generate_series(1,250) g;" > /dev/null
export BACKUP_DIR="$T/backups" MEDIA_DIR="$T/media" BACKUP_OFFSITE_DIR="$T/offsite" BACKUP_KEEP_MIN=2 BACKUP_RETENTION_DAYS=1

echo "== backup"
sh "$HERE/backup.sh" once > "$T/b1.log" 2>&1; rc=$?
check "backup exits 0" "[ $rc = 0 ]"
check "marker LATEST_OK written" "[ -s '$T/backups/LATEST_OK' ]"
check "database dump, media archive and checksums exist" "ls '$T'/backups/mebelchi-*.dump '$T'/backups/mebelchi-*.media.tar.gz '$T'/backups/mebelchi-*.sha256 >/dev/null 2>&1"
check "off-site copy verified" "ls '$T'/offsite/mebelchi-*.dump >/dev/null 2>&1 && grep -q 'copied and verified' '$T/b1.log'"
DUMP="$(ls "$T"/backups/mebelchi-*.dump | head -1)"; MEDIA="${DUMP%.dump}.media.tar.gz"

echo "== restore into a separate database"
sh "$HERE/restore.sh" --db-file "$DUMP" --target-db "$RDB" --media-file "$MEDIA" --media-dir "$T/media_restored" > "$T/r1.log" 2>&1; rc=$?
check "restore exits 0" "[ $rc = 0 ]"
check "restored row count equals source" "[ \"\$(psql -d '$RDB' -Atc 'SELECT count(*) FROM backup_probe')\" = 250 ]"
check "media files restored byte for byte" "cmp -s '$T/media/designs/a.glb' '$T/media_restored/designs/a.glb' && cmp -s '$T/media/logo.png' '$T/media_restored/logo.png'"
check "restore refuses a non-empty database without --force" "! sh '$HERE/restore.sh' --db-file '$DUMP' --target-db '$RDB' >/dev/null 2>&1"
check "restore refuses the live database name" "! POSTGRES_DB='$POSTGRES_DB' sh '$HERE/restore.sh' --db-file '$DUMP' --target-db '$POSTGRES_DB' >/dev/null 2>&1"
check "restore refuses a non-empty media directory without --force" "! sh '$HERE/restore.sh' --db-file '$DUMP' --target-db '${RDB}_x' --media-file '$MEDIA' --media-dir '$T/media_restored' >/dev/null 2>&1"
dropdb --if-exists "${RDB}_x" 2>/dev/null

echo "== corruption is detected"
cp "$DUMP" "$T/corrupt.dump"; cp "${DUMP%.dump}.sha256" "$T/corrupt.sha256"
sed -i 's/mebelchi-[0-9-]*\.dump/corrupt.dump/' "$T/corrupt.sha256"
printf 'X' | dd of="$T/corrupt.dump" bs=1 seek=100 conv=notrunc 2>/dev/null
check "tampered dump is rejected by checksum" "! sh '$HERE/restore.sh' --db-file '$T/corrupt.dump' --target-db '${RDB}_c' >/dev/null 2>&1"
dropdb --if-exists "${RDB}_c" 2>/dev/null

echo "== failure keeps the last good marker and raises an alert"
before="$(cat "$T/backups/LATEST_OK")"
POSTGRES_DB="no_such_db_$$" sh "$HERE/backup.sh" once > "$T/b2.log" 2>&1; rc=$?
check "failed backup exits non-zero" "[ $rc != 0 ]"
check "LAST_FAILURE written" "[ -s '$T/backups/LAST_FAILURE' ]"
check "LATEST_OK untouched by the failure" "[ \"\$(cat '$T/backups/LATEST_OK')\" = \"\$before\" ]"
check "a failed run leaves no partial files" "! ls '$T'/backups/*.tmp '$T'/backups/*.err >/dev/null 2>&1"
check "alert text reaches stderr" "grep -q 'backup FAILED' '$T/b2.log'"

echo "== retention keeps the newest sets"
for i in 1 2 3 4; do sleep 1; sh "$HERE/backup.sh" once > /dev/null 2>&1; done
for f in "$T"/backups/mebelchi-*.dump; do touch -d '10 days ago' "$f"; done
sh "$HERE/backup.sh" once > "$T/b3.log" 2>&1
n="$(ls "$T"/backups/mebelchi-*.dump | wc -l)"
check "old sets are pruned but at least BACKUP_KEEP_MIN remain (have $n)" "[ $n -ge 2 ] && [ $n -le 3 ]"
check "pruned sets lose media and checksum files too" "[ \"\$(ls '$T'/backups/mebelchi-*.sha256 | wc -l)\" = $n ]"
check "the newest backup is still restorable" "dropdb --if-exists '${RDB}_n'; sh '$HERE/restore.sh' --db-file \"\$(ls -1t '$T'/backups/mebelchi-*.dump | head -1)\" --target-db '${RDB}_n' >/dev/null 2>&1"
dropdb --if-exists "${RDB}_n" 2>/dev/null

echo "== invalid settings"
BACKUP_RETENTION_DAYS=abc sh "$HERE/backup.sh" once >/dev/null 2>&1; check "non-numeric retention is rejected" "[ $? = 2 ]"

echo; echo "backup/restore: $PASS passed, $FAILED failed"
[ "$FAILED" = 0 ]
