"""The only entry point feature code should use to call an AI provider: it records usage and never invents an answer."""
from __future__ import annotations

import time

from . import providers
from .models import AIUsage


def _log(user, feature, p, status, started, completion=None, error=""):
    usage = (completion.usage if completion else None) or {}
    AIUsage.objects.create(
        user=user if getattr(user, "pk", None) else None, feature=feature[:40], provider=p.name[:40], model=(completion.model if completion else getattr(p, "model", ""))[:80],
        status=status, input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        duration_ms=int((time.monotonic() - started) * 1000), error=error[:200])


def _run(user, feature, call):
    p = providers.get_provider()
    started = time.monotonic()
    try:
        out = call(p)
    except providers.AIDisabled:
        _log(user, feature, p, AIUsage.Status.DISABLED, started)
        raise
    except providers.AIError as exc:
        _log(user, feature, p, AIUsage.Status.ERROR, started, error=str(exc))
        raise
    _log(user, feature, p, AIUsage.Status.OK, started, out)
    return out


def complete(user, feature: str, messages: list[providers.Message], *, system: str = "", max_tokens: int = 1024) -> providers.Completion:
    return _run(user, feature, lambda p: p.complete(messages, system=system, max_tokens=max_tokens))


def analyze_image(user, feature: str, image: bytes, mime: str, prompt: str, *, max_tokens: int = 1024) -> providers.Completion:
    return _run(user, feature, lambda p: p.analyze_image(image, mime, prompt, max_tokens=max_tokens))
