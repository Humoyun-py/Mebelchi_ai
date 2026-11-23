"""Room design in Telegram. The conversation lives on the server (backend /telegram/bot/room-flows/); this module only renders
what the server asks (a "descriptor": choice, photo, number_group, openings, furnish, summary) and sends the answers back.

Nothing is remembered here except a few half-typed values of one form in the FSM (the calculator does the same). After a
restart, /room asks the server for the active flow and continues from the right step."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.files import _download
from bot.keyboards import Nav, cancel_keyboard
from bot.keyboards.room import (RoomPick, catalog_keyboard, choice_keyboard, done_keyboard, furnish_keyboard, item_keyboard, multi_keyboard, numbers_keyboard,
                                photo_keyboard, resume_keyboard, walls_keyboard, width_keyboard)
from bot.services.api import ApiError, BackendClient
from bot.services.uploads import UploadRejected, check_upload
from bot.states import RoomStates
from bot.utils.calc import InvalidNumber, parse_number
from bot.utils.errors import api_error_text
from bot.utils.i18n import t

router = Router(name="room")

DOOR_DEFAULTS = {"width": 900, "height": 2100}
WINDOW_DEFAULTS = {"width": 1200, "height": 1200, "sill": 900}
MOVES = {"w": ("x", -100), "e": ("x", 100), "n": ("z", -100), "s": ("z", 100)}
QUIET_CODES = {"step_mismatch", "not_furnishing", "not_generated"}   # the screen is simply out of date: show the real one
HIDDEN_FIELDS = {"code", "expected", "current_rev", "detail"}


# ------------------------------------------------------------------------------------------------ small helpers

def _msg(event: Message | CallbackQuery) -> Message:
    return event if isinstance(event, Message) else event.message


async def _say(event: Message | CallbackQuery, text: str, kb=None) -> None:
    """Edit the button message in place when possible, otherwise send a new one."""
    if isinstance(event, CallbackQuery) and event.message is not None:
        try:
            await event.message.edit_text(text, reply_markup=kb)
            return
        except Exception:  # noqa: BLE001 - unchanged, too old, or has a photo: send a new message instead
            pass
    await _msg(event).answer(text, reply_markup=kb)


def _web_url(web_app_url: str, flow_id: int) -> str | None:
    return f"{web_app_url}/app/room-flow?flow={flow_id}" if web_app_url else None


def fields_text(fields: dict) -> str:
    parts = []
    for key, value in (fields or {}).items():
        if key in HIDDEN_FIELDS:
            continue
        msg = value[0] if isinstance(value, list) and value else value
        parts.append(f"{key}: {msg}")
    return "; ".join(parts[:3])


def _item_label(item: dict, view: dict, lang: str) -> str:
    if item.get("name"):
        return item["name"]
    for c in view.get("descriptor", {}).get("catalog", []):
        if c["slug"] == item.get("template"):
            return c["label"][lang]
    return item.get("template") or item["id"]


def item_line(n: int, item: dict, view: dict, lang: str) -> str:
    return t("room_item_line", lang, n=n, name=_item_label(item, view, lang), w=item["width"], d=item["depth"], h=item["height"], x=item["x"], z=item["z"], rot=item["rot"])


def warning_lines(view: dict, lang: str) -> list[str]:
    items = {i["id"]: i for i in view.get("items", [])}
    catalog = {c["slug"]: c for c in view.get("descriptor", {}).get("catalog", [])}
    out = []
    for w in view.get("warnings", []):
        code = w.get("code")
        if code == "door_zone" and w.get("item") in items:
            out.append(t("room_warn_door_zone", lang, name=_item_label(items[w["item"]], view, lang)))
        elif code == "not_placed":
            c = catalog.get(w.get("item"))
            out.append(t("room_warn_not_placed", lang, name=c["label"][lang] if c else w.get("item", "")))
        elif code == "items_reset":
            out.append(t("room_warn_items_reset", lang))
    return out


def _head(d: dict, lang: str) -> str:
    return f"{t('room_progress', lang, i=d['index'], n=d['total'])}\n<b>{d['title'][lang]}</b>\n{d['prompt'][lang]}"


# ------------------------------------------------------------------------------------------------ rendering

async def render(event: Message | CallbackQuery, state: FSMContext, lang: str, web_app_url: str, view: dict, say=None) -> None:
    """Show the step the server is on and prepare the FSM for it."""
    d, fid = view["descriptor"], view["id"]
    notes = "\n".join(warning_lines(view, lang))
    suffix = f"\n\n{notes}" if notes else ""
    say = say or _say
    if view["status"] != "active" and d["kind"] != "summary":
        await state.clear()
        await say(event, t("room_closed", lang))
        return
    kind = d["kind"]
    if kind == "choice":
        await state.clear()
        text = _head(d, lang)
        if d["step"] == "style":
            text += "\n\n" + "\n".join(f"<b>{o['label'][lang]}</b>: {o['text'][lang]}" for o in d["options"])
        await say(event, text + suffix, choice_keyboard(d["options"], lang, fid, d["can_back"]))
    elif kind == "photo":
        await state.clear()
        await state.set_state(RoomStates.photo)
        await state.update_data(flow_id=fid)
        await say(event, f"{_head(d, lang)}\n\n{t('room_photo_hint', lang)}", photo_keyboard(lang, fid))
    elif kind == "number_group":
        await state.clear()
        await state.update_data(mode="group", flow_id=fid, step=d["step"], fields=d["fields"], idx=0, values={}, selected=[], head=_head(d, lang))
        await _ask_field(event, state, lang, say)
    elif kind == "openings":
        await state.clear()
        todo = ["door"] * d["required"]["doors"] + ["window"] * d["required"]["windows"]
        await state.update_data(mode="opening", flow_id=fid, todo=todo, done=[], idx=0, cur={}, phase="wall", room=d["room"], limits=d["limits"],
                                wall_lengths=d["wall_lengths"], walls=d["walls"])
        await _ask_wall(event, state, lang, say)
    elif kind == "furnish":
        await state.clear()
        await say(event, _furnish_text(view, lang) + suffix, furnish_keyboard(view.get("items", []), lang, fid, _web_url(web_app_url, fid)))
    else:  # summary: the design is saved
        await state.clear()
        a = view["answers"]
        size = a.get("size", {})
        text = t("room_saved", lang, goal=t(f"room_goal_{a.get('goal', 'other')}", lang), w=size.get("width", "-"), l=size.get("length", "-"), h=size.get("height", "-"),
                 n=len(view.get("items", [])), disclaimer=t("calc_disclaimer", lang))
        await say(event, text, done_keyboard(lang, _web_url(web_app_url, fid)))


def _furnish_text(view: dict, lang: str) -> str:
    d = view["descriptor"]
    items = view.get("items", [])
    lines = [item_line(i + 1, it, view, lang) for i, it in enumerate(items)] or [t("room_no_items", lang)]
    return f"{_head(d, lang)}\n\n{t('room_items_title', lang)}\n" + "\n".join(lines)


async def _fail(event, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, exc: ApiError, flow_id: int | None) -> None:
    """Turn a backend error into something useful. Out-of-date screens are replaced by the real current step."""
    message = _msg(event)
    if exc.code == "not_active":
        await state.clear()
        await message.answer(t("room_closed", lang))
    elif exc.code == "rev_conflict" or exc.code in QUIET_CODES or exc.status == 400:
        if exc.code == "rev_conflict":
            await message.answer(t("room_conflict", lang))
        elif exc.status == 400:
            await message.answer(t("room_invalid_values", lang, detail=fields_text(exc.fields) or exc.detail))
        if flow_id:
            try:
                await render(event, state, lang, web_app_url, await api.room_get(event.from_user.id, flow_id), say=_new_message)
            except ApiError as again:
                await message.answer(api_error_text(again, lang))
    else:
        await message.answer(api_error_text(exc, lang))


async def _new_message(event, text: str, kb=None) -> None:
    await _msg(event).answer(text, reply_markup=kb)


async def _submit(event, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, flow_id: int, step: str, value) -> None:
    try:
        view = await api.room_answer(event.from_user.id, flow_id, step, value)
    except ApiError as exc:
        await _fail(event, state, api, lang, web_app_url, exc, flow_id)
        return
    await render(event, state, lang, web_app_url, view, say=_new_message if isinstance(event, Message) else _say)


# ------------------------------------------------------------------------------------------------ entry points

@router.message(Command("room"))
@router.callback_query(Nav.filter(F.to == "room"))
async def start_room(event: Message | CallbackQuery, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    await state.clear()
    try:
        view, created = await api.room_start(event.from_user.id)
    except ApiError as exc:
        await _msg(event).answer(api_error_text(exc, lang))
        if isinstance(event, CallbackQuery):
            await event.answer()
        return
    d = view["descriptor"]
    if created or not view["answers"]:
        await render(event, state, lang, web_app_url, view, say=_new_message)
    else:
        await _msg(event).answer(t("room_unfinished", lang, i=d["index"], n=d["total"]), reply_markup=resume_keyboard(lang, view["id"]))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.callback_query(RoomPick.filter(F.a == "resume"))
async def resume(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    await _reload(callback, state, api, lang, web_app_url, callback_data.f)
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "new"))
async def start_new(callback: CallbackQuery, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    try:
        view, _ = await api.room_start(callback.from_user.id, new=True)
    except ApiError as exc:
        await callback.message.answer(api_error_text(exc, lang))
    else:
        await render(callback, state, lang, web_app_url, view)
    await callback.answer()


async def _reload(event, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, flow_id: int) -> None:
    try:
        view = await api.room_get(event.from_user.id, flow_id)
    except ApiError as exc:
        await _msg(event).answer(api_error_text(exc, lang))
        return
    await render(event, state, lang, web_app_url, view)


# ------------------------------------------------------------------------------------------------ choice, photo, back

@router.callback_query(RoomPick.filter(F.a == "pick"))
async def pick(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    try:
        view = await api.room_get(callback.from_user.id, callback_data.f)
        step = view["descriptor"]["step"]
        if view["descriptor"]["kind"] != "choice":
            await render(callback, state, lang, web_app_url, view)
        else:
            await _submit(callback, state, api, lang, web_app_url, callback_data.f, step, callback_data.v)
    except ApiError as exc:
        await _fail(callback, state, api, lang, web_app_url, exc, callback_data.f)
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "back"))
async def go_back(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    try:
        view = await api.room_back(callback.from_user.id, callback_data.f)
    except ApiError as exc:
        await _fail(callback, state, api, lang, web_app_url, exc, callback_data.f)
    else:
        await render(callback, state, lang, web_app_url, view)
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "skip"))
async def skip_photo(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    await _submit(callback, state, api, lang, web_app_url, callback_data.f, "photo", {"skip": True})
    await callback.answer()


@router.message(RoomStates.photo, F.photo)
async def receive_photo(message: Message, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, max_upload_mb: int) -> None:
    flow_id = (await state.get_data()).get("flow_id")
    photo = message.photo[-1]
    try:
        content = await _download(message, photo.file_id, photo.file_size, max_upload_mb * 1024 * 1024)
        checked = check_upload(f"room_{photo.file_unique_id}.jpg", content, max_upload_mb * 1024 * 1024)
        view = await api.room_photo(message.from_user.id, flow_id, checked.filename, checked.content)
    except UploadRejected as exc:
        await message.answer(t(f"upload_rejected_{exc.reason}", lang), reply_markup=photo_keyboard(lang, flow_id))
        return
    except ApiError as exc:
        await _fail(message, state, api, lang, web_app_url, exc, flow_id)
        return
    await render(message, state, lang, web_app_url, view, say=_new_message)


@router.message(RoomStates.photo)
async def photo_expected(message: Message, state: FSMContext, lang: str) -> None:
    flow_id = (await state.get_data()).get("flow_id", 0)
    await message.answer(t("room_photo_wrong", lang), reply_markup=photo_keyboard(lang, flow_id))


# ------------------------------------------------------------------------------------------------ number_group forms

async def _ask_field(event, state: FSMContext, lang: str, say) -> None:
    data = await state.get_data()
    f, fid = data["fields"][data["idx"]], data["flow_id"]
    label = f["label"][lang]
    if f["type"] == "multi":
        await state.set_state(None)   # with no options the keyboard is only "Done", so the user can still move on
        await say(event, f"{data['head']}\n\n{t('room_ask_multi', lang, label=label)}", multi_keyboard(f["options"], data.get("selected", []), lang, fid))
    elif f["max"] - f["min"] <= 5:
        await state.set_state(None)
        await say(event, f"{data['head']}\n\n{t('room_ask_choice', lang, label=label)}", numbers_keyboard(f["min"], f["max"], fid))
    else:
        await state.set_state(RoomStates.number)
        await say(event, f"{data['head']}\n\n{t('room_ask_number', lang, label=label, lo=f['min'], hi=f['max'])}", cancel_keyboard(lang))


async def _field_value(event, state: FSMContext, lang: str, say, value, api=None, web_app_url: str = "") -> None:
    data = await state.get_data()
    values = {**data["values"], data["fields"][data["idx"]]["key"]: value}
    idx = data["idx"] + 1
    if idx < len(data["fields"]):
        await state.update_data(values=values, idx=idx, selected=[])
        await _ask_field(event, state, lang, say)
        return
    await state.clear()
    await _submit(event, state, api, lang, web_app_url, data["flow_id"], data["step"], values)


@router.callback_query(RoomPick.filter(F.a == "num"))
async def pick_number(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    if (await state.get_data()).get("mode") != "group":
        await _reload(callback, state, api, lang, web_app_url, callback_data.f)
    else:
        await _field_value(callback, state, lang, _say, int(callback_data.v), api, web_app_url)
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "tog"))
async def toggle(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    data = await state.get_data()
    if data.get("mode") != "group":
        await _reload(callback, state, api, lang, web_app_url, callback_data.f)
        await callback.answer()
        return
    selected = list(data.get("selected", []))
    selected.remove(callback_data.v) if callback_data.v in selected else selected.append(callback_data.v)
    await state.update_data(selected=selected)
    f = data["fields"][data["idx"]]
    await callback.message.edit_reply_markup(reply_markup=multi_keyboard(f["options"], selected, lang, data["flow_id"]))
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "multi_done"))
async def multi_done(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    data = await state.get_data()
    if data.get("mode") != "group":
        await _reload(callback, state, api, lang, web_app_url, callback_data.f)
    else:
        await _field_value(callback, state, lang, _say, list(data.get("selected", [])), api, web_app_url)
    await callback.answer()


# ------------------------------------------------------------------------------------------------ openings

def _what(data: dict, lang: str) -> str:
    kind = data["todo"][data["idx"]]
    n = sum(1 for k in data["todo"][:data["idx"] + 1] if k == kind)
    return t("room_opening_door" if kind == "door" else "room_opening_window", lang, n=n)


async def _ask_wall(event, state: FSMContext, lang: str, say) -> None:
    data = await state.get_data()
    await state.set_state(None)
    await say(event, t("room_ask_wall", lang, what=_what(data, lang)), walls_keyboard(data["walls"], lang, data["flow_id"]))


@router.callback_query(RoomPick.filter(F.a == "wall"))
async def pick_wall(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    data = await state.get_data()
    if data.get("mode") != "opening":
        await _reload(callback, state, api, lang, web_app_url, callback_data.f)
        await callback.answer()
        return
    wall = callback_data.v
    label = next(w["label"][lang] for w in data["walls"] if w["id"] == wall)
    await state.update_data(cur={"wall": wall}, phase="offset")
    await state.set_state(RoomStates.number)
    start = t("room_start_x" if wall in ("north", "south") else "room_start_z", lang)
    await callback.message.answer(t("room_ask_offset", lang, what=_what(data, lang), wall=label, start=start, length=data["wall_lengths"][wall]), reply_markup=cancel_keyboard(lang))
    await callback.answer()


async def _finish_opening(event, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, width: float) -> None:
    data = await state.get_data()
    kind, cur, room = data["todo"][data["idx"]], data["cur"], data["room"]
    top = room["height"] - 100                      # openings must end 100 mm below the ceiling
    if kind == "door":
        opening = {"type": "door", "wall": cur["wall"], "offset": cur["offset"], "width": width, "height": min(DOOR_DEFAULTS["height"], top), "sill": 0}
    else:
        sill = WINDOW_DEFAULTS["sill"]
        opening = {"type": "window", "wall": cur["wall"], "offset": cur["offset"], "width": width, "height": min(WINDOW_DEFAULTS["height"], top - sill), "sill": sill}
    done, idx = data["done"] + [opening], data["idx"] + 1
    if idx < len(data["todo"]):
        await state.update_data(done=done, idx=idx, cur={}, phase="wall")
        await _ask_wall(event, state, lang, _new_message)
        return
    await state.clear()
    await _submit(event, state, api, lang, web_app_url, data["flow_id"], "openings", done)


@router.callback_query(RoomPick.filter(F.a == "wdef"))
async def default_width(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    data = await state.get_data()
    if data.get("mode") != "opening" or data.get("phase") != "width":
        await _reload(callback, state, api, lang, web_app_url, callback_data.f)
    else:
        default = DOOR_DEFAULTS["width"] if data["todo"][data["idx"]] == "door" else WINDOW_DEFAULTS["width"]
        await _finish_opening(callback, state, api, lang, web_app_url, default)
    await callback.answer()


# ------------------------------------------------------------------------------------------------ typed numbers

@router.message(RoomStates.number, F.text)
async def receive_number(message: Message, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    data = await state.get_data()
    mode = data.get("mode")
    if mode == "group":
        f = data["fields"][data["idx"]]
        lo, hi, integer = f["min"], f["max"], False
    elif mode == "opening" and data["phase"] == "offset":
        lo, hi, integer = 0, data["wall_lengths"][data["cur"]["wall"]], False
    elif mode == "opening":
        kind = data["todo"][data["idx"]]
        lo, hi = data["limits"][kind]["width"]
        integer = False
    else:
        await message.answer(t("generic_error", lang))
        return
    try:
        value = parse_number(message.text or "", lo, hi, integer)
    except InvalidNumber:
        await message.answer(t("invalid_number", lang), reply_markup=cancel_keyboard(lang))
        return
    if mode == "group":
        await _field_value(message, state, lang, _new_message, value, api, web_app_url)
    elif data["phase"] == "offset":
        kind = data["todo"][data["idx"]]
        default = DOOR_DEFAULTS["width"] if kind == "door" else WINDOW_DEFAULTS["width"]
        await state.update_data(cur={**data["cur"], "offset": value}, phase="width")
        await message.answer(t("room_ask_width", lang, what=_what(data, lang), value=default), reply_markup=width_keyboard(lang, data["flow_id"]))
    else:
        await _finish_opening(message, state, api, lang, web_app_url, value)


# ------------------------------------------------------------------------------------------------ furnish

async def _fresh(event, api: BackendClient, flow_id: int) -> dict:
    return await api.room_get(event.from_user.id, flow_id)


async def _edit(event, state: FSMContext, api: BackendClient, lang: str, web_app_url: str, flow_id: int, op, notice: str | None = None) -> None:
    """Run one furniture change with the room revision the server holds now; retry once if somebody changed the room meanwhile."""
    try:
        for attempt in (0, 1):
            view = await _fresh(event, api, flow_id)
            try:
                result = await op(view)
                break
            except ApiError as exc:
                if exc.code != "rev_conflict" or attempt:
                    raise
        view = await _fresh(event, api, flow_id)
        view["warnings"] = result.get("warnings", [])
    except ApiError as exc:
        await _fail(event, state, api, lang, web_app_url, exc, flow_id)
        return
    if notice:
        await _msg(event).answer(notice)
    await render(event, state, lang, web_app_url, view, say=_new_message)


@router.callback_query(RoomPick.filter(F.a == "addmenu"))
async def add_menu(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    try:
        view = await _fresh(callback, api, callback_data.f)
    except ApiError as exc:
        await _fail(callback, state, api, lang, web_app_url, exc, callback_data.f)
    else:
        await _say(callback, t("room_pick_furniture", lang), catalog_keyboard(view["descriptor"].get("catalog", []), lang, callback_data.f))
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "list"))
async def show_list(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    await _reload(callback, state, api, lang, web_app_url, callback_data.f)
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "add"))
async def add_item(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    tg, fid, slug = callback.from_user.id, callback_data.f, callback_data.v

    async def op(view):
        return await api.room_add_item(tg, fid, view["rev"], template=slug)

    await _edit(callback, state, api, lang, web_app_url, fid, op, notice=t("room_added", lang, name=slug))
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "sel"))
async def select_item(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    try:
        view = await _fresh(callback, api, callback_data.f)
    except ApiError as exc:
        await _fail(callback, state, api, lang, web_app_url, exc, callback_data.f)
        await callback.answer()
        return
    items = view.get("items", [])
    idx = next((i for i, it in enumerate(items) if it["id"] == callback_data.v), None)
    if idx is None:
        await render(callback, state, lang, web_app_url, view)
    else:
        await _say(callback, t("room_item_selected", lang, line=item_line(idx + 1, items[idx], view, lang)), item_keyboard(callback_data.v, lang, callback_data.f))
    await callback.answer()


def _item_of(view: dict, item_id: str) -> dict:
    return next((i for i in view.get("items", []) if i["id"] == item_id), {})


@router.callback_query(RoomPick.filter(F.a.in_({"mvw", "mve", "mvn", "mvs"})))
async def move_item(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    item_id = callback_data.v
    axis, delta = MOVES[callback_data.a[2]]
    tg, fid = callback.from_user.id, callback_data.f

    async def op(view):
        item = _item_of(view, item_id)
        return await api.room_update_item(tg, fid, item_id, view["rev"], **{axis: item[axis] + delta})

    await _edit_item(callback, state, api, lang, web_app_url, fid, item_id, op)


@router.callback_query(RoomPick.filter(F.a == "rot"))
async def rotate_item(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    item_id, tg, fid = callback_data.v, callback.from_user.id, callback_data.f

    async def op(view):
        return await api.room_update_item(tg, fid, item_id, view["rev"], rot=(_item_of(view, item_id)["rot"] + 90) % 360)

    await _edit_item(callback, state, api, lang, web_app_url, fid, item_id, op)


async def _edit_item(callback: CallbackQuery, state, api, lang, web_app_url, flow_id: int, item_id: str, op) -> None:
    """Like _edit, but stays on the selected item so the user can keep nudging it."""
    try:
        for attempt in (0, 1):
            view = await _fresh(callback, api, flow_id)
            try:
                await op(view)
                break
            except ApiError as exc:
                if exc.code != "rev_conflict" or attempt:
                    raise
        view = await _fresh(callback, api, flow_id)
    except ApiError as exc:
        await _fail(callback, state, api, lang, web_app_url, exc, None)
        await callback.answer()
        return
    items = view.get("items", [])
    idx = next((i for i, it in enumerate(items) if it["id"] == item_id), None)
    if idx is not None:
        await _say(callback, t("room_item_selected", lang, line=item_line(idx + 1, items[idx], view, lang)), item_keyboard(item_id, lang, flow_id))
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "del"))
async def delete_item(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    item_id, tg, fid = callback_data.v, callback.from_user.id, callback_data.f

    async def op(view):
        return await api.room_delete_item(tg, fid, item_id, view["rev"])

    await _edit(callback, state, api, lang, web_app_url, fid, op, notice=t("room_removed", lang))
    await callback.answer()


@router.callback_query(RoomPick.filter(F.a == "done"))
async def finish(callback: CallbackQuery, callback_data: RoomPick, state: FSMContext, api: BackendClient, lang: str, web_app_url: str) -> None:
    await _submit(callback, state, api, lang, web_app_url, callback_data.f, "furnish", {"done": True})
    await callback.answer()
