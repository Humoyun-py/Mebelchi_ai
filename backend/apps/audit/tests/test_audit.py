from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.test.utils import override_settings
from django.test import skipUnlessDBFeature

from apps.audit import services
from apps.audit.models import AppendOnlyError, AuditLog
from apps.core.tests.helpers import make_user


class AppendOnlyModelTests(TestCase):
    def setUp(self):
        self.actor = make_user("actor@x.com", is_staff=True)
        self.entry = services.record("test.action", actor=self.actor, target_type="thing", target_id=7,
                                     changes={"a": [1, 2]})

    def test_record_snapshots_actor_and_changes(self):
        self.assertEqual(self.entry.actor_id, self.actor.id)
        self.assertEqual(self.entry.actor_email, "actor@x.com")
        self.assertEqual(self.entry.target_id, "7")
        self.assertEqual(self.entry.changes, {"a": [1, 2]})

    def test_existing_row_cannot_be_saved_again(self):
        self.entry.action = "changed"
        with self.assertRaises(AppendOnlyError):
            self.entry.save()
        self.assertEqual(AuditLog.objects.get(pk=self.entry.pk).action, "test.action")

    def test_row_cannot_be_deleted_by_instance_or_queryset(self):
        with self.assertRaises(AppendOnlyError):
            self.entry.delete()
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.filter(pk=self.entry.pk).delete()

    def test_bulk_update_is_refused(self):
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.update(action="x")

    def test_deleting_the_actor_keeps_history(self):
        self.actor.delete()
        self.assertTrue(AuditLog.objects.filter(pk=self.entry.pk).exists())
        self.assertEqual(AuditLog.objects.get(pk=self.entry.pk).actor_email, "actor@x.com")


class AppendOnlyDatabaseTests(TestCase):
    @skipUnlessDBFeature("supports_transactions")
    def test_postgres_trigger_blocks_raw_sql_mutation(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL trigger test; SQLite is protected at the model layer only.")
        services.record("test.raw", target_type="thing", target_id=1)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute("UPDATE audit_auditlog SET action = 'tampered'")
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                with connection.cursor() as cur:
                    cur.execute("DELETE FROM audit_auditlog")
