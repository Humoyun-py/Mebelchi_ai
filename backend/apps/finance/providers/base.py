from __future__ import annotations

from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    name = ""
    implemented = True

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """True only when the provider is implemented and every setting it needs is present."""

    @abstractmethod
    def handle_webhook(self, *, method: str, body: bytes, headers: dict) -> tuple[int, dict]:
        """Verifies the call and applies it. Returns (HTTP status, JSON body). Must never raise for bad input."""


class NotImplementedProvider(PaymentProvider):
    """Registered so the URL space is stable, but it refuses everything: there is no verified protocol to follow."""

    implemented = False

    @property
    def enabled(self) -> bool:
        return False

    def handle_webhook(self, *, method, body, headers):
        return 503, {"detail": f"{self.name} payments are not available: the integration is not implemented."}
