"""AI provider abstraction.

Nothing here talks to a real service. The platform runs without any AI provider; every feature that needs one asks `get_provider()`, which
returns the `DisabledProvider` until a provider AND its key are configured. The disabled provider never invents an answer: it raises
`AIDisabled`, which the API reports as 503 "AI is not configured".

Plugging a real provider in later (OpenAI, Anthropic, ...) is one class plus one settings line:
    class MyProvider(AIProvider):
        name = "my"
        def complete(...): ...
    AI_PROVIDERS = {"my": "myproject.ai.MyProvider"}      # settings
    AI_PROVIDER=my  AI_API_KEY=...                         # environment

Deterministic work (prices, geometry, cutting lists, matching) must never call a provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from django.conf import settings
from django.utils.module_loading import import_string


class AIDisabled(Exception):
    """No AI provider is configured (or the key is missing)."""


class AIError(Exception):
    """The provider failed (network, quota, refusal). Callers show a clear message; nothing is faked."""


@dataclass(frozen=True)
class Message:
    role: str            # "user" | "assistant"
    content: str


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str = ""
    usage: dict = field(default_factory=dict)


class AIProvider(ABC):
    name = ""
    capabilities: frozenset[str] = frozenset()      # subset of {"chat", "vision"}

    def __init__(self, api_key: str = "", **options):
        self.api_key = api_key
        self.options = options

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def complete(self, messages: list[Message], *, system: str = "", max_tokens: int = 1024) -> Completion: ...

    @abstractmethod
    def analyze_image(self, image: bytes, mime: str, prompt: str, *, max_tokens: int = 1024) -> Completion: ...


class DisabledProvider(AIProvider):
    name = "disabled"
    capabilities = frozenset()

    @property
    def enabled(self) -> bool:
        return False

    def complete(self, messages, *, system="", max_tokens=1024):
        raise AIDisabled("AI is not configured on this server.")

    def analyze_image(self, image, mime, prompt, *, max_tokens=1024):
        raise AIDisabled("AI is not configured on this server.")


def registry() -> dict[str, str]:
    return dict(getattr(settings, "AI_PROVIDERS", {}) or {})


def get_provider() -> AIProvider:
    name = (getattr(settings, "AI_PROVIDER", "") or "").strip().lower()
    key = getattr(settings, "AI_API_KEY", "") or ""
    path = registry().get(name)
    if not name or not key or not path:
        return DisabledProvider()
    return import_string(path)(api_key=key, model=getattr(settings, "AI_MODEL", ""))


def status() -> dict:
    p = get_provider()
    return {"enabled": p.enabled, "provider": p.name if p.enabled else None, "capabilities": sorted(p.capabilities),
            "available_providers": sorted(registry()),
            "message": "" if p.enabled else "AI is not configured. Chat, layouts and prices use the built-in rules engine."}
