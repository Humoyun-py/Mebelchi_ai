from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.filters import IsAdmin
from bot.services.api import ApiError, BackendClient
from bot.states import BroadcastStates
from bot.utils.errors import api_error_text
from bot.utils.i18n import t

router = Router(name="admin")


def register_admin_handlers(admin_ids: frozenset[int]) -> Router:
    """Admin commands are only reachable through IsAdmin; everyone else gets the 'forbidden' text.
    The router is built per configuration so the admin ID list comes from settings, not from code."""
    is_admin = IsAdmin(admin_ids)
    admin_router = Router(name="admin-commands")

    @admin_router.message(Command("admin"), is_admin)
    async def admin_menu(message: Message, lang: str) -> None:
        await message.answer(t("admin_menu", lang))

    @admin_router.message(Command("stats"), is_admin)
    @admin_router.message(Command("users"), is_admin)
    async def stats(message: Message, api: BackendClient, lang: str) -> None:
        try:
            s = await api.admin_stats(message.from_user.id)
        except ApiError as exc:
            await message.answer(api_error_text(exc, lang))
            return
        projects = s["projects_total"]
        await message.answer(t("admin_stats", lang, users=s["users_total"], active=s["users_active_30d"],
                               linked=s["telegram_linked"], projects=projects))

    @admin_router.message(Command("system_status"), is_admin)
    async def system_status(message: Message, api: BackendClient, lang: str) -> None:
        try:
            s = await api.admin_system(message.from_user.id)
        except ApiError as exc:
            await message.answer(api_error_text(exc, lang))
            return
        await message.answer(t("admin_system", lang, backend=s["backend"]["status"], db=s["database"].get("active_engine", "-"),
                               redis=s["redis"]["status"], celery=s["celery"]["status"]))

    @admin_router.message(Command("broadcast"), is_admin)
    async def broadcast(message: Message, state: FSMContext, api: BackendClient, lang: str, command: CommandObject) -> None:
        text = command.args or ""
        if text.strip():
            await _send_broadcast(message, api, lang, text)
            return
        await state.set_state(BroadcastStates.text)
        await message.answer(t("admin_broadcast_ask", lang))

    @admin_router.message(BroadcastStates.text, F.text, is_admin)
    async def broadcast_text(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
        await state.clear()
        await _send_broadcast(message, api, lang, message.text)

    @admin_router.message(Command("stats", "users", "system_status", "broadcast", "admin"))
    async def forbidden(message: Message, lang: str) -> None:
        await message.answer(t("forbidden", lang))

    return admin_router


async def _send_broadcast(message: Message, api: BackendClient, lang: str, text: str) -> None:
    try:
        await api.admin_broadcast(message.from_user.id, text.strip())
    except ApiError as exc:
        await message.answer(api_error_text(exc, lang))
        return
    await message.answer(t("admin_broadcast_queued", lang))
