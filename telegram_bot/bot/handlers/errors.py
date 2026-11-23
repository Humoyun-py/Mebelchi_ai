import logging

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import CallbackQuery, ErrorEvent, Message

from bot.services.api import ApiError
from bot.utils.errors import api_error_text
from bot.utils.i18n import DEFAULT_LANG, language_for, t

logger = logging.getLogger("telegram_bot")
router = Router(name="errors")


def _lang_of(event: ErrorEvent) -> str:
    update_event = event.update.event
    user = getattr(update_event, "from_user", None)
    return language_for(getattr(user, "language_code", None))


async def _reply(event: ErrorEvent, text: str) -> None:
    inner = event.update.event
    if isinstance(inner, Message):
        await inner.answer(text)
    elif isinstance(inner, CallbackQuery):
        await inner.answer(text, show_alert=True)


@router.error(ExceptionTypeFilter(ApiError))
async def on_api_error(event: ErrorEvent) -> bool:
    exc = event.exception
    logger.warning("Backend error %s %s", exc.status, exc.code)
    await _reply(event, api_error_text(exc, _lang_of(event)))
    return True


@router.error()
async def on_unexpected(event: ErrorEvent) -> bool:
    # Full traceback goes to logs only; the user gets a generic text with no internal details.
    logger.exception("Unhandled error in update %s", event.update.update_id, exc_info=event.exception)
    try:
        await _reply(event, t("generic_error", _lang_of(event) if event.update else DEFAULT_LANG))
    except Exception:  # noqa: BLE001 - never let the error handler itself crash the dispatcher
        logger.exception("Could not send generic error message")
    return True
