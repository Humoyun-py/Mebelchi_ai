#!/bin/sh
# Approved deploy: build -> database up -> fresh verified backup -> release (migrations) -> start everything.
# Stops at the first failure. Nothing in the database changes before the backup is verified, and the app containers are only
# (re)started after the release step succeeded.
#
#   deploy/deploy.sh            asks you to type DEPLOY
#   deploy/deploy.sh --yes      non-interactive (CI / runbook after approval)
#   deploy/deploy.sh --dry-run  prints the plan and validates the compose file, changes nothing
set -eu
cd "$(dirname "$0")/.."
step() { echo; echo "==> $*"; }

DRY=0; YES=0
for a in "$@"; do case "$a" in --yes) YES=1 ;; --dry-run) DRY=1 ;; *) echo "unknown option $a" >&2; exit 2 ;; esac; done

[ -f .env ] || { echo "deploy: .env is missing (cp .env.example .env and fill it in)" >&2; exit 1; }
step "validating docker-compose.yml"
docker compose config -q

if [ "$DRY" = 1 ]; then
  cat <<'PLAN'

Plan (dry run, nothing executed):
  1. docker compose build
  2. docker compose up -d db redis          (wait until db is healthy)
  3. docker compose run --rm backup once    (pg_dump + media + checksums; fails the deploy if anything is wrong)
  4. docker compose run --rm release        (refuses without that backup; migrates; collectstatic)
  5. docker compose up -d                   (backend, worker, beat, telegram-bot, web, backup)
PLAN
  exit 0
fi

if [ "$YES" != 1 ]; then
  printf 'This will back up and then migrate the PRODUCTION database. Type DEPLOY to continue: '
  read -r answer
  [ "$answer" = "DEPLOY" ] || { echo "aborted"; exit 1; }
fi

step "building images";                 docker compose build
step "starting database and redis";     docker compose up -d --wait db redis
step "verified backup";                 docker compose run --rm backup once
step "release (backup check + migrate)"; docker compose run --rm release
step "starting services";               docker compose up -d --remove-orphans
step "status";                          docker compose ps
echo; echo "deploy: finished"
