from django.test import TestCase

from apps.core.tests.helpers import client_for, make_user


class ProfileTests(TestCase):
    def setUp(self):
        self.u = make_user("u@example.com")
        self.c = client_for(self.u)

    def test_me_get_and_patch_preferences(self):
        self.assertEqual(self.c.get("/api/v1/users/me/").data["email"], "u@example.com")
        r = self.c.patch("/api/v1/users/me/", {"language": "uz", "theme": "light", "first_name": "Ali"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.u.refresh_from_db()
        self.assertEqual((self.u.language, self.u.theme, self.u.first_name), ("uz", "light", "Ali"))

    def test_invalid_language_rejected(self):
        self.assertEqual(self.c.patch("/api/v1/users/me/", {"language": "xx"}, format="json").status_code, 400)

    def test_no_privilege_escalation(self):
        self.c.patch("/api/v1/users/me/", {"is_staff": True, "is_superuser": True, "email": "new@example.com"}, format="json")
        self.u.refresh_from_db()
        self.assertFalse(self.u.is_staff or self.u.is_superuser)
        self.assertEqual(self.u.email, "u@example.com")

    def test_role_selection(self):
        r = self.c.post("/api/v1/users/me/role/", {"role": "homeowner"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["role"], "homeowner")
        self.assertEqual(self.c.post("/api/v1/users/me/role/", {"role": "admin"}, format="json").status_code, 400)

    def test_password_change_requires_current_password(self):
        bad = self.c.post("/api/v1/users/me/password/", {"current_password": "wrong", "new_password": "BrandNew!Pass99"}, format="json")
        self.assertEqual(bad.status_code, 400)
        ok = self.c.post("/api/v1/users/me/password/", {"current_password": "StrongPass!234", "new_password": "BrandNew!Pass99"}, format="json")
        self.assertEqual(ok.status_code, 204, getattr(ok, "data", None))
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("BrandNew!Pass99"))

    def test_weak_new_password_rejected(self):
        r = self.c.post("/api/v1/users/me/password/", {"current_password": "StrongPass!234", "new_password": "12345678"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_avatar_file_needs_valid_signature(self):
        self.assertEqual(client_for().get(f"/api/v1/users/{self.u.id}/avatar/").status_code, 404)
        self.assertEqual(client_for().get(f"/api/v1/users/{self.u.id}/avatar/?sig=bogus").status_code, 404)

    def test_storage_summary(self):
        r = self.c.get("/api/v1/users/me/storage/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("used_bytes", r.data)

    def test_requires_auth(self):
        self.assertEqual(client_for().get("/api/v1/users/me/").status_code, 401)
