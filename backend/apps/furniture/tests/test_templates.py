from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests.helpers import client_for, make_user
from apps.furniture.models import FurnitureTemplate

URL = "/api/v1/furniture/templates/"


class TemplateTests(TestCase):
    def setUp(self):
        self.c = client_for(make_user("a@x.com"))

    def test_login_is_required(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.assertEqual(APIClient().get("/api/v1/furniture/categories/").status_code, 401)

    def test_templates_are_read_only(self):
        t = FurnitureTemplate.objects.first()
        self.assertIsNotNone(t, "the seeded catalogue is missing")
        self.assertEqual(self.c.post(URL, {"slug": "x", "category": "c", "name": "n"}, format="json").status_code, 405)
        self.assertEqual(self.c.patch(f"{URL}{t.pk}/", {"name": "x"}, format="json").status_code, 405)
        self.assertEqual(self.c.delete(f"{URL}{t.pk}/").status_code, 405)

    def test_inactive_templates_are_hidden_everywhere(self):
        t = FurnitureTemplate.objects.create(slug="retired", category="wardrobe", name="Retired", is_active=False)
        self.assertNotIn("retired", [x["slug"] for x in self.c.get(URL).data])
        self.assertEqual(self.c.get(f"{URL}{t.pk}/").status_code, 404)

    def test_category_filter_and_search(self):
        FurnitureTemplate.objects.create(slug="zz-1", category="zz-cat", name="Zebra cabinet")
        self.assertEqual([x["slug"] for x in self.c.get(URL, {"category": "zz-cat"}).data], ["zz-1"])
        self.assertEqual([x["slug"] for x in self.c.get(URL, {"search": "zebra"}).data], ["zz-1"])
        self.assertEqual(self.c.get(URL, {"category": "no-such"}).data, [])

    def test_categories_endpoint(self):
        r = self.c.get("/api/v1/furniture/categories/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data) > 0)

    def test_slugs_are_unique_in_the_database(self):
        from django.db import IntegrityError, transaction
        FurnitureTemplate.objects.create(slug="dup", category="c", name="One")
        with self.assertRaises(IntegrityError), transaction.atomic():
            FurnitureTemplate.objects.create(slug="dup", category="c", name="Two")
