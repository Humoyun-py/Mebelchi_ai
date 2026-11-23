from django.db import migrations

FORWARD_PG = """
CREATE OR REPLACE FUNCTION audit_auditlog_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditlog is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_auditlog_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_auditlog_block_mutation();

CREATE TRIGGER audit_auditlog_no_truncate
    BEFORE TRUNCATE ON audit_auditlog
    FOR EACH STATEMENT EXECUTE FUNCTION audit_auditlog_block_mutation();
"""

REVERSE_PG = """
DROP TRIGGER IF EXISTS audit_auditlog_no_truncate ON audit_auditlog;
DROP TRIGGER IF EXISTS audit_auditlog_no_update_delete ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_auditlog_block_mutation();
"""


def apply_triggers(apps, schema_editor):
    # SQLite has no trigger-level enforcement here; the model layer blocks mutation there (documented).
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD_PG)


def remove_triggers(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE_PG)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]

    operations = [migrations.RunPython(apply_triggers, remove_triggers)]
