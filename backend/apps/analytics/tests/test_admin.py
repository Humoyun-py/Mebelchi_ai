from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.subscriptions.models import Payment, Plan


class AdminApiTests(TestCase):
    def setUp(self):
        self.user = make_user("u@x.com")
        self.admin = make_user("admin@x.com", is_staff=True, is_superuser=True)
        self.cu, self.ca = client_for(self.user), client_for(self.admin)

    def test_non_admin_forbidden_everywhere(self):
        for path in ("stats/", "users/", "projects/", "subscriptions/", "payments/", "logs/", "features/", "storage/"):
            self.assertEqual(self.cu.get(f"/api/v1/admin-api/{path}").status_code, 403, path)
        self.assertEqual(self.cu.post("/api/v1/admin-api/broadcast/", {"title": "x"}, format="json").status_code, 403)
        self.assertEqual(self.cu.patch(f"/api/v1/admin-api/users/{self.user.id}/", {"is_staff": True}, format="json").status_code, 403)

    def test_admin_sees_data(self):
        s = self.ca.get("/api/v1/admin-api/stats/")
        self.assertEqual(s.status_code, 200)
        self.assertEqual(s.data["users"]["total"], 2)
        self.assertEqual(self.ca.get("/api/v1/admin-api/users/?search=u@x").data["count"], 1)

    def test_admin_cannot_lock_self_out(self):
        r = self.ca.patch(f"/api/v1/admin-api/users/{self.admin.id}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.ca.patch(f"/api/v1/admin-api/users/{self.user.id}/", {"is_active": False}, format="json").status_code, 200)

    def test_payment_confirmation_activates_plan(self):
        r = self.cu.post("/api/v1/subscriptions/upgrade/", {"plan": "starter"}, format="json")
        self.assertFalse(r.data["activated"])
        self.assertEqual(self.cu.get("/api/v1/subscriptions/me/").data["plan"]["slug"], "free")
        pid = Payment.objects.get().id
        self.assertEqual(self.cu.post(f"/api/v1/admin-api/payments/{pid}/confirm/").status_code, 403)
        self.assertEqual(self.ca.post(f"/api/v1/admin-api/payments/{pid}/confirm/").status_code, 200)
        self.assertEqual(self.ca.post(f"/api/v1/admin-api/payments/{pid}/confirm/").status_code, 400)
        cu = client_for(type(self.user).objects.get(pk=self.user.pk))
        self.assertEqual(cu.get("/api/v1/subscriptions/me/").data["plan"]["slug"], "starter")
        self.assertEqual(cu.get("/api/v1/notifications/unread-count/").data["count"], 1)

    def test_plans_public_and_upgrade_unknown(self):
        from rest_framework.test import APIClient
        self.assertEqual(len(APIClient().get("/api/v1/subscriptions/plans/").data), 4)
        self.assertEqual(self.cu.post("/api/v1/subscriptions/upgrade/", {"plan": "nope"}, format="json").status_code, 404)

    def test_broadcast_and_features(self):
        self.assertEqual(self.ca.post("/api/v1/admin-api/broadcast/", {"title": "Maintenance", "body": "Sunday"}, format="json").data["sent"], 2)
        self.assertEqual(self.cu.get("/api/v1/notifications/").data["count"], 1)
        n = self.cu.get("/api/v1/notifications/").data["results"][0]["id"]
        self.assertTrue(self.cu.post(f"/api/v1/notifications/{n}/read/").data["read"])
        self.assertEqual(self.cu.post("/api/v1/notifications/read-all/").data["updated"], 0)
        self.assertIn("optimizer", self.cu.get("/api/v1/analytics/features/").data)

    def test_notification_isolation(self):
        self.ca.post("/api/v1/admin-api/broadcast/", {"title": "T"}, format="json")
        nid = self.cu.get("/api/v1/notifications/").data["results"][0]["id"]
        other = client_for(make_user("o@x.com"))
        self.assertEqual(other.post(f"/api/v1/notifications/{nid}/read/").status_code, 404)

    def test_materials_system_readonly(self):
        sys_id = self.cu.get("/api/v1/materials/").data[0]["id"]
        self.assertEqual(self.cu.patch(f"/api/v1/materials/{sys_id}/", {"name": "x"}, format="json").status_code, 403)
        self.assertEqual(self.cu.delete(f"/api/v1/materials/{sys_id}/").status_code, 403)
        mine = self.cu.post("/api/v1/materials/", {"name": "Mine", "kind": "MDF", "thickness": "18.0"}, format="json")
        self.assertEqual(mine.status_code, 201, mine.data)
        self.assertFalse(mine.data["is_system"])
        other = client_for(make_user("o@x.com"))
        self.assertNotIn(mine.data["id"], [m["id"] for m in other.get("/api/v1/materials/").data])
        self.assertEqual(other.delete(f"/api/v1/materials/{mine.data['id']}/").status_code, 404)

    def test_templates_designs(self):
        t = self.cu.get("/api/v1/furniture/templates/?category=kitchen").data
        self.assertGreater(len(t), 0)
        d = self.cu.post("/api/v1/designs/", {"name": "Kitchen", "kind": "interior", "config": {"style": "modern"}}, format="json")
        self.assertEqual(d.status_code, 201)
        self.assertEqual(client_for(make_user("o@x.com")).get(f"/api/v1/designs/{d.data['id']}/").status_code, 404)
        self.assertEqual(self.cu.post("/api/v1/designs/", {"name": "x", "config": "notdict"}, format="json").status_code, 400)
