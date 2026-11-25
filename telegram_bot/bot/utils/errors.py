from bot.services.api import ApiError
from bot.utils.i18n import t

_CODE_TEXT = {
    "invalid_code": "err_invalid_code",
    "expired": "err_expired",
    "too_many_attempts": "err_too_many_attempts",
    "telegram_in_use": "err_telegram_in_use",
    "not_linked": "not_linked",
    "backend_unavailable": "backend_unavailable",
}


def api_error_text(exc: ApiError, lang: str) -> str:
    """Map a backend error code to a user-facing text. Raw backend messages are never shown to users."""
    return t(_CODE_TEXT.get(exc.code, "generic_error"), lang)
