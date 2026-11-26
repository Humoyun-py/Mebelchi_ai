-- Optional database roles for the append-only audit log. Run ONCE as a PostgreSQL superuser, after the first `release`:
--
--   psql -U postgres -d "$POSTGRES_DB" -v app_role="$POSTGRES_USER" -v archiver_password="'CHANGE-ME'" -f deploy/sql/audit_roles.sql
--
-- 1. mebelchi_audit_archiver: can only READ audit_auditlog. The archiving job (manage.py audit_archive, via AUDIT_ARCHIVER_USER)
--    runs with it, so a leaked archiver password cannot change history.
-- 2. Ownership split (hardening): audit_auditlog moves to a NOLOGIN owner role, and the application role keeps only SELECT and
--    INSERT. Afterwards the application role cannot UPDATE, DELETE, TRUNCATE the table or DROP its triggers, even with raw SQL.
--
-- Consequence of 2: a *future Django migration that alters audit_auditlog* cannot run as the application role. Run that one release
-- with a superuser (or the table owner) and nobody else: the application role is deliberately NOT a member of the owner role, because
-- membership would let a compromised application drop the trigger again (tested).
-- Idempotent: safe to run again.
\set ON_ERROR_STOP on

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mebelchi_audit_owner') THEN CREATE ROLE mebelchi_audit_owner NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mebelchi_audit_archiver') THEN CREATE ROLE mebelchi_audit_archiver LOGIN; END IF;
END $$;
ALTER ROLE mebelchi_audit_archiver PASSWORD :archiver_password;
REVOKE mebelchi_audit_owner FROM :"app_role";      -- no membership, no inherited ownership (a no-op the first time; fixes older runs)

-- The owner of a schema may drop any table in it, and the database owner owns `public` by default (PostgreSQL 15+). Give the schema
-- to the audit owner as well and hand the application role the two rights it needs (look up objects, create its own tables).
ALTER SCHEMA public OWNER TO mebelchi_audit_owner;
GRANT USAGE, CREATE ON SCHEMA public TO :"app_role";

ALTER TABLE audit_auditlog OWNER TO mebelchi_audit_owner;
ALTER SEQUENCE audit_auditlog_id_seq OWNER TO mebelchi_audit_owner;
REVOKE ALL ON audit_auditlog FROM PUBLIC;
GRANT SELECT, INSERT ON audit_auditlog TO :"app_role";
GRANT USAGE, SELECT ON SEQUENCE audit_auditlog_id_seq TO :"app_role";

SELECT current_database() AS db \gset
GRANT CONNECT ON DATABASE :"db" TO mebelchi_audit_archiver;
GRANT USAGE ON SCHEMA public TO mebelchi_audit_archiver;
GRANT SELECT ON audit_auditlog TO mebelchi_audit_archiver;
