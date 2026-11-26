# Production runbook (Phase 4.10)

Everything here is a procedure to be run by an operator after approval. Nothing in it has been run against a production database.
Status of what was rehearsed on throwaway databases is stated per section.

## 1. Migration rehearsal on a copy of the real database

Run on a machine that is **not** production, with its own PostgreSQL 16 (never the live server).

```bash
# 1. dump the live database from the live host (read-only operation)
pg_dump -Fc -h LIVE_HOST -U mebelchi mebelchi > live.dump && sha256sum live.dump > live.sha256
# 2. restore into a separate database on the rehearsal server
sh deploy/restore.sh --db-file live.dump --target-db mebelchi_rehearsal      # prints table/migration/user/audit counts and audit trigger count
# 3. record row counts of the important tables BEFORE
psql -d mebelchi_rehearsal -Atc "select 'users',count(*) from users_user union all select 'workshops',count(*) from workshops_workshop \
  union all select 'orders',count(*) from workshops_order union all select 'audit',count(*) from audit_auditlog" > before.txt
# 4. migrate with the release code that will be deployed (same image as production: python:3.12-slim)
POSTGRES_DB=mebelchi_rehearsal ... python manage.py showmigrations --plan | grep '\[ \]'     # what will run
POSTGRES_DB=mebelchi_rehearsal ... python manage.py migrate --noinput
# 5. the same counts AFTER must match (migrations in this release only add a column and a status choice)
#    then: manage.py check, manage.py test is NOT run here (it creates its own test database)
```

Pass criteria: no migration error; `before.txt` equals the counts after; `audit_auditlog` row count unchanged; the two audit triggers still exist
(`select tgname from pg_trigger where tgname like 'audit_auditlog_no_%'` returns 2 rows); a sample of workshops still has the same `status`.

Rehearsed so far (synthetic data only): a database at migration `workshops.0002` was backed up, then `release` refused with no or a stale backup,
and applied `0003_workshop_review_note_and_rejected` once a verified backup existed. `0003` adds one `varchar(500) NOT NULL DEFAULT ''` column
(metadata-only on PostgreSQL 11+, no table rewrite) and changes `choices` (no SQL). **Not yet rehearsed on a copy of real data.**

### Recovery if a production migration fails
1. `release` exits non-zero; backend, worker and beat are not (re)started, the old containers keep serving. Do not retry blindly.
2. Read the `[release]` log lines: which migration, which error. PostgreSQL migrations run in transactions, so a failed one leaves nothing half-applied;
   check with `showmigrations`.
3. If the schema is consistent: fix the cause and run `docker compose run --rm release` again (it demands a backup no older than `BACKUP_MAX_AGE_MINUTES`).
4. If the data or schema is damaged: stop `backend worker beat`, then
   `deploy/restore.sh --db-file <the backup the release step verified> --target-db mebelchi_recovered` and check it; to go live from it either
   point `POSTGRES_DB` at it, or restore into the live name with `--allow-production-target --force` while the application is stopped.
   Roll the application back to the previous image first (`git checkout <previous tag> && docker compose build`), because new code expects the new schema.
5. Record the incident; the audit log is inside the restored dump, so history up to the backup is intact.

## 2. Audit database roles (`deploy/sql/audit_roles.sql`): review

| Topic | Finding |
|---|---|
| Role inheritance | The application role is **not** a member of the owner role (membership would inherit ownership and allow `DROP TRIGGER`; found and fixed while testing). The script `REVOKE`s any earlier membership. |
| Table ownership | `audit_auditlog` and its sequence move to NOLOGIN `mebelchi_audit_owner`. App role keeps `SELECT, INSERT` + sequence `USAGE, SELECT`. |
| Schema ownership | The schema owner can drop any table in it, so `public` also moves to `mebelchi_audit_owner`; the app role gets `USAGE, CREATE` (it still creates and alters its own tables). |
| Trigger protection | Trigger from migration 0004 blocks UPDATE/DELETE/TRUNCATE for everyone; ownership split additionally stops the app role dropping it. A superuser or the owner role still can: by design, that is the DBA path. |
| Migration compatibility | Ordinary migrations as the app role keep working (tested: ALTER of other tables, CREATE TABLE). A future migration touching `audit_auditlog` fails for the app role: run that one release as a superuser. Fresh installs: run `migrate` first, then the script. |
| Archiver role | `mebelchi_audit_archiver`: `SELECT` on the audit table only (tested: INSERT and reading other tables are denied). |
| Cluster-wide effects | Roles are cluster-global; the schema/table changes affect only the database the script runs in. Choose a strong archiver password and pass it with `-v archiver_password="'...'"` (quotes included). |

### Exact steps (documented, not yet applied anywhere real)
```bash
# take and verify a backup first
docker compose run --rm backup once
# as a PostgreSQL superuser, on the live database, once
psql -U postgres -d "$POSTGRES_DB" -v app_role="$POSTGRES_USER" -v archiver_password="'STRONG-PASSWORD'" -f deploy/sql/audit_roles.sql
# then in .env
#   AUDIT_ARCHIVER_USER=mebelchi_audit_archiver
#   AUDIT_ARCHIVER_PASSWORD=STRONG-PASSWORD
# verify as the app role: UPDATE / DELETE / TRUNCATE / DROP TRIGGER / ALTER TABLE on audit_auditlog must all fail; INSERT and SELECT must work
docker compose up -d && docker compose exec backend python manage.py audit_archive --report
```
Undo (as superuser): `ALTER TABLE audit_auditlog OWNER TO <app role>; ALTER SEQUENCE audit_auditlog_id_seq OWNER TO <app role>; ALTER SCHEMA public OWNER TO pg_database_owner;`

## 3. Open decisions (nothing below is guessed in the code)
- TLS termination point and the proxy's address range: see `DEPLOYMENT.md` section 3 (nginx stays unchanged until answered).
- Remote backup storage: `BACKUP_OFFSITE_DIR` / `BACKUP_POST_HOOK` stay empty until a real target is chosen.
- Real-data rehearsal: needs a dump of the live database delivered to a rehearsal host.
