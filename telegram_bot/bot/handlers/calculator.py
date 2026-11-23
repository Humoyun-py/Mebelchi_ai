"""Material calculator and cutting list: one question per parameter, validated before moving on."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards import ExportFile, Nav, PickProject, back_to_menu, cancel_keyboard, export_keyboard, pick_project_keyboard
from bot.services.api import ApiError, BackendClient
from bot.states import CalcStates
from bot.utils.calc import InvalidNumber, parse_number
from bot.utils.errors import api_error_text
from bot.utils.i18n import t

router = Router(name="calculator")

# (state, field, min, max, integer, prompt key). Ranges mirror backend apps/calculations/engine.py LIMITS.
STEPS = [
    (CalcStates.width, "width", 200, 4000, False, "ask_width"),
    (CalcStates.height, "height", 200, 3000, False, "ask_height"),
    (CalcStates.depth, "depth", 150, 1000, False, "ask_depth"),
    (CalcStates.thickness, "thickness", 8, 40, False, "ask_thickness"),
    (CalcStates.shelves, "shelves", 0, 20, True, "ask_shelves"),
    (CalcStates.doors, "doors", 0, 6, True, "ask_doors"),
]
STEP_BY_STATE = {step[0].state: step for step in STEPS}


async def start_flow(event: Message | CallbackQuery, state: FSMContext, lang: str, mode: str) -> None:
    await state.clear()
    await state.update_data(mode=mode, params={})
    await state.set_state(STEPS[0][0])
    message = event if isinstance(event, Message) else event.message
    await message.answer(t(STEPS[0][5], lang), reply_markup=cancel_keyboard(lang))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("calc"))
@router.callback_query(Nav.filter(F.to == "calc"))
async def start_calc(event: Message | CallbackQuery, state: FSMContext, lang: str) -> None:
    await start_flow(event, state, lang, "calc")


@router.message(Command("cutting"))
@router.callback_query(Nav.filter(F.to == "cutting"))
async def start_cutting(event: Message | CallbackQuery, state: FSMContext, lang: str) -> None:
    await start_flow(event, state, lang, "cutting")


@router.message(CalcStates.width, F.text)
@router.message(CalcStates.height, F.text)
@router.message(CalcStates.depth, F.text)
@router.message(CalcStates.thickness, F.text)
@router.message(CalcStates.shelves, F.text)
@router.message(CalcStates.doors, F.text)
async def receive_parameter(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    step_state, field, lo, hi, integer, _ = STEP_BY_STATE[await state.get_state()]
    try:
        value = parse_number(message.text or "", lo, hi, integer)
    except InvalidNumber:
        await message.answer(t("invalid_number", lang), reply_markup=cancel_keyboard(lang))
        return
    data = await state.get_data()
    params = {**data.get("params", {}), field: value}
    await state.update_data(params=params)

    index = [s[0].state for s in STEPS].index(step_state.state)
    if index + 1 < len(STEPS):
        next_state, *_rest, next_prompt = STEPS[index + 1]
        await state.set_state(next_state)
        await message.answer(t(next_prompt, lang), reply_markup=cancel_keyboard(lang))
        return

    if data.get("mode", "calc") == "calc":
        await state.clear()
        await _send_calculation(message, api, lang, params)
        return
    await state.set_state(CalcStates.project)
    projects = await api.projects(message.from_user.id)
    await message.answer(t("choose_project", lang), reply_markup=pick_project_keyboard(projects, lang))


async def _send_calculation(message: Message, api: BackendClient, lang: str, params: dict) -> None:
    try:
        result = await api.calculate(message.from_user.id, params)
    except ApiError as exc:
        await message.answer(api_error_text(exc, lang), reply_markup=back_to_menu(lang))
        return
    s = result["summary"]
    text = t("calc_result", lang, panels=s["panel_count"], distinct=s["distinct_parts"], area=s["total_area_m2"],
             edge=s["edge_banding_m"], disclaimer=t("calc_disclaimer", lang))
    await message.answer(text, reply_markup=back_to_menu(lang))


@router.callback_query(PickProject.filter(), CalcStates.project)
async def cutting_with_project(callback: CallbackQuery, callback_data: PickProject, state: FSMContext,
                               api: BackendClient, lang: str) -> None:
    data = await state.get_data()
    await state.clear()
    params = dict(data.get("params", {}))
    if callback_data.project_id:
        params["project_id"] = callback_data.project_id
    try:
        cl = await api.create_cutting_list(callback.from_user.id, params)
    except ApiError as exc:
        await callback.message.answer(api_error_text(exc, lang), reply_markup=back_to_menu(lang))
        await callback.answer()
        return
    cost = (t("cutting_cost", lang, cost=cl["estimated_cost"]) if cl["estimated_cost"] is not None
            else t("cutting_nocost", lang))
    text = t("cutting_done", lang, parts=cl["parts_count"], sheets=cl["sheet_count"], util=cl["utilization_pct"],
             cost=cost, disclaimer=cl["disclaimer"])
    await callback.message.answer(text, reply_markup=export_keyboard(cl["id"], lang))
    await callback.answer()


@router.callback_query(ExportFile.filter())
async def send_export(callback: CallbackQuery, callback_data: ExportFile, api: BackendClient, lang: str) -> None:
    try:
        content = await api.export_cutting_list(callback.from_user.id, callback_data.list_id, callback_data.kind)
    except ApiError as exc:
        await callback.message.answer(api_error_text(exc, lang))
        await callback.answer()
        return
    filename = f"cutting-list-{callback_data.list_id}.{callback_data.kind}"
    await callback.message.answer_document(BufferedInputFile(content, filename=filename))
    await callback.answer()
