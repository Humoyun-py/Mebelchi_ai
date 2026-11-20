import re

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User

REG = dict(first_name="Ali", last_name="Karimov", email="Ali@Example.com", phone="+998901112233",
           password="Str0ng!Passw0rd", confirm_password="Str0ng!Passw0rd")
URL = "/api/v1/auth/"


class AuthTests(TestCase):
    def setUp(self):
        self.c = APIClient()

    def _register(self):
        r = self.c.post(URL + "register/", REG, format="json")
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return r

    def test_register_login_refresh_logout(self):
        r = self.c.post(URL + "register/", REG, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["user"]["email"], "ali@example.com")
        self.assertFalse(r.data["user"]["role_selected"])
        self.assertNotIn("password", r.data["user"])
        r = self.c.post(URL + "login/", {"email": "ALI@example.com", "password": REG["password"]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(self.c.get("/api/v1/users/me/").status_code, 200)
        r2 = self.c.post(URL + "refresh/", {"refresh": r.data["refresh"]}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self.c.post(URL + "logout/", {"refresh": r2.data["refresh"]}, format="json").status_code, 204)
        self.assertEqual(self.c.post(URL + "refresh/", {"refresh": r2.data["refresh"]}, format="json").status_code, 401)

    def test_register_validation(self):
        self.assertEqual(self.c.post(URL + "register/", dict(REG, confirm_password="x"), format="json").status_code, 400)
        weak = dict(REG, password="12345678", confirm_password="12345678")
        self.assertEqual(self.c.post(URL + "register/", weak, format="json").status_code, 400)
        self.c.post(URL + "register/", REG, format="json")
        r = self.c.post(URL + "register/", dict(REG, email="ali@example.com"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.data)

    def test_bad_login(self):
        self.c.post(URL + "register/", REG, format="json")
        r = self.c.post(URL + "login/", {"email": "ali@example.com", "password": "nope"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_protected_requires_auth(self):
        for url in ("/api/v1/users/me/", "/api/v1/projects/", "/api/v1/gallery/", "/api/v1/admin-api/stats/"):
            self.assertEqual(self.c.get(url).status_code, 401, url)

    def test_role_selection(self):
        self._register()
        self.assertEqual(self.c.post("/api/v1/users/me/role/", {"role": "admin"}, format="json").status_code, 400)
        r = self.c.post("/api/v1/users/me/role/", {"role": "maker"}, format="json")
        self.assertEqual((r.data["role"], r.data["role_selected"]), ("maker", True))
        self.assertEqual(User.objects.get(email="ali@example.com").role, "maker")

    def test_profile_cannot_escalate(self):
        reg = self._register()
        self.c.patch("/api/v1/users/me/", {"is_staff": True, "is_superuser": True, "email": "evil@x.com",
                                           "theme": "light", "language": "uz"}, format="json")
        u = User.objects.get(pk=reg.data["user"]["id"])
        self.assertFalse(u.is_staff or u.is_superuser)
        self.assertEqual((u.email, u.theme, u.language), ("ali@example.com", "light", "uz"))

    def test_password_reset_flow(self):
        self.c.post(URL + "register/", REG, format="json")
        self.assertEqual(self.c.post(URL + "password-reset/", {"email": "nobody@example.com"}, format="json").status_code, 202)
        self.assertEqual(len(mail.outbox), 0)  # no account enumeration
        self.c.post(URL + "password-reset/", {"email": "ali@example.com"}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        uid, token = re.search(r"uid=([^&\s]+)&token=([^\s]+)", mail.outbox[0].body).groups()
        confirm = URL + "password-reset/confirm/"
        new = "N3w!Passw0rdX"
        self.assertEqual(self.c.post(confirm, {"uid": uid, "token": "bad", "new_password": new}, format="json").status_code, 400)
        self.assertEqual(self.c.post(confirm, {"uid": uid, "token": token, "new_password": "123"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(confirm, {"uid": uid, "token": token, "new_password": new}, format="json").status_code, 204)
        self.assertEqual(self.c.post(URL + "login/", {"email": "ali@example.com", "password": new}, format="json").status_code, 200)
        self.assertEqual(self.c.post(confirm, {"uid": uid, "token": token, "new_password": "An0ther!Passw0rd"}, format="json").status_code, 400)

    def test_password_change_and_sessions(self):
        self._register()
        pw = "/api/v1/users/me/password/"
        self.assertEqual(self.c.post(pw, {"current_password": "wrong", "new_password": "N3w!Passw0rdX"}, format="json").status_code, 400)
        self.assertEqual(self.c.post(pw, {"current_password": REG["password"], "new_password": "N3w!Passw0rdX"}, format="json").status_code, 204)
        self.assertEqual(len(self.c.get("/api/v1/users/me/sessions/").data), 1)
        self.assertEqual(self.c.delete("/api/v1/users/me/sessions/").data["revoked"], 1)
        self.assertEqual(len(self.c.get("/api/v1/users/me/sessions/").data), 0)
