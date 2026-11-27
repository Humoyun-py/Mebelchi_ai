from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.i18n import t


class Nav(CallbackData, prefix="nav"):
    to: str


class ProjectAction(CallbackData, prefix="prj"):
    action: str  # "rename"
    project_id: int


class OrderAct(CallbackData, prefix="ord"):
    # "view" | "acc" (accept) | "rej" (reject, asks for a reason) | "to_<status>" (any other move the server allows)
    action: str
    order_id: int


class PickProject(CallbackData, prefix="pick"):
    project_id: int  # 0 means no project


class ExportFile(CallbackData, prefix="exp"):
    kind: str  # "pdf" | "xlsx"
    list_id: int


def _button(text: str, to: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=Nav(to=to).pack())


def main_menu(lang: str, linked: bool, workshop: bool = False) -> InlineKeyboardMarkup:
    if not linked:
        return InlineKeyboardMarkup(inline_keyboard=[
            [_button(t("btn_link", lang), "link")],
            [_button(t("btn_help", lang), "help")],
        ])
    rows = [
        [_button(t("btn_profile", lang), "profile"), _button(t("btn_projects", lang), "projects")],
        [_button(t("btn_create", lang), "new_project"), _button(t("btn_calc", lang), "calc")],
        [_button(t("btn_cutting", lang), "cutting"), _button(t("btn_designs", lang), "designs")],
        [_button(t("btn_upload", lang), "upload"), _button(t("btn_notifications", lang), "notifications")],
        [_button(t("btn_help", lang), "help"), InlineKeyboardButton(text=t("btn_web", lang), callback_data=Nav(to="web").pack())],
        [_button(t("btn_unlink", lang), "unlink")],
    ]
    if workshop:
        rows.insert(0, [_button(t("btn_orders", lang), "orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button(t("btn_cancel", lang), "cancel")]])


def back_to_menu(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_button(t("btn_back", lang), "menu")]])


def projects_keyboard(projects: list[dict], lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{p['name'][:40]}", callback_data=ProjectAction(action="rename", project_id=p["id"]).pack())]
            for p in projects]
    rows.append([_button(t("btn_new_project", lang), "new_project")])
    rows.append([_button(t("btn_back", lang), "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pick_project_keyboard(projects: list[dict], lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=p["name"][:40], callback_data=PickProject(project_id=p["id"]).pack())] for p in projects]
    rows.append([InlineKeyboardButton(text=t("no_project", lang), callback_data=PickProject(project_id=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def export_keyboard(list_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_pdf", lang), callback_data=ExportFile(kind="pdf", list_id=list_id).pack()),
         InlineKeyboardButton(text=t("btn_xlsx", lang), callback_data=ExportFile(kind="xlsx", list_id=list_id).pack())],
        [_button(t("btn_back", lang), "menu")],
    ])


def web_keyboard(url: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("btn_web", lang), url=url)]])


def orders_keyboard(orders: list[dict], lang: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{o['order_number']} · {(o['title'] or o['customer_name'])[:22]} · {t('order_status_' + o['status'], lang)}"[:60],
                                  callback_data=OrderAct(action="view", order_id=o["id"]).pack())] for o in orders]
    rows.append([_button(t("btn_back", lang), "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


ORDER_ACTION_PRIORITY = ["confirmed", "in_production", "quality_check", "ready", "delivery", "delivered", "rejected", "cancelled"]


def sorted_order_statuses(allowed: list[str]) -> list[str]:
    """Forward steps first, reject next, cancel last (the server lists the allowed moves alphabetically)."""
    rank = {s: i for i, s in enumerate(ORDER_ACTION_PRIORITY)}
    return sorted(allowed, key=lambda s: rank.get(s, len(rank)))


def _order_action(status: str) -> str:
    return {"confirmed": "acc", "rejected": "rej"}.get(status, f"to_{status}")


def order_actions_keyboard(order: dict, lang: str) -> InlineKeyboardMarkup:
    """One button per move the server says is allowed (the bot never decides what is allowed)."""
    rows = [[InlineKeyboardButton(text=t(f"order_btn_{s}", lang), callback_data=OrderAct(action=_order_action(s), order_id=order["id"]).pack())]
            for s in sorted_order_statuses(order.get("allowed_next_statuses", []))]
    rows.append([_button(t("btn_orders", lang), "orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
