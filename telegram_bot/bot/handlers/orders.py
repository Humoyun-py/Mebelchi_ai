"""Workshop orders in the chat: list, details, accept / reject (with a reason) and the production steps the server allows."""
import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.handlers.common import is_workshop, linked_user
from bot.keyboards import Nav, OrderAct, back_to_menu, cancel_keyboard, order_actions_keyboard, orders_keyboard
from bot.services.api import ApiError, BackendClient
from bot.states import OrderStates
from bot.utils.i18n import t

router = Router(name="orders")


def card(order: dict, lang: str) -> str:
    extra = ""
    if order.get("total_price") is not None:
        extra += t("order_price", lang, price=order["total_price"])
    if order.get("deadline"):
        extra += t("order_deadline", lang, deadline=order["deadline"])
    if order.get("rejection_reason"):
        extra += t("order_reason", lang, reason=order["rejection_reason"])
    return t("order_card", lang, title=order["title"] or order["order_number"], number=order["order_number"],
             status=t(f"order_status_{order['status']}", lang), customer=order["customer_name"] or "-",
             phone=order["customer_phone"] or "-", address=order["customer_address"] or "-", extra=extra)


async def _guard(event: Message | CallbackQuery, api: BackendClient, lang: str) -> bool:
    me = await linked_user(api, event.from_user.id)
    if me is None:
        await (event if isinstance(event, Message) else event.message).answer(t("not_linked", lang))
    elif not is_workshop(me):
        await (event if isinstance(event, Message) else event.message).answer(t("order_workshop_only", lang), reply_markup=back_to_menu(lang))
    else:
        return True
    if isinstance(event, CallbackQuery):
        await event.answer()
    return False


@router.message(Command("orders"))
@router.callback_query(Nav.filter(F.to == "orders"))
async def list_orders(event: Message | CallbackQuery, api: BackendClient, lang: str) -> None:
    if not await _guard(event, api, lang):
        return
    orders = await api.orders(event.from_user.id)
    message = event if isinstance(event, Message) else event.message
    if not orders:
        await message.answer(t("orders_empty", lang), reply_markup=back_to_menu(lang))
    else:
        await message.answer(t("orders_title", lang), reply_markup=orders_keyboard(orders, lang))
    if isinstance(event, CallbackQuery):
        await event.answer()


async def _show(callback: CallbackQuery, order: dict, lang: str, prefix: str = "") -> None:
    await callback.message.answer(prefix + card(order, lang), reply_markup=order_actions_keyboard(order, lang))


@router.callback_query(OrderAct.filter(F.action == "view"))
async def view_order(callback: CallbackQuery, callback_data: OrderAct, api: BackendClient, lang: str) -> None:
    try:
        order = await api.order(callback.from_user.id, callback_data.order_id)
    except ApiError as exc:
        await callback.answer(t("order_not_found" if exc.status == 404 else "generic_error", lang), show_alert=True)
        return
    await _show(callback, order, lang)
    await callback.answer()


async def _move(callback: CallbackQuery, api: BackendClient, lang: str, order_id: int, status: str, note: str = "") -> None:
    try:
        order = await api.set_order_status(callback.from_user.id, order_id, status, note)
    except ApiError as exc:
        # 404: not mine / gone; 400: the server refused the move (stale button, missing reason); anything else is handled by the error router
        if exc.status in (400, 404, 409):
            await callback.answer(t("order_not_found" if exc.status == 404 else "order_cannot", lang), show_alert=True)
            return
        raise
    await _show(callback, order, lang, prefix=t("order_updated", lang, status=t(f"order_status_{order['status']}", lang)) + "\n\n")
    await callback.answer()


@router.callback_query(OrderAct.filter(F.action == "acc"))
async def accept_order(callback: CallbackQuery, callback_data: OrderAct, api: BackendClient, lang: str) -> None:
    await _move(callback, api, lang, callback_data.order_id, "confirmed")


@router.callback_query(OrderAct.filter(F.action.startswith("to_")))
async def move_order(callback: CallbackQuery, callback_data: OrderAct, api: BackendClient, lang: str) -> None:
    await _move(callback, api, lang, callback_data.order_id, callback_data.action[3:])


@router.callback_query(OrderAct.filter(F.action == "rej"))
async def ask_reject_reason(callback: CallbackQuery, callback_data: OrderAct, state: FSMContext, lang: str) -> None:
    await state.set_state(OrderStates.reject_reason)
    await state.update_data(order_id=callback_data.order_id)
    await callback.message.answer(t("ask_reject_reason", lang), reply_markup=cancel_keyboard(lang))
    await callback.answer()


@router.message(OrderStates.reject_reason, F.text)
async def reject_with_reason(message: Message, state: FSMContext, api: BackendClient, lang: str) -> None:
    reason = (message.text or "").strip()
    if not reason or reason.startswith("/"):
        await message.answer(t("order_reason_empty", lang), reply_markup=cancel_keyboard(lang))
        return
    data = await state.get_data()
    try:
        order = await api.set_order_status(message.from_user.id, data["order_id"], "rejected", reason[:255])
    except ApiError as exc:
        await state.clear()
        if exc.status in (400, 404, 409):
            await message.answer(t("order_not_found" if exc.status == 404 else "order_cannot", lang), reply_markup=back_to_menu(lang))
            return
        raise
    await state.clear()
    await message.answer(t("order_updated", lang, status=t("order_status_rejected", lang)) + "\n\n" + card(order, lang),
                         reply_markup=order_actions_keyboard(order, lang))
