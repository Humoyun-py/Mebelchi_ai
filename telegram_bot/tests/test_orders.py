from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.types import Message

from bot.handlers.orders import accept_order, ask_reject_reason, card, list_orders, move_order, reject_with_reason, view_order
from bot.keyboards import OrderAct, main_menu, order_actions_keyboard, orders_keyboard
from bot.services.api import ApiError, BackendClient
from bot.states import OrderStates
from bot.utils.i18n import SUPPORTED, TEXTS
from tests.helpers import fake_callback, fake_message, fsm, last_text

STATUSES = ["new", "pending", "confirmed", "rejected", "in_production", "quality_check", "ready", "delivery", "delivered", "cancelled"]


def order(status="pending", next_=("confirmed", "rejected", "cancelled"), **kw):
    return {"id": 7, "order_number": "ORD-7", "title": "Kitchen", "description": "", "customer_name": "Ali", "customer_phone": "+998901112233",
            "customer_address": "Tashkent", "status": status, "allowed_next_statuses": list(next_), "deadline": "2026-12-20",
            "rejection_reason": "", "total_price": "1500000.00", "paid_amount": "0.00", **kw}


def api_for(role="workshop", linked=True) -> AsyncMock:
    api = AsyncMock(spec=BackendClient)
    api.me.return_value = {"linked": True, "user": {"role": role, "email": "a@b.c", "first_name": "A", "last_name": "B"}} if linked else None
    api.orders.return_value = [order()]
    api.order.return_value = order()
    api.set_order_status.return_value = order("confirmed", ("in_production", "cancelled"))
    return api


def command_message(text: str) -> AsyncMock:
    # a handler that serves both /orders and the menu button branches on isinstance(event, Message), so the double needs the spec
    m = AsyncMock(spec=Message)
    m.text = text
    m.from_user = SimpleNamespace(id=42, username="tester", language_code="uz")
    m.answer = AsyncMock()
    return m


def buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def test_every_status_has_a_label_and_a_button_text_in_every_language():
    for lang in SUPPORTED:
        for s in STATUSES:
            assert f"order_status_{s}" in TEXTS[lang] and f"order_btn_{s}" in TEXTS[lang], (lang, s)
    assert set(TEXTS["uz"]) == set(TEXTS["ru"]) == set(TEXTS["en"])


def test_callback_data_fits_telegram_limit_for_the_longest_action():
    assert len(OrderAct(action="to_quality_check", order_id=2_000_000_000).pack().encode()) <= 64
    # the backend builds "ord:acc:<id>" itself: the bot must parse exactly that
    assert OrderAct.unpack("ord:acc:12") == OrderAct(action="acc", order_id=12)
    assert OrderAct.unpack("ord:rej:12").action == "rej" and OrderAct.unpack("ord:view:12").action == "view"


def test_menu_has_orders_only_for_a_workshop():
    assert any("orders" in b.callback_data for b in buttons(main_menu("uz", True, workshop=True)))
    assert not any("orders" in b.callback_data for b in buttons(main_menu("uz", True)))
    assert not any("orders" in b.callback_data for b in buttons(main_menu("uz", False)))


def test_card_shows_price_only_when_the_server_sent_it_and_escapes_html():
    assert "1500000.00" in card(order(), "uz")
    employee = order()
    del employee["total_price"]
    assert "1500000" not in card(employee, "uz")
    assert "&lt;b&gt;" in card(order(title="<b>x"), "en")


def test_action_buttons_are_exactly_what_the_server_allows():
    cb = [b.callback_data for b in buttons(order_actions_keyboard(order("confirmed", ("in_production", "cancelled")), "uz"))]
    assert cb[:2] == ["ord:to_in_production:7", "ord:to_cancelled:7"]
    cb = [b.callback_data for b in buttons(order_actions_keyboard(order(), "uz"))]
    assert cb[:2] == ["ord:acc:7", "ord:rej:7"]
    assert not [b for b in buttons(order_actions_keyboard(order("delivered", ()), "uz")) if b.callback_data.startswith("ord:")]


def test_list_keyboard_has_one_button_per_order():
    kb = orders_keyboard([order(), order(id=8)], "uz")
    assert [b.callback_data for b in buttons(kb)][:2] == ["ord:view:7", "ord:view:8"]


async def test_list_for_a_workshop():
    api = api_for()
    msg = command_message("/orders")
    await list_orders(msg, api=api, lang="uz")
    api.orders.assert_awaited_once_with(42)
    assert any(b.callback_data == "ord:view:7" for b in buttons(msg.answer.await_args.kwargs["reply_markup"]))


async def test_list_is_refused_for_unlinked_and_for_non_workshop_accounts():
    for kw in (dict(linked=False), dict(role="maker")):
        api = api_for(**kw)
        msg = command_message("/orders")
        await list_orders(msg, api=api, lang="uz")
        api.orders.assert_not_awaited()
        assert msg.answer.await_count == 1


async def test_view_shows_the_card_with_server_allowed_buttons():
    api = api_for()
    cb = fake_callback()
    await view_order(cb, OrderAct(action="view", order_id=7), api=api, lang="en")
    assert "ORD-7" in last_text(cb.message.answer) and "Waiting for answer" in last_text(cb.message.answer)
    assert [b.callback_data for b in buttons(cb.message.answer.await_args.kwargs["reply_markup"])][:2] == ["ord:acc:7", "ord:rej:7"]


async def test_view_of_a_missing_order_says_so():
    api = api_for()
    api.order.side_effect = ApiError(404, "not_found", "Order not found.")
    cb = fake_callback()
    await view_order(cb, OrderAct(action="view", order_id=7), api=api, lang="en")
    assert cb.answer.await_args.kwargs.get("show_alert") is True and "not found" in cb.answer.await_args.args[0].lower()
    cb.message.answer.assert_not_awaited()


async def test_accept_calls_the_server_and_shows_the_new_state():
    api = api_for()
    cb = fake_callback()
    await accept_order(cb, OrderAct(action="acc", order_id=7), api=api, lang="en")
    api.set_order_status.assert_awaited_once_with(42, 7, "confirmed", "")
    assert "Accepted" in last_text(cb.message.answer)


async def test_next_step_buttons_send_the_status_name_without_the_prefix():
    api = api_for()
    cb = fake_callback()
    await move_order(cb, OrderAct(action="to_in_production", order_id=7), api=api, lang="en")
    api.set_order_status.assert_awaited_once_with(42, 7, "in_production", "")


async def test_a_refused_move_is_explained_not_crashed():
    api = api_for()
    api.set_order_status.side_effect = ApiError(400, "validation_error", "bad")
    cb = fake_callback()
    await accept_order(cb, OrderAct(action="acc", order_id=7), api=api, lang="en")
    assert cb.answer.await_args.kwargs.get("show_alert") is True
    cb.message.answer.assert_not_awaited()


async def test_rejecting_asks_for_a_reason_and_sends_it():
    api = api_for()
    state = fsm()
    cb = fake_callback()
    await ask_reject_reason(cb, OrderAct(action="rej", order_id=7), state, lang="en")
    assert await state.get_state() == OrderStates.reject_reason.state
    await reject_with_reason(fake_message("   "), state, api=api, lang="en")
    await reject_with_reason(fake_message("/start"), state, api=api, lang="en")
    api.set_order_status.assert_not_awaited()  # an empty reason or a command is not a reason
    assert await state.get_state() == OrderStates.reject_reason.state
    api.set_order_status.return_value = order("rejected", (), rejection_reason="Too far")
    msg = fake_message("Too far away")
    await reject_with_reason(msg, state, api=api, lang="en")
    api.set_order_status.assert_awaited_once_with(42, 7, "rejected", "Too far away")
    assert await state.get_state() is None
    assert "Rejected" in last_text(msg.answer)


async def test_reject_when_the_server_refuses_clears_the_state():
    api = api_for()
    api.set_order_status.side_effect = ApiError(400, "validation_error", "bad")
    state = fsm()
    await state.set_state(OrderStates.reject_reason)
    await state.update_data(order_id=7)
    msg = fake_message("reason")
    await reject_with_reason(msg, state, api=api, lang="en")
    assert await state.get_state() is None and msg.answer.await_count == 1
