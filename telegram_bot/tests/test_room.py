import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import room
from bot.keyboards import room as kb
from bot.keyboards.room import RoomPick
from bot.services.api import ApiError, BackendClient
from bot.states import RoomStates
from bot.utils.i18n import TEXTS, t
from tests.helpers import fake_callback, fake_message

WEB = "https://mebelchi.example"
L3 = lambda en, uz=None, ru=None: {"en": en, "uz": uz or en, "ru": ru or en}  # noqa: E731


def descriptor(step, kind, **extra):
    return {"step": step, "kind": kind, "title": L3(step.title()), "prompt": L3(f"Prompt for {step}"), "index": 1, "total": 7, "can_back": True, "optional": False, "value": None, **extra}


def flow_view(step, kind, fid=7, status="active", items=None, rev=None, warnings=None, answers=None, **extra):
    v = {"id": fid, "status": status, "step": step, "descriptor": descriptor(step, kind, **extra), "answers": answers or {}, "design_id": None, "photo_id": None, "rev": rev,
         "warnings": warnings or []}
    if items is not None:
        v["items"] = items
    return v


GOAL = flow_view("goal", "choice", options=[{"id": "kitchen", "label": L3("Kitchen", "Oshxona", "Кухня")}, {"id": "bedroom", "label": L3("Bedroom", "Yotoqxona", "Спальня")}], can_back=False)
ELEMENTS = flow_view("elements", "number_group", fields=[
    {"key": "doors", "type": "number", "label": L3("Doors", "Eshiklar", "Двери"), "min": 0, "max": 2},
    {"key": "windows", "type": "number", "label": L3("Windows"), "min": 0, "max": 4},
    {"key": "furniture", "type": "multi", "label": L3("Furniture"), "options": [{"id": "bedside", "label": L3("Bedside table")}, {"id": "dresser", "label": L3("Dresser")}]}])
SIZE = flow_view("size", "number_group", fields=[{"key": k, "type": "number", "label": L3(k.title()), "min": lo, "max": hi}
                                                 for k, lo, hi in (("width", 1000, 15000), ("length", 1000, 15000), ("height", 2000, 4500))])
WALLS = [{"id": w, "label": L3(w.title())} for w in ("north", "east", "south", "west")]


def openings_view(doors=1, windows=1, height=2700):
    return flow_view("openings", "openings", required={"doors": doors, "windows": windows}, room={"width": 4000, "length": 3000, "height": height}, walls=WALLS,
                     wall_lengths={"north": 4000, "east": 3000, "south": 4000, "west": 3000}, limits={"door": {"width": [600, 1200]}, "window": {"width": [300, 3000]}})


ITEM = {"id": "a1b2c3d4e5f6", "template": "bedside", "name": "Bedside table", "x": 100, "z": 0, "rot": 0, "width": 450, "depth": 400, "height": 500, "shelves": 0, "doors": 0, "drawers": 2}
CATALOG = [{"slug": "bedside", "category": "bedroom", "label": L3("Bedside table", "Tumba", "Тумба"), "name": "Bedside table", "defaults": {}}]


def furnish_view(items=(ITEM,), rev=3, **kw):
    return flow_view("furnish", "furnish", rev=rev, items=list(items), catalog=CATALOG, **kw)


def make_api(**returns) -> AsyncMock:
    api = AsyncMock(spec=BackendClient)
    for name, value in returns.items():
        getattr(api, name).return_value = value
    return api


def fsm(user=42) -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=user, user_id=user))


def _calls(event):
    """Every text sent for this event: replies to a message, or edits/answers on the message a button belongs to."""
    targets = [event]
    if isinstance(getattr(event, "message", None), AsyncMock):
        targets.append(event.message)
    return [c for o in targets for name in ("edit_text", "answer") for c in getattr(o, name).await_args_list if c.args]


def texts(event) -> list[str]:
    return [c.args[0] for c in _calls(event)]


def last_markup(event):
    return [c for c in _calls(event) if "reply_markup" in c.kwargs][-1].kwargs["reply_markup"]


def buttons(markup) -> list[tuple[str, str]]:
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row if b.callback_data]


def pick(a, v="", f=7) -> RoomPick:
    return RoomPick(a=a, v=v, f=f)


async def press(handler, callback, data, state, api, lang="en"):
    await handler(callback, data, state, api, lang, WEB)


# ------------------------------------------------------------------------------------------------ keyboards

def test_every_callback_fits_telegram_limit():
    worst_flow = 2_000_000_000
    long_option = {"id": "x" * 24, "label": L3("A very long furniture name that gets truncated by the keyboard builder")}
    item = {**ITEM, "id": "f" * 12}
    boards = [kb.resume_keyboard("ru", worst_flow), kb.choice_keyboard([long_option] * 6, "uz", worst_flow, True), kb.numbers_keyboard(0, 4, worst_flow),
              kb.multi_keyboard([long_option] * 6, [long_option["id"]], "ru", worst_flow), kb.photo_keyboard("en", worst_flow), kb.walls_keyboard(WALLS, "en", worst_flow),
              kb.width_keyboard("en", worst_flow), kb.furnish_keyboard([item] * 25, "en", worst_flow, WEB), kb.item_keyboard(item["id"], "ru", worst_flow),
              kb.catalog_keyboard([{"slug": "y" * 24, "label": L3("x")}] * 10, "en", worst_flow), kb.done_keyboard("en", WEB)]
    for board in boards:
        for _, data in buttons(board):
            assert len(data.encode()) <= 64, data


def test_callback_data_round_trips():
    packed = RoomPick(a="mve", v="a1b2c3d4e5f6", f=123).pack()
    assert RoomPick.unpack(packed) == RoomPick(a="mve", v="a1b2c3d4e5f6", f=123)


def test_furnish_keyboard_limits_the_item_list_and_has_a_web_link():
    board = kb.furnish_keyboard([{**ITEM, "id": f"{i:012x}"} for i in range(60)], "en", 7, WEB)
    assert len([b for b in buttons(board) if RoomPick.unpack(b[1]).a == "sel"]) == 20
    assert any(b.url == f"{WEB}/x" for row in kb.furnish_keyboard([], "en", 7, f"{WEB}/x").inline_keyboard for b in row)
    assert not any(b.url for row in kb.furnish_keyboard([], "en", 7, None).inline_keyboard for b in row)


def test_every_room_text_key_used_in_code_exists_in_every_language():
    source = "".join(p.read_text() for p in Path(room.__file__).parent.parent.rglob("*.py") if "room" in p.name)
    used = set(re.findall(r't\(\s*["\'](room_[a-z_]+|btn_room)["\']', source)) | set(re.findall(r'["\'](room_[a-z_]+)["\']', source))
    used = {k for k in used if not k.startswith("room_goal_")}
    for lang in TEXTS:
        assert {k for k in used if k not in TEXTS[lang] and not k.endswith(("_", "pick"))} == set(), lang
    for lang in TEXTS:
        for goal in ("kitchen", "bedroom", "living", "wardrobe", "office", "other"):
            assert f"room_goal_{goal}" in TEXTS[lang]


def test_texts_keep_their_placeholders_in_every_language():
    placeholders = lambda s: set(re.findall(r"{(\w+)}", s))  # noqa: E731
    for key in (k for k in TEXTS["en"] if k.startswith("room_")):
        assert {lang: placeholders(TEXTS[lang][key]) for lang in TEXTS}["uz"] == placeholders(TEXTS["en"][key]) == placeholders(TEXTS["ru"][key]), key


# ------------------------------------------------------------------------------------------------ entry and resume

async def test_new_user_gets_the_first_question():
    api = make_api(room_start=(GOAL, True))
    state, msg = fsm(), fake_message("/room")
    await room.start_room(msg, state, api, "uz", WEB)
    api.room_start.assert_awaited_once_with(42)
    assert "Prompt for goal" in texts(msg)[-1]
    assert [RoomPick.unpack(d).v for _, d in buttons(last_markup(msg))] == ["kitchen", "bedroom"]       # no back button on the first step
    assert [text for text, _ in buttons(last_markup(msg))] == ["Oshxona", "Yotoqxona"]                  # labels follow the language


async def test_unfinished_flow_asks_continue_or_new():
    api = make_api(room_start=(flow_view("size", "number_group", answers={"goal": "kitchen"}, fields=SIZE["descriptor"]["fields"]), False))
    msg = fake_message("/room")
    await room.start_room(msg, fsm(), api, "en", WEB)
    assert "unfinished" in texts(msg)[-1]
    assert [RoomPick.unpack(d).a for _, d in buttons(last_markup(msg))] == ["resume", "new"]


async def test_resume_continues_on_the_servers_step_even_with_an_empty_fsm():
    api = make_api(room_get=SIZE)
    cb = fake_callback()
    await room.resume(cb, pick("resume"), fsm(), api, "en", WEB)        # fresh FSM: the bot was restarted
    api.room_get.assert_awaited_once_with(42, 7)
    assert "Prompt for size" in " ".join(texts(cb))


async def test_new_discards_the_old_flow():
    api = make_api(room_start=(GOAL, True))
    cb = fake_callback()
    await room.start_new(cb, fsm(), api, "en", WEB)
    api.room_start.assert_awaited_once_with(42, new=True)


async def test_backend_down_is_reported_not_raised():
    api = AsyncMock(spec=BackendClient)
    api.room_start.side_effect = ApiError(503, "backend_unavailable", "down")
    msg = fake_message("/room")
    await room.start_room(msg, fsm(), api, "en", WEB)
    assert texts(msg)[-1] == t("backend_unavailable", "en")


async def test_closed_flow_is_not_shown_as_a_question():
    cb = fake_callback()
    api = make_api(room_get=flow_view("goal", "choice", status="abandoned", options=[]))
    await room.resume(cb, pick("resume"), fsm(), api, "en", WEB)
    assert t("room_closed", "en") in " ".join(texts(cb))


# ------------------------------------------------------------------------------------------------ choice and back

async def test_picking_an_option_answers_the_current_step():
    api = make_api(room_get=GOAL, room_answer=flow_view("photo", "photo"))
    cb = fake_callback()
    await press(room.pick, cb, pick("pick", "kitchen"), fsm(), api)
    api.room_answer.assert_awaited_once_with(42, 7, "goal", "kitchen")


async def test_stale_button_does_not_answer_the_wrong_step():
    api = make_api(room_get=SIZE, room_answer=SIZE)       # the server is already at "size"; the pressed button belonged to "goal"
    cb = fake_callback()
    await press(room.pick, cb, pick("pick", "kitchen"), fsm(), api)
    api.room_answer.assert_not_awaited()


async def test_back_shows_the_previous_step():
    api = make_api(room_back=GOAL)
    cb = fake_callback()
    await press(room.go_back, cb, pick("back"), fsm(), api)
    api.room_back.assert_awaited_once_with(42, 7)


async def test_style_screen_lists_the_descriptions():
    view = flow_view("style", "choice", options=[{"id": "modern", "label": L3("Modern"), "text": L3("Clean lines"), "furniture": "#fff", "wall": "#eee"}])
    api = make_api(room_get=view)
    cb = fake_callback()
    await room.resume(cb, pick("resume"), fsm(), api, "en", WEB)
    assert "Clean lines" in " ".join(texts(cb))


# ------------------------------------------------------------------------------------------------ photo

async def test_photo_step_waits_for_a_photo_and_can_be_skipped():
    state, cb = fsm(), fake_callback()
    api = make_api(room_get=flow_view("photo", "photo"), room_answer=ELEMENTS)
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    assert await state.get_state() == RoomStates.photo.state
    assert (await state.get_data())["flow_id"] == 7
    assert [RoomPick.unpack(d).a for _, d in buttons(last_markup(cb))] == ["skip", "back"]
    await press(room.skip_photo, cb, pick("skip"), state, api)
    api.room_answer.assert_awaited_with(42, 7, "photo", {"skip": True})


async def test_photo_is_downloaded_validated_and_sent(monkeypatch):
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 32      # Telegram always sends photos as JPEG
    monkeypatch.setattr(room, "_download", AsyncMock(return_value=jpeg))
    state, msg = fsm(), fake_message()
    msg.photo = [SimpleNamespace(file_id="small", file_unique_id="u1", file_size=10), SimpleNamespace(file_id="big", file_unique_id="u2", file_size=999)]
    await state.set_state(RoomStates.photo)
    await state.update_data(flow_id=7)
    api = make_api(room_photo=ELEMENTS)
    await room.receive_photo(msg, state, api, "en", WEB, 10)
    assert room._download.await_args.args[1] == "big"                          # the largest size
    api.room_photo.assert_awaited_once_with(42, 7, "room_u2.jpg", jpeg)


async def test_a_fake_photo_is_rejected_before_the_backend(monkeypatch):
    monkeypatch.setattr(room, "_download", AsyncMock(return_value=b"MZ definitely not a jpeg"))
    state, msg = fsm(), fake_message()
    msg.photo = [SimpleNamespace(file_id="x", file_unique_id="u", file_size=10)]
    await state.update_data(flow_id=7)
    api = make_api()
    await room.receive_photo(msg, state, api, "en", WEB, 10)
    api.room_photo.assert_not_awaited()
    assert texts(msg)[-1] == t("upload_rejected_content_mismatch", "en")


async def test_text_while_waiting_for_a_photo_gets_a_hint():
    state, msg = fsm(), fake_message("hello")
    await state.update_data(flow_id=7)
    await room.photo_expected(msg, state, "en")
    assert texts(msg)[-1] == t("room_photo_wrong", "en")


# ------------------------------------------------------------------------------------------------ number_group forms

async def drive_elements(api, doors=1, windows=2, furniture=("bedside",)):
    state, cb = fsm(), fake_callback()
    api.room_get.return_value = ELEMENTS
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    await press(room.pick_number, cb, pick("num", str(doors)), state, api)
    await press(room.pick_number, cb, pick("num", str(windows)), state, api)
    for f in furniture:
        await press(room.toggle, cb, pick("tog", f), state, api)
    await press(room.multi_done, cb, pick("multi_done"), state, api)
    return state, cb


async def test_elements_form_collects_counts_and_furniture_then_submits_once():
    api = make_api(room_answer=SIZE)
    state, cb = await drive_elements(api, doors=1, windows=2, furniture=("bedside", "dresser"))
    api.room_answer.assert_awaited_once_with(42, 7, "elements", {"doors": 1, "windows": 2, "furniture": ["bedside", "dresser"]})
    data = await state.get_data()
    assert (data["step"], data["idx"], data["values"]) == ("size", 0, {})            # the finished form is gone; the next step's form has started
    assert await state.get_state() == RoomStates.number.state


async def test_small_ranges_are_buttons_and_large_ranges_are_typed():
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, make_api(room_get=ELEMENTS), "en", WEB)
    assert [d for _, d in buttons(last_markup(cb))] == [RoomPick(a="num", v=str(i), f=7).pack() for i in range(0, 3)]
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, make_api(room_get=SIZE), "en", WEB)
    assert await state.get_state() == RoomStates.number.state
    assert "from 1000 to 15000" in " ".join(texts(cb))


async def test_toggle_marks_and_unmarks_furniture():
    api = make_api(room_get=ELEMENTS)
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    await press(room.pick_number, cb, pick("num", "0"), state, api)
    await press(room.pick_number, cb, pick("num", "0"), state, api)
    await press(room.toggle, cb, pick("tog", "dresser"), state, api)
    assert (await state.get_data())["selected"] == ["dresser"]
    assert any(text.startswith("[x]") for text, _ in buttons(cb.message.edit_reply_markup.await_args.kwargs["reply_markup"]))
    await press(room.toggle, cb, pick("tog", "dresser"), state, api)
    assert (await state.get_data())["selected"] == []


async def test_size_form_accepts_decimals_and_submits_numbers():
    api = make_api(room_get=SIZE, room_answer=openings_view())
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    for text in ("4000", "3000,5", "2700"):
        await room.receive_number(fake_message(text), state, api, "en", WEB)
    api.room_answer.assert_awaited_once_with(42, 7, "size", {"width": 4000, "length": 3000.5, "height": 2700})


@pytest.mark.parametrize("bad", ["abc", "999", "15001", "", "1e999", "nan", "4 000"])
async def test_size_form_rejects_bad_numbers_and_asks_again(bad):
    api = make_api(room_get=SIZE)
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    msg = fake_message(bad)
    await room.receive_number(msg, state, api, "en", WEB)
    assert texts(msg)[-1] == t("invalid_number", "en")
    assert (await state.get_data())["idx"] == 0
    api.room_answer.assert_not_awaited()


async def test_server_rejection_is_shown_and_the_step_is_asked_again():
    api = make_api(room_get=SIZE)
    api.room_answer.side_effect = ApiError(400, "error", "Validation failed.", {"width": ["must be between 1000 and 15000 mm"]})
    state, cb = fsm(), fake_callback()
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    msg = fake_message()
    for text in ("4000", "3000", "2700"):
        msg = fake_message(text)
        await room.receive_number(msg, state, api, "en", WEB)
    shown = " ".join(texts(msg))
    assert "width: must be between 1000 and 15000 mm" in shown
    assert await state.get_state() == RoomStates.number.state            # asking from the first field again


async def test_stale_button_without_form_data_reloads_the_real_step():
    api = make_api(room_get=SIZE)
    cb = fake_callback()
    await press(room.pick_number, cb, pick("num", "1"), fsm(), api)       # empty FSM
    api.room_get.assert_awaited_once_with(42, 7)
    api.room_answer.assert_not_awaited()


# ------------------------------------------------------------------------------------------------ openings

async def run_openings(view, api, steps):
    state, cb = fsm(), fake_callback()
    api.room_get.return_value = view
    await room.resume(cb, pick("resume"), state, api, "en", WEB)
    for kind, value in steps:
        if kind == "wall":
            await press(room.pick_wall, cb, pick("wall", value), state, api)
        elif kind == "text":
            await room.receive_number(fake_message(value), state, api, "en", WEB)
        else:
            await press(room.default_width, cb, pick("wdef"), state, api)
    return state


async def test_openings_are_collected_with_default_sizes():
    api = make_api(room_answer=flow_view("style", "choice", options=[]))
    await run_openings(openings_view(), api, [("wall", "north"), ("text", "1000"), ("default", None), ("wall", "east"), ("text", "800"), ("text", "1500")])
    api.room_answer.assert_awaited_once_with(42, 7, "openings", [
        {"type": "door", "wall": "north", "offset": 1000, "width": 900, "height": 2100, "sill": 0},
        {"type": "window", "wall": "east", "offset": 800, "width": 1500, "height": 1200, "sill": 900}])


async def test_default_heights_stay_100_mm_below_a_low_ceiling():
    api = make_api(room_answer=flow_view("style", "choice", options=[]))
    await run_openings(openings_view(height=2000), api, [("wall", "north"), ("text", "500"), ("default", None), ("wall", "south"), ("text", "500"), ("default", None)])
    door, window = api.room_answer.await_args.args[3]
    assert door["height"] == 1900 and window["sill"] + window["height"] <= 1900 and window["height"] >= 300


async def test_offset_is_limited_to_the_wall_and_the_width_to_the_opening_limits():
    api = make_api(room_answer=flow_view("style", "choice", options=[]))
    state = await run_openings(openings_view(doors=1, windows=0), api, [("wall", "east")])
    msg = fake_message("3001")                                            # the east wall is 3000 long
    await room.receive_number(msg, state, api, "en", WEB)
    assert texts(msg)[-1] == t("invalid_number", "en")
    await room.receive_number(fake_message("100"), state, api, "en", WEB)
    msg = fake_message("1300")                                            # doors are 600-1200 wide
    await room.receive_number(msg, state, api, "en", WEB)
    assert texts(msg)[-1] == t("invalid_number", "en")
    api.room_answer.assert_not_awaited()


async def test_a_single_door_submits_after_its_width():
    api = make_api(room_answer=flow_view("style", "choice", options=[]))
    await run_openings(openings_view(doors=1, windows=0), api, [("wall", "south"), ("text", "200"), ("text", "800")])
    api.room_answer.assert_awaited_once_with(42, 7, "openings", [{"type": "door", "wall": "south", "offset": 200, "width": 800, "height": 2100, "sill": 0}])


# ------------------------------------------------------------------------------------------------ furnish

async def test_furnish_lists_items_and_warnings():
    view = furnish_view(warnings=[{"code": "door_zone", "item": ITEM["id"]}, {"code": "not_placed", "item": "bedside"}, {"code": "items_reset"}])
    cb = fake_callback()
    await room.resume(cb, pick("resume"), fsm(), make_api(room_get=view), "en", WEB)
    shown = " ".join(texts(cb))
    assert "1. Bedside table, 450 x 400 x 500 mm, x=100, z=0, 0 deg" in shown
    assert "blocks the area in front of a door" in shown and "did not fit" in shown and "rebuilt" in shown
    actions = [RoomPick.unpack(d).a for _, d in buttons(last_markup(cb))]
    assert actions == ["sel", "addmenu", "done", "back"]


async def test_empty_room_says_so():
    cb = fake_callback()
    await room.resume(cb, pick("resume"), fsm(), make_api(room_get=furnish_view(items=[])), "uz", WEB)
    assert t("room_no_items", "uz") in " ".join(texts(cb))


async def test_adding_furniture_uses_the_current_revision():
    api = make_api(room_get=furnish_view(rev=3))
    api.room_add_item.return_value = {"rev": 4, "item": ITEM, "items": [ITEM], "warnings": []}
    cb = fake_callback()
    await press(room.add_item, cb, pick("add", "bedside"), fsm(), api)
    api.room_add_item.assert_awaited_once_with(42, 7, 3, template="bedside")


async def test_a_revision_conflict_is_retried_once_with_fresh_data():
    api = make_api()
    api.room_get.side_effect = [furnish_view(rev=3), furnish_view(rev=4), furnish_view(rev=5)]
    api.room_add_item.side_effect = [ApiError(409, "rev_conflict", "changed", {"code": "rev_conflict", "current_rev": 4}), {"rev": 5, "items": [ITEM], "warnings": []}]
    cb = fake_callback()
    await press(room.add_item, cb, pick("add", "bedside"), fsm(), api)
    assert [c.args[2] for c in api.room_add_item.await_args_list] == [3, 4]


async def test_a_second_conflict_is_reported():
    api = make_api(room_get=furnish_view(rev=3))
    api.room_add_item.side_effect = ApiError(409, "rev_conflict", "changed", {"code": "rev_conflict", "current_rev": 9})
    cb = fake_callback()
    await press(room.add_item, cb, pick("add", "bedside"), fsm(), api)
    assert api.room_add_item.await_count == 2
    assert t("room_conflict", "en") in str(cb.message.answer.await_args_list)


@pytest.mark.parametrize("direction,fields", [("w", {"x": 0}), ("e", {"x": 200}), ("n", {"z": -100}), ("s", {"z": 100})])
async def test_move_buttons_nudge_by_100_mm(direction, fields):
    api = make_api(room_get=furnish_view(rev=3))
    api.room_update_item.return_value = {"rev": 4}
    await press(room.move_item, fake_callback(), pick(f"mv{direction}", ITEM["id"]), fsm(), api)
    api.room_update_item.assert_awaited_once_with(42, 7, ITEM["id"], 3, **fields)


async def test_rotate_adds_90_degrees_and_wraps():
    api = make_api(room_get=furnish_view(items=[{**ITEM, "rot": 270}], rev=3), room_update_item={"rev": 4})
    await press(room.rotate_item, fake_callback(), pick("rot", ITEM["id"]), fsm(), api)
    assert api.room_update_item.await_args.kwargs == {"rot": 0}


async def test_a_move_the_server_refuses_shows_the_reason_and_the_list():
    api = make_api(room_get=furnish_view(rev=3))
    api.room_update_item.side_effect = ApiError(400, "error", "Validation failed.", {"position": ["item must stay inside the room"]})
    cb = fake_callback()
    await press(room.move_item, cb, pick("mvw", ITEM["id"]), fsm(), api)
    assert "position: item must stay inside the room" in str(cb.message.answer.await_args_list)


async def test_remove_calls_delete_with_the_revision():
    api = make_api(room_get=furnish_view(rev=3), room_delete_item={"rev": 4, "items": [], "warnings": []})
    await press(room.delete_item, fake_callback(), pick("del", ITEM["id"]), fsm(), api)
    api.room_delete_item.assert_awaited_once_with(42, 7, ITEM["id"], 3)


async def test_selecting_an_item_shows_its_controls():
    cb = fake_callback()
    await press(room.select_item, cb, pick("sel", ITEM["id"]), fsm(), make_api(room_get=furnish_view()))
    assert "Selected: 1. Bedside table" in texts(cb)[-1]
    assert [RoomPick.unpack(d).a for _, d in buttons(last_markup(cb))] == ["mvw", "mve", "mvn", "mvs", "rot", "del", "list"]


async def test_add_menu_offers_the_catalog():
    cb = fake_callback()
    await press(room.add_menu, cb, pick("addmenu"), fsm(), make_api(room_get=furnish_view()))
    assert [(t_, RoomPick.unpack(d).v) for t_, d in buttons(last_markup(cb))][0] == ("Bedside table", "bedside")


async def test_finishing_shows_the_saved_summary_with_a_disclaimer():
    done = flow_view("done", "summary", status="completed", items=[ITEM], answers={"goal": "kitchen", "size": {"width": 4000, "length": 3000, "height": 2700}})
    api = make_api(room_answer=done)
    cb = fake_callback()
    await press(room.finish, cb, pick("done"), fsm(), api)
    api.room_answer.assert_awaited_once_with(42, 7, "furnish", {"done": True})
    shown = " ".join(texts(cb))
    assert "kitchen, 4000 x 3000 x 2700 mm, 1 item(s)" in shown and t("calc_disclaimer", "en") in shown


async def test_closed_flow_in_the_middle_of_editing_is_reported():
    api = make_api(room_get=furnish_view())
    api.room_add_item.side_effect = ApiError(409, "not_active", "closed", {"code": "not_active"})
    cb = fake_callback()
    await press(room.add_item, cb, pick("add", "bedside"), fsm(), api)
    assert t("room_closed", "en") in str(cb.message.answer.await_args_list)


def test_item_line_falls_back_to_the_catalog_label_and_the_id():
    view = furnish_view()
    assert room.item_line(1, {**ITEM, "name": ""}, view, "uz").startswith("1. Tumba")
    assert room.item_line(2, {**ITEM, "name": "", "template": ""}, view, "en").startswith(f"2. {ITEM['id']}")
