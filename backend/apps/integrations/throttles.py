from rest_framework.throttling import SimpleRateThrottle


class TelegramUserThrottle(SimpleRateThrottle):
    """Rate limit per Telegram user. The bot is one client IP, so the default per-IP limits must not apply to it."""

    scope = "telegram"

    def get_cache_key(self, request, view):
        telegram_id = request.query_params.get("telegram_id")
        if telegram_id is None and isinstance(getattr(request, "data", None), dict):
            telegram_id = request.data.get("telegram_id")
        ident = str(telegram_id) if telegram_id else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
