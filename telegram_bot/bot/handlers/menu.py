import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers.common import is_workshop, linked_user, send_menu
from bot.keyboards import Nav, back_to_menu, web_keyboard
from bot.services.api import BackendClient
from bot.utils.i18n import t

router = Router(name="menu")


@router.message(Command("menu"))
@router.callback_query(Nav.filter(F.to == "menu"))
async def show_menu(event: Message | CallbackQuery, api: BackendClient, lang: str) -> None:
    me = await linked_user(api, event.from_user.id)
    await send_menu(event, lang, linked=me is not None, workshop=is_workshop(me))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(Nav.filter(F.to == "profile"))
async def show_profile(callback: CallbackQuery, api: BackendClient, lang: str) -> None:
    me = await linked_user(api, callback.from_user.id)
    if me is None:
        await callback.message.answer(t("not_linked", lang))
    else:
        u = me["user"]
        name = f"{u['first_name']} {u['last_name']}".strip() or "-"
        await callback.message.answer(t("profile_text", lang, email=u["email"], name=name, role=u["role"]),
                                      reply_markup=back_to_menu(lang))
    await callback.answer()


@router.callback_query(Nav.filter(F.to == "notifications"))
async def show_notifications(callback: CallbackQuery, api: BackendClient, lang: str) -> None:
    items = await api.notifications(callback.from_user.id)
    if not items:
        text = t("notifications_empty", lang)
    else:
        lines = [t("notifications_title", lang)]
        lines += [f"• <b>{html.escape(n['title'])}</b>\n{html.escape(n['body'])}".rstrip() for n in items]
        text = "\n\n".join(lines)
    await callback.message.answer(text, reply_markup=back_to_menu(lang))
    await callback.answer()


@router.callback_query(Nav.filter(F.to == "web"))
async def open_web(callback: CallbackQuery, lang: str, web_app_url: str) -> None:
    await callback.message.answer(t("btn_web", lang), reply_markup=web_keyboard(web_app_url, lang))
    await callback.answer()


@router.callback_query(Nav.filter(F.to == "designs"))
async def open_designs(callback: CallbackQuery, lang: str, web_app_url: str) -> None:
    await callback.message.answer(t("btn_designs", lang), reply_markup=web_keyboard(f"{web_app_url}/app/editor", lang))
    await callback.answer()
