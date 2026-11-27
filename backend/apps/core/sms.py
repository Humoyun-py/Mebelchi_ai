"""SMS provider abstraction (phone verification).

`get_sms()` returns the disabled sender, which refuses to send instead of pretending, until SMS_PROVIDER names a registered provider AND that
provider has its credentials. The Eskiz adapter below follows the gateway documentation at https://notify.eskiz.uz (login, token, send);
tests inject an `httpx.MockTransport`, so no test needs credentials or the network.
"""
from __future__ import annotations

import re
import threading
from abc import ABC, abstractmethod

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string


class SmsDisabled(Exception):
    pass


class SmsError(Exception):
    """The provider failed or refused the message. The text never contains credentials or the message body."""


class InvalidPhone(ValueError):
    pass


def normalize_uz_phone(raw: str) -> str:
    """998XXXXXXXXX. Rules from the Eskiz documentation: keep only digits; if 9 remain, prepend 998; the result must be 12 digits starting 998."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        raise InvalidPhone("Enter an Uzbekistan mobile number: +998 XX XXX XX XX.")
    return digits


class SmsSender(ABC):
    name = ""

    def __init__(self, **options):
        self.options = options

    @property
    def enabled(self) -> bool:
        return True

    @abstractmethod
    def send(self, phone: str, text: str) -> None: ...


class DisabledSms(SmsSender):
    name = "disabled"

    @property
    def enabled(self) -> bool:
        return False

    def send(self, phone, text):
        raise SmsDisabled("SMS is not configured on this server.")


class EskizSms(SmsSender):
    """Eskiz gateway. POST /api/auth/login gives a token valid 30 days (`data.token`); every send uses `Authorization: Bearer <token>`;
    a 401 means the token is gone, so the adapter logs in again once. `callback_url` is deliberately not used (Eskiz callbacks carry no
    signature, so they could be forged)."""

    name = "eskiz"
    TOKEN_CACHE_KEY = "eskiz-token"
    TOKEN_TTL = 25 * 24 * 3600          # shorter than the documented 30 days
    _lock = threading.Lock()

    def __init__(self, *, transport: httpx.BaseTransport | None = None, **options):
        super().__init__(**options)
        self.transport = transport
        self.base_url = (getattr(settings, "ESKIZ_BASE_URL", "") or "https://notify.eskiz.uz").rstrip("/")
        self.email = getattr(settings, "ESKIZ_EMAIL", "")
        self.password = getattr(settings, "ESKIZ_PASSWORD", "")
        self.sender = getattr(settings, "ESKIZ_FROM", "")

    @property
    def enabled(self) -> bool:
        return bool(self.email and self.password)

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=15, transport=self.transport)

    def _login(self) -> str:
        try:
            with self._client() as c:
                r = c.post("/api/auth/login", json={"email": self.email, "password": self.password})
        except httpx.HTTPError as exc:
            raise SmsError(f"eskiz login failed ({type(exc).__name__})") from exc
        if r.status_code != 200:
            raise SmsError(f"eskiz login was refused (HTTP {r.status_code})")
        try:
            token = r.json()["data"]["token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SmsError("eskiz login returned an unexpected answer") from exc
        cache.set(self.TOKEN_CACHE_KEY, token, self.TOKEN_TTL)
        return token

    def _token(self) -> str:
        return cache.get(self.TOKEN_CACHE_KEY) or self._login()

    def _post_sms(self, token: str, phone: str, text: str) -> httpx.Response:
        body = {"mobile_phone": phone, "message": text}
        if self.sender:
            body["from"] = self.sender
        try:
            with self._client() as c:
                return c.post("/api/message/sms/send", json=body, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise SmsError(f"eskiz send failed ({type(exc).__name__})") from exc

    def send(self, phone: str, text: str) -> None:
        phone = normalize_uz_phone(phone)
        if not self.enabled:
            raise SmsDisabled("SMS is not configured on this server.")
        r = self._post_sms(self._token(), phone, text)
        if r.status_code == 401:                                   # expired token or changed password: log in once more
            with self._lock:
                cache.delete(self.TOKEN_CACHE_KEY)
                r = self._post_sms(self._login(), phone, text)
        if r.status_code != 200:
            raise SmsError(f"eskiz refused the message (HTTP {r.status_code})")
        try:
            status = r.json().get("status")
        except ValueError:
            status = None
        if status == "error":
            raise SmsError("eskiz refused the message")


def get_sms() -> SmsSender:
    name = (getattr(settings, "SMS_PROVIDER", "") or "").strip().lower()
    path = (getattr(settings, "SMS_PROVIDERS", {}) or {}).get(name)
    return import_string(path)() if name and path else DisabledSms()
