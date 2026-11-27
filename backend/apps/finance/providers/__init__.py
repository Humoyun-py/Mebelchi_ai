"""Payment providers. A provider is live only when it is implemented AND its settings are present; otherwise the webhook answers 503 and
nothing is recorded. Click and Uzum are registered but NOT implemented: their official protocol documents could not be read when this was
written, and a protocol is never guessed."""
from __future__ import annotations

from .base import PaymentProvider
from .click import ClickProvider
from .payme import PaymeProvider
from .uzum import UzumProvider

REGISTRY: dict[str, type[PaymentProvider]] = {"payme": PaymeProvider, "click": ClickProvider, "uzum": UzumProvider}


def get_provider(name: str) -> PaymentProvider | None:
    cls = REGISTRY.get((name or "").lower())
    return cls() if cls else None
