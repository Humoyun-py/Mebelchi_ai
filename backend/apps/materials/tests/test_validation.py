from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.materials.models import Material

URL = "/api/v1/materials/"


class MaterialValidationTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@x.com"), make_user("b@x.com")
        self.ca, self.cb = client_for(self.a), client_for(self.b)
        self.body = {"name": "My board", "kind": "MDF", "thickness": "18.0"}

    def test_login_is_required(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.assertEqual(APIClient().post(URL, self.body, format="json").status_code, 401)

    def test_invalid_input_is_a_400_and_creates_nothing(self):
        before = Material.objects.count()
        for bad in ({**self.body, "kind": "GOLD"}, {**self.body, "thickness": "abc"}, {**self.body, "name": ""}, {"name": "x"}, {**self.body, "thickness": "99999"}):
            self.assertEqual(self.ca.post(URL, bad, format="json").status_code, 400, bad)
        self.assertEqual(Material.objects.count(), before)

    def test_the_owner_edits_their_own_material_but_cannot_claim_system_status_or_ownership(self):
        mid = self.ca.post(URL, self.body, format="json").data["id"]
        r = self.ca.patch(f"{URL}{mid}/", {"name": "Renamed", "is_system": True, "owner": self.b.pk}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        m = Material.objects.get(pk=mid)
        self.assertEqual((m.name, m.is_system, m.owner), ("Renamed", False, self.a))

    def test_a_stranger_gets_404_for_a_private_material_and_403_for_a_system_one(self):
        mid = self.ca.post(URL, self.body, format="json").data["id"]
        self.assertEqual(self.cb.delete(f"{URL}{mid}/").status_code, 404)
        sys_id = Material.objects.filter(is_system=True).first().id
        self.assertEqual(self.cb.put(f"{URL}{sys_id}/", {**self.body}, format="json").status_code, 403)
        self.assertTrue(Material.objects.filter(pk=mid, name="My board").exists())
