from django.test import TestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user


class RoleSelectionTests(TestCase):
    def setUp(self):
        self.user = make_user("new@x.com", role="homeowner")
        self.client_api = client_for(self.user)

    def test_user_can_pick_maker_or_homeowner(self):
        for role in ("maker", "homeowner"):
            r = self.client_api.post("/api/v1/users/me/role/", {"role": role}, format="json")
            self.assertEqual(r.status_code, 200, role)

    def test_user_cannot_self_assign_workshop(self):
        r = self.client_api.post("/api/v1/users/me/role/", {"role": "workshop"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.role, "workshop")

    def test_admin_can_assign_workshop_and_it_is_audited(self):
        admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        r = client_for(admin).patch(f"/api/v1/admin-api/users/{self.user.id}/", {"role": "workshop"}, format="json")
        self.assertEqual(r.status_code, 200)
        entry = AuditLog.objects.get(event="user.role_changed")
        self.assertEqual(entry.actor_id, admin.id)
        self.assertEqual(entry.changes, {"role": ["homeowner", "workshop"]})

    def test_unchanged_role_writes_no_audit_row(self):
        admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        client_for(admin).patch(f"/api/v1/admin-api/users/{self.user.id}/", {"role": "homeowner"}, format="json")
        self.assertFalse(AuditLog.objects.filter(event="user.role_changed").exists())
