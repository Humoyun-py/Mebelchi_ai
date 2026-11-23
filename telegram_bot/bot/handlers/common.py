"""Shared handler helpers: the main menu and the linked-account check."""
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu
from bot.utils.i18n import t


async def send_menu(event: Message | CallbackQuery, lang: str, linked: bool, text: str | None = None) -> None:
    message = event if isinstance(event, Message) else event.message
    body = text or t("menu_title", lang)
    if isinstance(event, CallbackQuery) and message is not None:
        try:
            await message.edit_text(body, reply_markup=main_menu(lang, linked))
            return
        except Exception:  # noqa: BLE001 - message may be unchanged or too old to edit; send a new one instead
            pass
    if message is not None:
        await message.answer(body, reply_markup=main_menu(lang, linked))


async def linked_user(api, telegram_id: int) -> dict | None:
    return await api.me(telegram_id)
