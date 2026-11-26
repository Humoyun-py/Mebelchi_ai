"""SMS provider abstraction (phone verification). Not wired to any provider yet: `get_sms()` returns the disabled sender, which refuses
to send instead of pretending. A provider (Eskiz, Playmobile, ...) is one subclass plus `SMS_PROVIDERS = {"name": "dotted.Class"}`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string


class SmsDisabled(Exception):
    pass


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


def get_sms() -> SmsSender:
    name = (getattr(settings, "SMS_PROVIDER", "") or "").strip().lower()
    path = (getattr(settings, "SMS_PROVIDERS", {}) or {}).get(name)
    return import_string(path)() if name and path else DisabledSms()
