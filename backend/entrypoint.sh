#!/bin/sh
set -e
# Migrations and collectstatic are NOT run here any more. They belong to the one-shot `release` service (backend/release.sh), which
# demands a verified backup before it changes an existing database. A backend that merely restarts must never touch the schema.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "entrypoint: RUN_MIGRATIONS is no longer supported and is ignored; use the release step (docs/DEPLOYMENT.md)." >&2
fi
exec "$@"
