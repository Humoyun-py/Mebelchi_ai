"""Inline keyboards for the room-design flow. Telegram limits callback data to 64 bytes, so values stay short:
`a` is the action, `v` its value (an option id or an item id), `f` the flow id the button belongs to."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


class RoomPick(CallbackData, prefix="room"):
    a: str
    v: str = ""
    f: int = 0


def _b(text: str, a: str, v: str = "", f: int = 0) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text[:60], callback_data=RoomPick(a=a, v=v, f=f).pack())


def _pairs(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def _back(lang: str, f: int, can_back: bool) -> list[list[InlineKeyboardButton]]:
    return [[_b(t("btn_back", lang), "back", f=f)]] if can_back else []


def resume_keyboard(lang: str, flow_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t("room_continue", lang), "resume", f=flow_id)], [_b(t("room_new", lang), "new", f=flow_id)]])


def choice_keyboard(options: list[dict], lang: str, flow_id: int, can_back: bool) -> InlineKeyboardMarkup:
    rows = _pairs([_b(o["label"][lang], "pick", o["id"], flow_id) for o in options])
    return InlineKeyboardMarkup(inline_keyboard=rows + _back(lang, flow_id, can_back))


def numbers_keyboard(lo: int, hi: int, flow_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(str(i), "num", str(i), flow_id) for i in range(lo, hi + 1)]])


def multi_keyboard(options: list[dict], selected: list[str], lang: str, flow_id: int) -> InlineKeyboardMarkup:
    rows = [[_b(("[x] " if o["id"] in selected else "[ ] ") + o["label"][lang], "tog", o["id"], flow_id)] for o in options]
    rows.append([_b(t("room_ready", lang), "multi_done", f=flow_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def photo_keyboard(lang: str, flow_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t("room_skip", lang), "skip", f=flow_id)], [_b(t("btn_back", lang), "back", f=flow_id)]])


def walls_keyboard(walls: list[dict], lang: str, flow_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=_pairs([_b(w["label"][lang], "wall", w["id"], flow_id) for w in walls]))


def width_keyboard(lang: str, flow_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_b(t("room_default", lang), "wdef", f=flow_id)]])


def furnish_keyboard(items: list[dict], lang: str, flow_id: int, web_url: str | None) -> InlineKeyboardMarkup:
    rows = [[_b(f"{i + 1}. {it['name'] or it['template'] or it['id']}", "sel", it["id"], flow_id)] for i, it in enumerate(items[:20])]
    rows.append([_b(t("room_add", lang), "addmenu", f=flow_id)])
    if web_url:
        rows.append([InlineKeyboardButton(text=t("room_open_web", lang), url=web_url)])
    rows.append([_b(t("room_done", lang), "done", f=flow_id), _b(t("btn_back", lang), "back", f=flow_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def item_keyboard(item_id: str, lang: str, flow_id: int) -> InlineKeyboardMarkup:
    move = lambda key, d: _b(t(key, lang), f"mv{d}", item_id, flow_id)  # noqa: E731  (one action per direction: ":" is not allowed inside callback values)
    return InlineKeyboardMarkup(inline_keyboard=[
        [move("room_move_w", "w"), move("room_move_e", "e")], [move("room_move_n", "n"), move("room_move_s", "s")],
        [_b(t("room_rotate", lang), "rot", item_id, flow_id), _b(t("room_remove", lang), "del", item_id, flow_id)],
        [_b(t("room_list", lang), "list", f=flow_id)]])


def catalog_keyboard(catalog: list[dict], lang: str, flow_id: int) -> InlineKeyboardMarkup:
    rows = _pairs([_b(c["label"][lang], "add", c["slug"], flow_id) for c in catalog])
    rows.append([_b(t("room_list", lang), "list", f=flow_id)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def done_keyboard(lang: str, web_url: str | None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t("room_open_web", lang), url=web_url)]] if web_url else []
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
