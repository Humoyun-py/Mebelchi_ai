from django.test import TestCase

from apps.audit.models import AuditLog
from apps.core.tests.helpers import client_for, make_user
from apps.workshops.models import Workshop

PROFILE = {"kind": "workshop", "name": "Usta Ali Mebel", "city": "Toshkent"}


class WorkshopMeAccessTests(TestCase):
    def test_only_workshop_role_can_use_the_endpoint(self):
        for role in ("homeowner", "maker"):
            self.assertEqual(client_for(make_user(f"{role}@x.com", role=role)).get("/api/v1/workshops/me/").status_code, 403, role)
        staff = make_user("staff@x.com", role="homeowner", is_staff=True, is_superuser=True)
        self.assertEqual(client_for(staff).get("/api/v1/workshops/me/").status_code, 403)

    def test_anonymous_is_unauthorized(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get("/api/v1/workshops/me/").status_code, 401)


class WorkshopProfileTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@x.com", role="workshop")
        self.api = client_for(self.owner)

    def test_profile_does_not_exist_until_created(self):
        self.assertEqual(self.api.get("/api/v1/workshops/me/").status_code, 404)

    def test_create_starts_pending_and_is_audited(self):
        r = self.api.post("/api/v1/workshops/me/", PROFILE, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "pending")
        self.assertTrue(AuditLog.objects.filter(action="workshop.profile_created", actor_id=self.owner.id).exists())

    def test_second_create_is_refused(self):
        self.api.post("/api/v1/workshops/me/", PROFILE, format="json")
        self.assertEqual(self.api.post("/api/v1/workshops/me/", PROFILE, format="json").status_code, 400)

    def test_status_cannot_be_set_by_the_owner(self):
        self.api.post("/api/v1/workshops/me/", PROFILE, format="json")
        r = self.api.patch("/api/v1/workshops/me/", {"status": "approved", "name": "Yangi nom"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "pending")
        self.assertEqual(r.data["name"], "Yangi nom")

    def test_each_workshop_sees_only_its_own_profile(self):
        self.api.post("/api/v1/workshops/me/", PROFILE, format="json")
        other = make_user("other@x.com", role="workshop")
        client_for(other).post("/api/v1/workshops/me/", {**PROFILE, "name": "Boshqa sex"}, format="json")
        self.assertEqual(self.api.get("/api/v1/workshops/me/").data["name"], "Usta Ali Mebel")
        self.assertEqual(client_for(other).get("/api/v1/workshops/me/").data["name"], "Boshqa sex")


class WorkshopAdminTests(TestCase):
    def setUp(self):
        self.owner = make_user("owner@x.com", role="workshop")
        client_for(self.owner).post("/api/v1/workshops/me/", PROFILE, format="json")
        self.profile = Workshop.objects.get(owner=self.owner)
        self.admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        self.admin_api = client_for(self.admin)

    def test_non_admin_cannot_review_or_approve(self):
        maker = make_user("maker@x.com", role="maker")
        self.assertEqual(client_for(maker).get("/api/v1/admin-api/workshops/").status_code, 403)
        self.assertEqual(client_for(maker).post(f"/api/v1/admin-api/workshops/{self.profile.id}/approve/").status_code, 403)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.status, "pending")

    def test_approve_then_suspend_with_audit_trail(self):
        r = self.admin_api.post(f"/api/v1/admin-api/workshops/{self.profile.id}/approve/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "approved")
        self.assertEqual(self.admin_api.post(f"/api/v1/admin-api/workshops/{self.profile.id}/approve/").status_code, 400)
        r = self.admin_api.post(f"/api/v1/admin-api/workshops/{self.profile.id}/suspend/")
        self.assertEqual(r.data["status"], "suspended")
        actions = list(AuditLog.objects.filter(target_type="workshop").values_list("action", flat=True))
        self.assertEqual(sorted(actions), sorted(["workshop.profile_created", "workshop.approved", "workshop.suspended"]))

    def test_cannot_suspend_a_pending_profile(self):
        self.assertEqual(self.admin_api.post(f"/api/v1/admin-api/workshops/{self.profile.id}/suspend/").status_code, 400)

    def test_admin_list_includes_status(self):
        r = self.admin_api.get("/api/v1/admin-api/workshops/?status=pending")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
