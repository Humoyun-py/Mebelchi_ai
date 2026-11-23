from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import Nav, ProjectAction, back_to_menu, cancel_keyboard, projects_keyboard
from bot.services.api import BackendClient
from bot.states import ProjectStates
from bot.utils.i18n import t

router = Router(name="projects")


def _valid_name(text: str | None) -> str | None:
    name = (text or "").strip()
    return name if 2 <= len(name) <= 160 else None


@router.message(Command("projects"))
@router.callback_query(Nav.filter(F.to == "projects"))
async def list_projects(event: Message | CallbackQuery, api: BackendClient, lang: str) -> None:
    projects = await api.projects(event.from_user.id)
    message = event if isinstance(event, Message) else event.message
    if not projects:
        await message.answer(f"{t('projects_title', lang)}\n\n{t('projects_empty', lang)}", reply_markup=projects_keyboard([], lang))
    else:
        await message.answer(t("projects_title", lang), reply_markup=projects_keyboard(projects, lang))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(Nav.filter(F.to == "new_project"))
@router.callback_query(Nav.filter(F.to == "create"))
async def ask_new_project(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(ProjectStates.new_name)
    await callback.message.answer(t("ask_project_name", lang), reply_markup=cancel_keyboard(lang))
    await callback.answer()


@router.message(ProjectStates.new_name, F.text)
async def create_project(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    name = _valid_name(message.text)
    if name is None:
        await message.answer(t("ask_project_name", lang), reply_markup=cancel_keyboard(lang))
        return
    project = await api.create_project(message.from_user.id, name)
    await state.clear()
    await message.answer(t("project_created", lang, name=project["name"]), reply_markup=back_to_menu(lang))


@router.callback_query(ProjectAction.filter(F.action == "rename"))
async def ask_rename(callback: CallbackQuery, callback_data: ProjectAction, state: FSMContext, lang: str) -> None:
    await state.set_state(ProjectStates.rename)
    await state.update_data(project_id=callback_data.project_id)
    await callback.message.answer(t("ask_new_name", lang), reply_markup=cancel_keyboard(lang))
    await callback.answer()


@router.message(ProjectStates.rename, F.text)
async def apply_rename(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    name = _valid_name(message.text)
    if name is None:
        await message.answer(t("ask_new_name", lang), reply_markup=cancel_keyboard(lang))
        return
    data = await state.get_data()
    project = await api.rename_project(message.from_user.id, data["project_id"], name)
    await state.clear()
    await message.answer(t("project_renamed", lang, name=project["name"]), reply_markup=back_to_menu(lang))
