from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user


class DesignTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com"), make_user("b@example.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_crud_and_owner_isolation(self):
        r = self.ca.post("/api/v1/designs/", {"name": "Living room", "kind": "interior", "config": {"style": "modern"}}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        did = r.data["id"]
        self.assertEqual(self.ca.patch(f"/api/v1/designs/{did}/", {"name": "Lounge"}, format="json").data["name"], "Lounge")
        self.assertEqual(self.cb.get(f"/api/v1/designs/{did}/").status_code, 404)
        self.assertEqual(self.cb.delete(f"/api/v1/designs/{did}/").status_code, 404)
        self.assertEqual(self.cb.get("/api/v1/designs/").data["count"], 0)
        self.assertEqual(self.ca.delete(f"/api/v1/designs/{did}/").status_code, 204)

    def test_cannot_attach_foreign_project(self):
        pid = self.cb.post("/api/v1/projects/", {"name": "Theirs"}, format="json").data["id"]
        r = self.ca.post("/api/v1/designs/", {"name": "X", "kind": "interior", "project": pid, "config": {}}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("project", r.data["error"]["fields"])

    def test_config_must_be_object_and_bounded(self):
        r = self.ca.post("/api/v1/designs/", {"name": "X", "kind": "interior", "config": [1, 2]}, format="json")
        self.assertEqual(r.status_code, 400)
        big = {"k": "x" * 250_000}
        self.assertEqual(self.ca.post("/api/v1/designs/", {"name": "X", "kind": "interior", "config": big}, format="json").status_code, 400)

    def test_requires_auth(self):
        self.assertEqual(client_for().get("/api/v1/designs/").status_code, 401)
