from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.ai import providers
from apps.core import sms
from apps.core.tests.helpers import client_for, make_user


class FakeProvider(providers.AIProvider):
    name = "fake"
    capabilities = frozenset({"chat"})

    def complete(self, messages, *, system="", max_tokens=1024):
        return providers.Completion(text="ok", provider=self.name)

    def analyze_image(self, image, mime, prompt, *, max_tokens=1024):
        raise providers.AIError("no vision")


PATH = f"{__name__}.FakeProvider"


class ProviderTests(SimpleTestCase):
    def test_disabled_by_default_and_never_answers(self):
        p = providers.get_provider()
        self.assertFalse(p.enabled)
        with self.assertRaises(providers.AIDisabled):
            p.complete([providers.Message("user", "hi")])
        with self.assertRaises(providers.AIDisabled):
            p.analyze_image(b"x", "image/png", "describe")

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="", AI_PROVIDERS={"fake": PATH})
    def test_provider_without_key_stays_disabled(self):
        self.assertFalse(providers.get_provider().enabled)

    @override_settings(AI_PROVIDER="unknown", AI_API_KEY="k", AI_PROVIDERS={"fake": PATH})
    def test_unregistered_provider_stays_disabled(self):
        self.assertFalse(providers.get_provider().enabled)

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="k", AI_PROVIDERS={"fake": PATH})
    def test_registered_provider_with_key_is_used(self):
        p = providers.get_provider()
        self.assertTrue(p.enabled)
        self.assertEqual(p.complete([providers.Message("user", "hi")]).text, "ok")
        self.assertEqual(providers.status()["provider"], "fake")

    def test_sms_is_disabled_and_refuses(self):
        s = sms.get_sms()
        self.assertFalse(s.enabled)
        with self.assertRaises(sms.SmsDisabled):
            s.send("+998900000000", "code")


class StatusApiTests(TestCase):
    def test_requires_login_and_reports_disabled(self):
        self.assertEqual(APIClient().get("/api/v1/ai/status/").status_code, 401)
        r = client_for(make_user("a@x.com")).get("/api/v1/ai/status/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["enabled"], r.data["provider"], r.data["capabilities"]), (False, None, []))
        self.assertIn("not configured", r.data["message"])
