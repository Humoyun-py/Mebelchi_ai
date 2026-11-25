from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from apps.audit import services
from apps.audit.models import AppendOnlyError, AuditLog
from apps.core.tests.helpers import make_user


class AppendOnlyModelTests(TestCase):
    def setUp(self):
        self.actor = make_user("actor@x.com", is_staff=True)
        self.entry = services.record("test.created", actor=self.actor, target_type="thing", target_id=7, changes={"a": [1, 2]})

    def test_the_older_call_style_is_understood(self):
        e = self.entry
        self.assertEqual((e.actor_id, e.actor_email, e.model, e.object_id, e.event, e.action), (self.actor.id, "actor@x.com", "thing", "7", "test.created", "create"))
        self.assertEqual(e.changes, {"a": [1, 2]})

    def test_event_names_map_to_the_right_action(self):
        for name, action in (("order.created", "create"), ("order.deleted", "delete"), ("order.status_changed", "update"), ("user.role_changed", "update")):
            self.assertEqual(services.record(name, target_type="x", target_id=1).action, action, name)
        self.assertEqual(services.record("login", model="users.user", object_id=1).action, "login")      # plain actions are kept as they are

    def test_an_existing_row_cannot_be_saved_again(self):
        self.entry.event = "changed"
        with self.assertRaises(AppendOnlyError):
            self.entry.save()
        self.assertEqual(AuditLog.objects.get(pk=self.entry.pk).event, "test.created")

    def test_rows_cannot_be_deleted_by_instance_or_queryset(self):
        with self.assertRaises(AppendOnlyError):
            self.entry.delete()
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.filter(pk=self.entry.pk).delete()
        with self.assertRaises(PermissionError):      # AppendOnlyError is a PermissionError for callers that only know the builtin
            AuditLog.objects.all().delete()

    def test_bulk_updates_are_refused(self):
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.update(event="x")
        with self.assertRaises(AppendOnlyError):
            AuditLog.objects.bulk_update([self.entry], ["event"])

    def test_deleting_the_actor_keeps_the_history_untouched(self):
        actor_id = self.actor.id
        self.actor.delete()                                  # (Django clears .id on the deleted instance)
        e = AuditLog.objects.get(pk=self.entry.pk)
        self.assertEqual((e.actor_email, e.actor_id), ("actor@x.com", actor_id))


class AppendOnlyDatabaseTests(TestCase):
    """PostgreSQL only: the trigger (migration 0004) protects the table even against raw SQL."""

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL trigger test; SQLite is protected at the model layer only.")

    def test_raw_sql_mutation_is_blocked(self):
        services.record("test.raw", target_type="thing", target_id=1)
        for sql in ("UPDATE audit_auditlog SET event = 'tampered'", "DELETE FROM audit_auditlog", "TRUNCATE audit_auditlog"):
            with self.assertRaises(DatabaseError, msg=sql):
                with transaction.atomic(), connection.cursor() as cur:
                    cur.execute(sql)

    def test_deleting_an_account_still_works_while_the_trigger_is_active(self):
        """The reason `actor` has no database constraint: SET NULL would be an UPDATE and the trigger would refuse it."""
        u = make_user("gone@x.com")
        services.record("test.thing", actor=u, target_type="thing", target_id=2)
        u.delete()
        self.assertEqual(AuditLog.objects.filter(actor_email="gone@x.com").count(), 1)
