from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user
from apps.materials.models import Material


class MaterialTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@example.com"), make_user("b@example.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)

    def test_system_catalogue_visible_and_read_only(self):
        r = self.ca.get("/api/v1/materials/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data) > 0)
        sys_id = Material.objects.filter(is_system=True).first().id
        self.assertEqual(self.ca.patch(f"/api/v1/materials/{sys_id}/", {"name": "Hacked"}, format="json").status_code, 403)
        self.assertEqual(self.ca.delete(f"/api/v1/materials/{sys_id}/").status_code, 403)

    def test_user_material_private_to_owner(self):
        sys_count = Material.objects.filter(is_system=True).count()
        kind = Material.objects.filter(is_system=True).first().kind
        r = self.ca.post("/api/v1/materials/", {"name": "My board", "kind": kind, "thickness": "18.0"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        mid = r.data["id"]
        self.assertFalse(Material.objects.get(pk=mid).is_system)
        self.assertEqual(len(self.ca.get("/api/v1/materials/").data), sys_count + 1)
        self.assertEqual(len(self.cb.get("/api/v1/materials/").data), sys_count)
        self.assertEqual(self.cb.patch(f"/api/v1/materials/{mid}/", {"name": "x"}, format="json").status_code, 404)
        self.assertEqual(self.ca.delete(f"/api/v1/materials/{mid}/").status_code, 204)

    def test_cannot_create_system_material_via_api(self):
        kind = Material.objects.filter(is_system=True).first().kind
        r = self.ca.post("/api/v1/materials/", {"name": "Sneaky", "kind": kind, "thickness": "18.0", "is_system": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Material.objects.get(pk=r.data["id"]).is_system)
