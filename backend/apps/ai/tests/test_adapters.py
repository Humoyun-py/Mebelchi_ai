import json

import httpx
from django.test import SimpleTestCase, TestCase, override_settings

from apps.ai import providers, services
from apps.ai.adapters import AnthropicProvider, OpenAIProvider
from apps.ai.models import AIUsage
from apps.core.tests.helpers import make_user

MSGS = [providers.Message("user", "hello")]


def mock(handler):
    return httpx.MockTransport(handler)


class OpenAITests(SimpleTestCase):
    def test_chat_request_and_answer(self):
        seen = {}

        def handler(req):
            seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
            return httpx.Response(200, json={"model": "m-1", "choices": [{"message": {"content": "hi there"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 7}})

        p = OpenAIProvider("sk-test", model="m-1", transport=mock(handler))
        out = p.complete(MSGS, system="be brief", max_tokens=50)
        self.assertEqual((out.text, out.provider, out.usage), ("hi there", "openai", {"input_tokens": 5, "output_tokens": 7}))
        self.assertEqual(seen["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer sk-test")
        self.assertEqual(seen["body"]["messages"][0], {"role": "system", "content": "be brief"})
        self.assertEqual(seen["body"]["max_completion_tokens"], 50)

    def test_image_is_sent_as_data_url(self):
        seen = {}

        def handler(req):
            seen["body"] = json.loads(req.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "a room"}}]})

        OpenAIProvider("k", model="m", transport=mock(handler)).analyze_image(b"\x89PNG", "image/png", "what is this")
        part = seen["body"]["messages"][0]["content"][1]
        self.assertTrue(part["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_errors_never_leak_the_vendor_text(self):
        p = OpenAIProvider("k", model="m", transport=mock(lambda r: httpx.Response(429, json={"error": "secret prompt echoed"})))
        with self.assertRaises(providers.AIError) as cm:
            p.complete(MSGS)
        self.assertIn("429", str(cm.exception))
        self.assertNotIn("secret", str(cm.exception))

    def test_bad_shapes_and_network_failures_are_ai_errors(self):
        for handler in (lambda r: httpx.Response(200, json={"nope": 1}), lambda r: httpx.Response(200, text="<html>")):
            with self.assertRaises(providers.AIError):
                OpenAIProvider("k", model="m", transport=mock(handler)).complete(MSGS)

        def boom(req):
            raise httpx.ConnectError("down")
        with self.assertRaises(providers.AIError):
            OpenAIProvider("k", model="m", transport=mock(boom)).complete(MSGS)

    def test_a_key_without_a_model_is_not_enabled(self):
        self.assertFalse(OpenAIProvider("k", model="").enabled)
        self.assertTrue(OpenAIProvider("k", model="m").enabled)


class AnthropicTests(SimpleTestCase):
    def test_messages_request_and_answer(self):
        seen = {}

        def handler(req):
            seen.update(url=str(req.url), key=req.headers["x-api-key"], ver=req.headers["anthropic-version"], body=json.loads(req.content))
            return httpx.Response(200, json={"model": "c-1", "content": [{"type": "text", "text": "good"}, {"type": "text", "text": " day"}],
                                             "usage": {"input_tokens": 3, "output_tokens": 4}})

        out = AnthropicProvider("ak-test", model="c-1", transport=mock(handler)).complete(MSGS, system="sys", max_tokens=20)
        self.assertEqual((out.text, out.usage), ("good day", {"input_tokens": 3, "output_tokens": 4}))
        self.assertEqual((seen["url"], seen["key"], seen["ver"]), ("https://api.anthropic.com/v1/messages", "ak-test", "2023-06-01"))
        self.assertEqual((seen["body"]["system"], seen["body"]["max_tokens"]), ("sys", 20))

    def test_image_block(self):
        seen = {}

        def handler(req):
            seen["body"] = json.loads(req.content)
            return httpx.Response(200, json={"content": [{"type": "text", "text": "x"}]})

        AnthropicProvider("k", model="m", transport=mock(handler)).analyze_image(b"abc", "image/jpeg", "describe")
        block = seen["body"]["messages"][0]["content"][0]
        self.assertEqual((block["type"], block["source"]["media_type"]), ("image", "image/jpeg"))

    def test_http_error(self):
        with self.assertRaises(providers.AIError):
            AnthropicProvider("k", model="m", transport=mock(lambda r: httpx.Response(500))).complete(MSGS)


class DisabledByDefault(SimpleTestCase):
    def test_adapters_are_registered_but_inert_without_configuration(self):
        self.assertEqual(sorted(providers.registry()), ["anthropic", "openai"])
        self.assertFalse(providers.get_provider().enabled)

    @override_settings(AI_PROVIDER="openai", AI_API_KEY="k", AI_MODEL="")
    def test_key_without_model_stays_disabled(self):
        self.assertFalse(providers.get_provider().enabled)

    @override_settings(AI_PROVIDER="anthropic", AI_API_KEY="", AI_MODEL="m")
    def test_model_without_key_stays_disabled(self):
        self.assertFalse(providers.get_provider().enabled)


class UsageTests(TestCase):
    def test_disabled_call_is_logged_and_never_answers(self):
        u = make_user()
        with self.assertRaises(providers.AIDisabled):
            services.complete(u, "chat", MSGS)
        row = AIUsage.objects.get()
        self.assertEqual((row.status, row.feature, row.user_id), ("disabled", "chat", u.pk))

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="k", AI_PROVIDERS={"fake": "apps.ai.tests.test_providers.FakeProvider"})
    def test_successful_call_is_logged_without_content(self):
        services.complete(make_user("b@x.com"), "design", MSGS)
        row = AIUsage.objects.get()
        self.assertEqual((row.status, row.provider), ("ok", "fake"))
        self.assertFalse(any("hello" in str(getattr(row, f.name)) for f in AIUsage._meta.fields))

    @override_settings(AI_PROVIDER="fake", AI_API_KEY="k", AI_PROVIDERS={"fake": "apps.ai.tests.test_providers.FakeProvider"})
    def test_provider_error_is_logged_and_reraised(self):
        with self.assertRaises(providers.AIError):
            services.analyze_image(None, "vision", b"x", "image/png", "p")
        self.assertEqual(AIUsage.objects.get().status, "error")
