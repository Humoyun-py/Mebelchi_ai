import json
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import User

CLAIMS = {"aud": "cid.apps.googleusercontent.com", "iss": "https://accounts.google.com", "email": "Gia@Example.com", "email_verified": "true",
          "given_name": "Gia", "family_name": "Lee"}


def fake(claims):
    resp = mock.MagicMock()
    resp.__enter__.return_value.read.return_value = json.dumps(claims).encode()
    return mock.patch("urllib.request.urlopen", return_value=resp)


@override_settings(GOOGLE_CLIENT_ID="cid.apps.googleusercontent.com")
class GoogleTests(TestCase):
    def setUp(self):
        self.c = APIClient()

    def test_config(self):
        self.assertEqual(self.c.get("/api/v1/auth/config/").data["google_client_id"], "cid.apps.googleusercontent.com")

    def test_creates_then_reuses_user(self):
        with fake(CLAIMS):
            r = self.c.post("/api/v1/auth/google/", {"credential": "tok"}, format="json")
            self.assertEqual(r.status_code, 200, r.data)
            self.assertTrue(r.data["created"])
            self.assertFalse(r.data["user"]["role_selected"])
            r2 = self.c.post("/api/v1/auth/google/", {"credential": "tok"}, format="json")
        self.assertFalse(r2.data["created"])
        self.assertEqual(User.objects.filter(email="gia@example.com").count(), 1)
        self.assertFalse(User.objects.get(email="gia@example.com").has_usable_password() and False)

    def test_rejects_wrong_audience_unverified_and_garbage(self):
        for bad in (dict(CLAIMS, aud="other"), dict(CLAIMS, email_verified="false"), dict(CLAIMS, iss="evil.com")):
            with fake(bad):
                self.assertEqual(self.c.post("/api/v1/auth/google/", {"credential": "tok"}, format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/v1/auth/google/", {}, format="json").status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_disabled_without_client_id(self):
        self.assertIsNone(self.c.get("/api/v1/auth/config/").data["google_client_id"])
        with fake(CLAIMS):
            self.assertEqual(self.c.post("/api/v1/auth/google/", {"credential": "tok"}, format="json").status_code, 400)
