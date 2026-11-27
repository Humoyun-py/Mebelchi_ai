"""OpenAI and Anthropic adapters.

Nothing here runs unless an administrator sets AI_PROVIDER, AI_API_KEY and AI_MODEL (`get_provider()` otherwise returns the disabled provider).
No model name is chosen for you: AI_MODEL is required and is sent as given. Both adapters talk plain HTTPS through httpx; tests inject an
`httpx.MockTransport` through the `transport` argument, so no test ever needs a key or the network.

The request/response shapes follow the vendors' public chat APIs (OpenAI Chat Completions, Anthropic Messages). They have NOT been exercised
against the live services from this code base: the first real call has to be reviewed by a person before it is relied on.
"""
from __future__ import annotations

import base64

import httpx
from django.conf import settings

from .providers import AIError, AIProvider, Completion, Message


class _HttpProvider(AIProvider):
    base_url = ""

    def __init__(self, api_key: str = "", *, model: str = "", transport: httpx.BaseTransport | None = None, **options):
        super().__init__(api_key, **options)
        self.model = (model or "").strip()
        self.transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.model)

    def _post(self, path: str, headers: dict, body: dict) -> dict:
        timeout = float(getattr(settings, "AI_TIMEOUT_SECONDS", 60))
        try:
            with httpx.Client(base_url=self.base_url, timeout=timeout, transport=self.transport) as client:
                resp = client.post(path, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise AIError(f"{self.name}: the request failed ({type(exc).__name__})") from exc
        if resp.status_code >= 400:
            # the vendor's error text can echo request data, so only the status code is surfaced
            raise AIError(f"{self.name}: the provider answered HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as exc:
            raise AIError(f"{self.name}: the provider returned a non-JSON answer") from exc


class OpenAIProvider(_HttpProvider):
    name = "openai"
    capabilities = frozenset({"chat", "vision"})
    base_url = "https://api.openai.com"

    def _call(self, messages: list[dict], max_tokens: int) -> Completion:
        data = self._post("/v1/chat/completions", {"Authorization": f"Bearer {self.api_key}"},
                          {"model": self.model, "messages": messages, "max_completion_tokens": max_tokens})
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError("openai: unexpected answer shape") from exc
        u = data.get("usage") or {}
        return Completion(text=text, provider=self.name, model=str(data.get("model") or self.model),
                          usage={"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")})

    def complete(self, messages: list[Message], *, system: str = "", max_tokens: int = 1024) -> Completion:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": m.role, "content": m.content} for m in messages]
        return self._call(msgs, max_tokens)

    def analyze_image(self, image: bytes, mime: str, prompt: str, *, max_tokens: int = 1024) -> Completion:
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]
        return self._call([{"role": "user", "content": content}], max_tokens)


class AnthropicProvider(_HttpProvider):
    name = "anthropic"
    capabilities = frozenset({"chat", "vision"})
    base_url = "https://api.anthropic.com"
    api_version = "2023-06-01"

    def _call(self, messages: list[dict], system: str, max_tokens: int) -> Completion:
        body = {"model": self.model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body["system"] = system
        data = self._post("/v1/messages", {"x-api-key": self.api_key, "anthropic-version": self.api_version}, body)
        try:
            text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
        except (KeyError, TypeError, AttributeError) as exc:
            raise AIError("anthropic: unexpected answer shape") from exc
        u = data.get("usage") or {}
        return Completion(text=text, provider=self.name, model=str(data.get("model") or self.model),
                          usage={"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens")})

    def complete(self, messages: list[Message], *, system: str = "", max_tokens: int = 1024) -> Completion:
        return self._call([{"role": m.role, "content": m.content} for m in messages], system, max_tokens)

    def analyze_image(self, image: bytes, mime: str, prompt: str, *, max_tokens: int = 1024) -> Completion:
        content = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(image).decode()}},
                   {"type": "text", "text": prompt}]
        return self._call([{"role": "user", "content": content}], "", max_tokens)
