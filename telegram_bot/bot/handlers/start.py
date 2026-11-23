from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.common import linked_user, send_menu
from bot.keyboards import cancel_keyboard, main_menu, Nav
from bot.services.api import ApiError, BackendClient
from bot.states import LinkStates
from bot.utils.errors import api_error_text
from bot.utils.i18n import t

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    await state.clear()
    me = await linked_user(api, message.from_user.id)
    if me is None:
        await message.answer(t("welcome_unlinked", lang), reply_markup=main_menu(lang, linked=False))
        return
    name = me["user"]["first_name"] or me["user"]["email"]
    await message.answer(t("welcome_linked", lang, name=name), reply_markup=main_menu(lang, linked=True))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    await state.clear()
    me = await linked_user(api, message.from_user.id)
    await message.answer(t("cancelled", lang), reply_markup=main_menu(lang, linked=me is not None))


@router.callback_query(Nav.filter(F.to == "cancel"))
async def cb_cancel(callback: CallbackQuery, state: FSMContext, api: BackendClient, lang: str) -> None:
    await state.clear()
    me = await linked_user(api, callback.from_user.id)
    await send_menu(callback, lang, linked=me is not None, text=t("cancelled", lang))
    await callback.answer()


@router.message(Command("help"))
@router.callback_query(Nav.filter(F.to == "help"))
async def show_help(event: Message | CallbackQuery, lang: str) -> None:
    if isinstance(event, CallbackQuery):
        await event.message.answer(t("help_text", lang))
        await event.answer()
    else:
        await event.answer(t("help_text", lang))


@router.message(Command("link"))
@router.callback_query(Nav.filter(F.to == "link"))
async def start_link(event: Message | CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(LinkStates.code)
    message = event if isinstance(event, Message) else event.message
    await message.answer(t("link_ask_code", lang), reply_markup=cancel_keyboard(lang))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(LinkStates.code, F.text)
async def receive_link_code(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    user = message.from_user
    try:
        linked = await api.link(user.id, user.username or "", message.text or "")
    except ApiError as exc:
        await message.answer(api_error_text(exc, lang), reply_markup=cancel_keyboard(lang))
        return
    await state.clear()
    await message.answer(t("link_ok", lang, email=linked["email"]), reply_markup=main_menu(lang, linked=True))


@router.message(Command("unlink"))
@router.callback_query(Nav.filter(F.to == "unlink"))
async def unlink(event: Message | CallbackQuery, api: BackendClient, lang: str) -> None:
    telegram_id = event.from_user.id
    if await linked_user(api, telegram_id) is not None:
        await api.unlink(telegram_id)
    message = event if isinstance(event, Message) else event.message
    await message.answer(t("unlinked_done", lang), reply_markup=main_menu(lang, linked=False))
    if isinstance(event, CallbackQuery):
        await event.answer()
