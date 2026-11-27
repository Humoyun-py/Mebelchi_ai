import json

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.core import sms

CFG = dict(ESKIZ_EMAIL="gw@example.com", ESKIZ_PASSWORD="gw-pass", ESKIZ_BASE_URL="https://notify.eskiz.uz", ESKIZ_FROM="")


class PhoneFormatTests(SimpleTestCase):
    def test_documented_examples(self):
        for raw in ("+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"):
            self.assertEqual(sms.normalize_uz_phone(raw), "998901234567", raw)

    def test_invalid_numbers(self):
        for raw in ("8 90 123 45 67", "+7 916 123-45-67", "99890123456", "", "abc", "99990123456789"):
            with self.assertRaises(sms.InvalidPhone, msg=raw):
                sms.normalize_uz_phone(raw)


@override_settings(**CFG)
class EskizTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.calls = []

    def sender(self, handler):
        def wrapped(req):
            self.calls.append((req.method, req.url.path, req.headers.get("authorization"), json.loads(req.content or b"{}")))
            return handler(req)
        return sms.EskizSms(transport=httpx.MockTransport(wrapped))

    @staticmethod
    def ok(req):
        if req.url.path == "/api/auth/login":
            return httpx.Response(200, json={"message": "token_generated", "data": {"token": "T1"}, "token_type": "bearer"})
        return httpx.Response(200, json={"id": "abc", "status": "waiting", "message": "Waiting for SMS provider"})

    def test_login_then_send_with_bearer_and_normalised_phone(self):
        self.sender(self.ok).send("+998 90 123 45 67", "hello")
        self.assertEqual(self.calls[0][:2], ("POST", "/api/auth/login"))
        self.assertEqual(self.calls[0][3], {"email": "gw@example.com", "password": "gw-pass"})
        self.assertEqual(self.calls[1][:3], ("POST", "/api/message/sms/send", "Bearer T1"))
        self.assertEqual(self.calls[1][3], {"mobile_phone": "998901234567", "message": "hello"})
        self.assertNotIn("callback_url", self.calls[1][3])

    def test_token_is_cached_between_sends(self):
        s = self.sender(self.ok)
        s.send("901234567", "a")
        s.send("901234567", "b")
        self.assertEqual([c[1] for c in self.calls].count("/api/auth/login"), 1)

    def test_expired_token_logs_in_once_more(self):
        state = {"n": 0}

        def handler(req):
            if req.url.path == "/api/auth/login":
                state["n"] += 1
                return httpx.Response(200, json={"data": {"token": f"T{state['n']}"}})
            return httpx.Response(401, json={"message": "Expired"}) if req.headers["authorization"] == "Bearer T1" else httpx.Response(200, json={"status": "waiting"})

        self.sender(handler).send("901234567", "x")
        self.assertEqual(state["n"], 2)

    def test_refusals_raise_without_leaking_secrets(self):
        def bad_login(req):
            return httpx.Response(401, json={"message": "wrong"})
        with self.assertRaises(sms.SmsError) as cm:
            self.sender(bad_login).send("901234567", "x")
        self.assertNotIn("gw-pass", str(cm.exception))

        def balance(req):
            return httpx.Response(200, json={"data": {"token": "T"}}) if req.url.path.endswith("login") else httpx.Response(400, json={"status": "error", "message": "Please, fill the balance"})
        cache.clear()
        with self.assertRaises(sms.SmsError):
            self.sender(balance).send("901234567", "x")

    def test_invalid_phone_never_reaches_the_network(self):
        with self.assertRaises(sms.InvalidPhone):
            self.sender(self.ok).send("123", "x")
        self.assertEqual(self.calls, [])

    def test_network_error(self):
        def boom(req):
            raise httpx.ConnectError("down")
        with self.assertRaises(sms.SmsError):
            self.sender(boom).send("901234567", "x")


class DisabledTests(SimpleTestCase):
    def test_default_is_disabled(self):
        self.assertFalse(sms.get_sms().enabled)

    @override_settings(SMS_PROVIDER="eskiz", ESKIZ_EMAIL="", ESKIZ_PASSWORD="")
    def test_eskiz_without_credentials_is_not_enabled_and_does_not_send(self):
        s = sms.get_sms()
        self.assertFalse(s.enabled)
        with self.assertRaises(sms.SmsDisabled):
            s.send("901234567", "x")

    @override_settings(SMS_PROVIDER="eskiz", **CFG)
    def test_eskiz_with_credentials_is_enabled(self):
        self.assertTrue(sms.get_sms().enabled)
