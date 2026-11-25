import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.services.api import BackendClient
from bot.utils.i18n import language_for, t
from bot.utils.ratelimit import SlidingWindowLimiter

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class ServicesMiddleware(BaseMiddleware):
    """Injects the API client and the user's language into every handler."""

    def __init__(self, api: BackendClient, web_app_url: str, max_upload_mb: int):
        self.api = api
        self.web_app_url = web_app_url.rstrip("/")
        self.max_upload_mb = max_upload_mb

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        data["api"] = self.api
        data["web_app_url"] = self.web_app_url
        data["max_upload_mb"] = self.max_upload_mb
        data["lang"] = language_for(getattr(user, "language_code", None))
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Protects the bot and the backend from floods. Answers once per refused update, then stays silent."""

    def __init__(self, limit_per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.limiter = SlidingWindowLimiter(limit_per_minute)
        self.clock = clock

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)
        if self.limiter.allow(user.id, self.clock()):
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer(t("rate_limited", data.get("lang", "uz")))
        elif isinstance(event, CallbackQuery):
            await event.answer(t("rate_limited", data.get("lang", "uz")), show_alert=False)
        return None
