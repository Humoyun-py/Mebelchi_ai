from django.test import TestCase

from apps.core.tests.helpers import CAB, client_for, make_user
from apps.subscriptions.models import Plan, Subscription


class ProjectTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_crud_and_activity(self):
        r = self.ca.post("/api/v1/projects/", {"name": "Wardrobe", "category": "wardrobe", "width": 1000, "height": 2200, "depth": 580}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        pid = r.data["id"]
        self.assertEqual(self.ca.patch(f"/api/v1/projects/{pid}/", {"name": "Wardrobe 2", "description": "x"}, format="json").data["name"], "Wardrobe 2")
        self.assertEqual(len(self.ca.get(f"/api/v1/projects/{pid}/activity/").data), 2)
        self.assertEqual(self.ca.delete(f"/api/v1/projects/{pid}/").status_code, 204)

    def test_isolation_between_users(self):
        pid = self.ca.post("/api/v1/projects/", {"name": "Private"}, format="json").data["id"]
        self.assertEqual(self.cb.get(f"/api/v1/projects/{pid}/").status_code, 404)
        self.assertEqual(self.cb.patch(f"/api/v1/projects/{pid}/", {"name": "hacked"}, format="json").status_code, 404)
        self.assertEqual(self.cb.delete(f"/api/v1/projects/{pid}/").status_code, 404)
        self.assertEqual(self.cb.post(f"/api/v1/projects/{pid}/duplicate/").status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/projects/").data["count"], 0)

    def test_cannot_attach_foreign_objects(self):
        fid = self.cb.post("/api/v1/folders/", {"name": "B folder"}, format="json").data["id"]
        self.assertEqual(self.ca.post("/api/v1/projects/", {"name": "x", "folder": fid}, format="json").status_code, 400)
        pid = self.cb.post("/api/v1/projects/", {"name": "B project"}, format="json").data["id"]
        self.assertEqual(self.ca.post("/api/v1/calculations/material/", dict(CAB, save=True, project=pid), format="json").status_code, 400)
        self.assertEqual(self.ca.post("/api/v1/cutting-lists/from-calculation/", dict(CAB, project=pid), format="json").status_code, 400)
        self.assertEqual(self.ca.post("/api/v1/designs/", {"name": "d", "project": pid, "config": {}}, format="json").status_code, 400)

    def test_duplicate_archive_pin(self):
        pid = self.ca.post("/api/v1/projects/", {"name": "Orig"}, format="json").data["id"]
        self.ca.post("/api/v1/calculations/material/", dict(CAB, save=True, project=pid), format="json")
        self.ca.post("/api/v1/cutting-lists/from-calculation/", dict(CAB, project=pid), format="json")
        d = self.ca.post(f"/api/v1/projects/{pid}/duplicate/")
        self.assertEqual(d.status_code, 201)
        self.assertEqual(d.data["counts"]["calculations"], 1)
        self.assertEqual(d.data["counts"]["cutting_lists"], 1)
        self.assertTrue(self.ca.post(f"/api/v1/projects/{pid}/pin/").data["pinned"])
        self.assertEqual(self.ca.post(f"/api/v1/projects/{pid}/archive/").data["status"], "archived")
        ids = [p["id"] for p in self.ca.get("/api/v1/projects/").data["results"]]
        self.assertNotIn(pid, ids)
        self.assertEqual(self.ca.get("/api/v1/projects/?status=archived").data["count"], 1)

    def test_validation(self):
        self.assertEqual(self.ca.post("/api/v1/projects/", {"name": ""}, format="json").status_code, 400)
        self.assertEqual(self.ca.post("/api/v1/projects/", {"name": "x", "width": 99999}, format="json").status_code, 400)

    def test_plan_project_limit(self):
        for i in range(5):
            self.assertEqual(self.ca.post("/api/v1/projects/", {"name": f"p{i}"}, format="json").status_code, 201)
        self.assertEqual(self.ca.post("/api/v1/projects/", {"name": "p6"}, format="json").status_code, 403)
        Subscription.objects.filter(user=self.a).update(plan=Plan.objects.get(slug="professional"))
        self.ca = client_for(type(self.a).objects.get(pk=self.a.pk))  # fresh instance, as on a real request
        self.assertEqual(self.ca.post("/api/v1/projects/", {"name": "p6"}, format="json").status_code, 201)
