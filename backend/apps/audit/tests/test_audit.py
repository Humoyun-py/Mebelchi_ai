from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.audit import services
from apps.core.tests.helpers import CAB, client_for, make_user
from apps.projects.models import Project
from apps.users.models import User

API = "/api/v1/"
ADMIN = "/api/v1/admin-api/audit-logs/"


def logs(**kw):
    return AuditLog.objects.filter(**kw)


class RecordingTests(TestCase):
    def setUp(self):
        self.user = make_user("owner@x.com")
        self.c = client_for(self.user)
        AuditLog.objects.all().delete()  # forget the setup noise

    def test_create_update_delete_through_the_api(self):
        r = self.c.post(API + "projects/", {"name": "Kitchen", "category": "kitchen"}, format="json", REMOTE_ADDR="203.0.113.7")
        self.assertEqual(r.status_code, 201, r.data)
        pid = r.data["id"]
        created = logs(model="projects.project", object_id=str(pid), action="create").get()
        self.assertEqual(created.actor, self.user)
        self.assertEqual(created.actor_email, "owner@x.com")
        self.assertEqual(created.object_repr, "Kitchen")
        self.assertEqual((created.method, created.path), ("POST", "/api/v1/projects/"))
        self.assertEqual(created.ip, "203.0.113.7")

        self.assertEqual(self.c.patch(f"{API}projects/{pid}/", {"name": "Kitchen v2", "description": "south wall"}, format="json").status_code, 200)
        upd = logs(model="projects.project", object_id=str(pid), action="update").get()
        self.assertEqual(upd.changes["name"], {"old": "Kitchen", "new": "Kitchen v2"})
        self.assertEqual(upd.changes["description"], {"old": "", "new": "south wall"})
        self.assertNotIn("updated_at", upd.changes)
        self.assertEqual(upd.method, "PATCH")

        self.assertEqual(self.c.delete(f"{API}projects/{pid}/").status_code, 204)
        gone = logs(model="projects.project", object_id=str(pid), action="delete").get()
        self.assertEqual((gone.actor, gone.object_repr), (self.user, "Kitchen v2"))

    def test_a_save_that_changes_nothing_writes_nothing(self):
        p = Project.objects.create(owner=self.user, name="Same")
        n = AuditLog.objects.count()
        p.save()
        p.name = "Same"
        p.save()
        self.assertEqual(AuditLog.objects.count(), n)

    def test_failed_requests_are_not_recorded(self):
        self.assertEqual(self.c.post(API + "projects/", {"name": ""}, format="json").status_code, 400)
        self.assertEqual(AuditLog.objects.count(), 0)
        self.assertEqual(self.c.delete(API + "projects/999999/").status_code, 404)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_other_users_cannot_cause_entries_for_my_objects(self):
        p = Project.objects.create(owner=self.user, name="Mine")
        intruder = client_for(make_user("evil@x.com"))
        AuditLog.objects.all().delete()
        self.assertEqual(intruder.delete(f"{API}projects/{p.id}/").status_code, 404)
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_saved_calculation_is_recorded_without_its_payload(self):
        r = self.c.post(API + "calculations/material/", dict(CAB, save=True, name="Wardrobe"), format="json")
        entry = logs(model="calculations.calculation", object_id=str(r.data["saved_id"])).get()
        self.assertEqual((entry.action, entry.actor), ("create", self.user))

    def test_cascade_deletes_are_recorded_for_children(self):
        r = self.c.post(API + "calculations/material/", dict(CAB, save=True, project=Project.objects.create(owner=self.user, name="P").id), format="json")
        AuditLog.objects.all().delete()
        Project.objects.get(owner=self.user).delete()
        self.assertTrue(logs(model="calculations.calculation", object_id=str(r.data["saved_id"]), action="delete").exists())

    def test_cutting_list_parts_replacement_is_recorded(self):
        cl = self.c.post(API + "cutting-lists/", {"name": "L", "parts": [{"name": "A", "width": 300, "height": 600, "thickness": 18, "quantity": 1}]},
                         format="json").data
        AuditLog.objects.all().delete()
        self.c.patch(f"{API}cutting-lists/{cl['id']}/", {"parts": [{"name": "B", "width": 200, "height": 400, "thickness": 18, "quantity": 2},
                                                                    {"name": "C", "width": 100, "height": 400, "thickness": 18, "quantity": 1}]}, format="json")
        e = logs(model="cutting_lists.cuttinglist", action="update").get()
        self.assertEqual(e.changes["parts"], {"old": "1 rows", "new": "2 rows"})


class SensitiveDataTests(TestCase):
    def test_passwords_are_never_stored(self):
        u = make_user("pw@x.com")
        AuditLog.objects.all().delete()
        u.set_password("Another-Strong-1!")
        u.first_name = "Renamed"
        u.save()
        e = logs(model="users.user", action="update").get()
        self.assertEqual(e.changes["password"], {"old": "[redacted]", "new": "[redacted]"})
        self.assertEqual(e.changes["first_name"]["new"], "Renamed")
        self.assertNotIn("Another-Strong-1!", str(e.changes))
        self.assertNotIn("pbkdf2", str(e.changes))

    def test_last_login_updates_are_not_logged(self):
        u = make_user("ll@x.com")
        AuditLog.objects.all().delete()
        from django.utils import timezone
        u.last_login = timezone.now()
        u.save(update_fields=["last_login"])
        self.assertEqual(AuditLog.objects.count(), 0)

    def test_privilege_changes_are_visible(self):
        u = make_user("promote@x.com")
        AuditLog.objects.all().delete()
        u.is_staff = True
        u.save()
        self.assertEqual(logs(action="update").get().changes["is_staff"], {"old": False, "new": True})

    def test_long_values_are_truncated(self):
        u = make_user("long@x.com")
        p = Project.objects.create(owner=u, name="x")
        AuditLog.objects.all().delete()
        p.description = "y" * 5000
        p.save()
        self.assertLessEqual(len(logs(action="update").get().changes["description"]["new"]), 201)


class AuthEventTests(TestCase):
    def test_login_logout_and_password_change(self):
        u = make_user("auth@x.com")
        AuditLog.objects.all().delete()
        c = APIClient()
        r = c.post(API + "auth/login/", {"email": "auth@x.com", "password": "StrongPass!234"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(logs(action="login", actor=u).count(), 1)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        c.post(API + "users/me/password/", {"current_password": "StrongPass!234", "new_password": "Brand-New-Pass-9!"}, format="json")
        self.assertEqual(logs(action="password", actor=u).count(), 1)
        c.post(API + "auth/logout/", {"refresh": r.data["refresh"]}, format="json")
        self.assertEqual(logs(action="logout", actor=u).count(), 1)

    def test_failed_login_is_not_recorded_as_a_login(self):
        make_user("auth2@x.com")
        AuditLog.objects.all().delete()
        APIClient().post(API + "auth/login/", {"email": "auth2@x.com", "password": "wrong"}, format="json")
        self.assertFalse(logs(action="login").exists())

    def test_registration_creates_an_entry_for_the_new_account(self):
        r = APIClient().post(API + "auth/register/", {"first_name": "A", "last_name": "B", "email": "new@x.com", "password": "Sup3r-Secret-Pw!",
                                                       "confirm_password": "Sup3r-Secret-Pw!"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(logs(model="users.user", action="create", object_repr="new@x.com").exists())


class SystemAndRetentionTests(TestCase):
    def test_changes_outside_a_request_have_no_actor(self):
        u = make_user("sys@x.com")
        Project.objects.create(owner=u, name="From a script")
        e = logs(model="projects.project", action="create").get()
        self.assertIsNone(e.actor)
        self.assertEqual((e.actor_email, e.path), ("", ""))

    def test_entries_survive_deleting_the_actor(self):
        u = make_user("leaver@x.com")
        client_for(u).post(API + "projects/", {"name": "Kept"}, format="json")
        User.objects.get(pk=u.pk).delete()
        e = logs(model="projects.project", action="create").get()
        self.assertIsNone(e.actor)
        self.assertEqual(e.actor_email, "leaver@x.com")

    def test_entries_are_immutable(self):
        e = services.record("update", model="x.y", object_id=1)
        e.object_repr = "tampered"
        with self.assertRaises(PermissionError):
            e.save()
        with self.assertRaises(PermissionError):
            e.delete()
        self.assertEqual(AuditLog.objects.get(pk=e.pk).object_repr, "")

    def test_a_failing_audit_write_does_not_break_the_request(self):
        from unittest import mock
        u = make_user("resilient@x.com")
        with mock.patch("apps.audit.services.AuditLog.objects.create", side_effect=RuntimeError("db hiccup")), self.assertLogs("apps.audit.services", "ERROR"):
            r = client_for(u).post(API + "projects/", {"name": "Still works"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Project.objects.filter(name="Still works").exists())

    def test_forwarded_ip_header_is_only_trusted_when_configured(self):
        from django.test import override_settings
        u = make_user("ip@x.com")
        c = client_for(u)
        c.post(API + "projects/", {"name": "a"}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="198.51.100.9")
        self.assertEqual(logs(model="projects.project").first().ip, "10.0.0.1")
        with override_settings(AUDIT_IP_HEADER="HTTP_X_REAL_IP"):
            c.post(API + "projects/", {"name": "b"}, format="json", REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="198.51.100.9")
        self.assertEqual(logs(model="projects.project", object_repr="b").get().ip, "198.51.100.9")


class AdminApiTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@x.com", is_staff=True)
        self.user = make_user("user@x.com")
        client_for(self.user).post(API + "projects/", {"name": "Alpha"}, format="json")
        client_for(make_user("second@x.com")).post(API + "projects/", {"name": "Beta"}, format="json")

    def test_only_platform_admins_can_read(self):
        self.assertEqual(client_for().get(ADMIN).status_code, 401)
        self.assertEqual(client_for(self.user).get(ADMIN).status_code, 403)
        self.assertEqual(client_for(self.admin).get(ADMIN).status_code, 200)

    def test_it_is_read_only(self):
        c = client_for(self.admin)
        e = AuditLog.objects.first()
        self.assertEqual(c.post(ADMIN, {"action": "create"}, format="json").status_code, 405)
        self.assertEqual(c.patch(f"{ADMIN}{e.id}/", {"object_repr": "x"}, format="json").status_code, 405)
        self.assertEqual(c.delete(f"{ADMIN}{e.id}/").status_code, 405)

    def test_filters_search_and_pagination(self):
        c = client_for(self.admin)
        r = c.get(ADMIN, {"model": "projects.project", "action": "create"})
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(c.get(ADMIN, {"actor_email": "user@x.com", "model": "projects.project"}).data["count"], 1)
        self.assertEqual(c.get(ADMIN, {"search": "Beta"}).data["count"], 1)
        self.assertEqual(c.get(ADMIN, {"page_size": 1}).data["results"].__len__(), 1)
        self.assertEqual(c.get(ADMIN, {"created_after": "2999-01-01T00:00:00Z"}).data["count"], 0)
        pid = Project.objects.get(name="Alpha").id
        hist = c.get(ADMIN, {"model": "projects.project", "object_id": pid}).data
        self.assertEqual(hist["count"], 1)

    def test_newest_first_and_fields(self):
        r = client_for(self.admin).get(ADMIN).data["results"]
        self.assertEqual(r, sorted(r, key=lambda e: e["created_at"], reverse=True))
        self.assertTrue({"actor_email", "action", "model", "object_id", "object_repr", "changes", "ip", "created_at"} <= set(r[0]))

    def test_admin_actions_are_attributed_to_the_admin(self):
        AuditLog.objects.all().delete()
        c = client_for(self.admin)
        uid = self.user.id
        r = c.patch(f"{API}admin-api/users/{uid}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        e = logs(model="users.user", action="update").get()
        self.assertEqual((e.actor, e.object_id), (self.admin, str(uid)))
        self.assertEqual(e.changes["is_active"], {"old": True, "new": False})
