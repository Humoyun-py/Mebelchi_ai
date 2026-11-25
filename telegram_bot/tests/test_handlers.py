from unittest.mock import AsyncMock

from aiogram.fsm.state import State

from bot.filters import IsAdmin
from bot.handlers.calculator import receive_parameter, start_flow
from bot.handlers.start import receive_link_code
from bot.keyboards import PickProject
from bot.handlers.calculator import cutting_with_project
from bot.services.api import ApiError, BackendClient
from bot.states import CalcStates, LinkStates
from tests.helpers import fake_callback, fake_message, fsm, last_text


def make_api() -> AsyncMock:
    api = AsyncMock(spec=BackendClient)
    api.projects.return_value = [{"id": 5, "name": "Oshxona"}]
    api.calculate.return_value = {"summary": {"panel_count": 6, "distinct_parts": 4, "total_area_m2": 1.23, "edge_banding_m": 4.5}}
    api.create_cutting_list.return_value = {"id": 9, "parts_count": 6, "sheet_count": 1, "utilization_pct": 71.2,
                                            "estimated_cost": None, "unplaced_count": 0, "disclaimer": "check"}
    return api


async def test_calculator_asks_every_parameter_and_calculates_once():
    api = make_api()
    state = fsm()
    await state.update_data(mode="calc", params={})
    await state.set_state(CalcStates.width)
    answers = ["800", "2000", "400", "18", "3", "2"]
    for a in answers:
        await receive_parameter(fake_message(a), state, api=api, lang="uz")
    api.calculate.assert_awaited_once()
    sent = api.calculate.await_args.args[1]
    assert sent == {"width": 800.0, "height": 2000.0, "depth": 400.0, "thickness": 18.0, "shelves": 3, "doors": 2}
    assert await state.get_state() is None  # flow finished


async def test_invalid_value_keeps_the_same_question():
    api = make_api()
    state = fsm()
    await state.update_data(mode="calc", params={})
    await state.set_state(CalcStates.width)
    message = fake_message("abc")
    await receive_parameter(message, state, api=api, lang="ru")
    assert await state.get_state() == CalcStates.width.state
    assert "Некорректное" in last_text(message.answer)
    api.calculate.assert_not_awaited()


async def test_fractional_shelves_are_rejected():
    api = make_api()
    state = fsm()
    await state.update_data(mode="calc", params={"width": 800.0})
    await state.set_state(CalcStates.shelves)
    message = fake_message("2.5")
    await receive_parameter(message, state, api=api, lang="uz")
    assert await state.get_state() == CalcStates.shelves.state


async def test_cutting_flow_asks_for_project_then_creates_list():
    api = make_api()
    state = fsm()
    await state.update_data(mode="cutting", params={"width": 800.0, "height": 2000.0, "depth": 400.0,
                                                   "thickness": 18.0, "shelves": 2})
    await state.set_state(CalcStates.doors)
    await receive_parameter(fake_message("2"), state, api=api, lang="uz")
    assert await state.get_state() == CalcStates.project.state
    api.projects.assert_awaited_once()

    callback = fake_callback()
    await cutting_with_project(callback, PickProject(project_id=5), state, api=api, lang="uz")
    params = api.create_cutting_list.await_args.args[1]
    assert params["project_id"] == 5 and params["doors"] == 2.0


async def test_cutting_without_project_omits_project_id():
    api = make_api()
    state = fsm()
    await state.update_data(mode="cutting", params={"width": 800.0})
    await state.set_state(CalcStates.project)
    await cutting_with_project(fake_callback(), PickProject(project_id=0), state, api=api, lang="uz")
    assert "project_id" not in api.create_cutting_list.await_args.args[1]


async def test_backend_error_is_shown_as_safe_text():
    api = make_api()
    api.calculate.side_effect = ApiError(400, "error", "Validation failed.", {"width": ["bad"]})
    state = fsm()
    await state.update_data(mode="calc", params={})
    await state.set_state(CalcStates.doors)
    message = fake_message("1")
    await receive_parameter(message, state, api=api, lang="en")
    assert last_text(message.answer) == "Something went wrong. Try again."


async def test_link_code_failure_keeps_user_in_link_state():
    api = make_api()
    api.link.side_effect = ApiError(400, "invalid_code", "x")
    state = fsm()
    await state.set_state(LinkStates.code)
    message = fake_message("WRONG-CODE")
    await receive_link_code(message, state, api=api, lang="uz")
    assert await state.get_state() == LinkStates.code.state
    assert "noto'g'ri" in last_text(message.answer)


async def test_link_success_clears_state_and_confirms_email():
    api = make_api()
    api.link.return_value = {"email": "maker@x.com"}
    state = fsm()
    await state.set_state(LinkStates.code)
    message = fake_message("abcd-efgh")
    await receive_link_code(message, state, api=api, lang="uz")
    assert await state.get_state() is None
    assert "maker@x.com" in last_text(message.answer)
    api.link.assert_awaited_once_with(42, "tester", "abcd-efgh")


async def test_start_flow_moves_to_first_question():
    state = fsm()
    cb = fake_callback()
    await start_flow(cb, state, "uz", "calc")
    assert await state.get_state() == CalcStates.width.state
    assert "Kengligi" in last_text(cb.message.answer)


def test_admin_filter_matches_only_configured_ids():
    flt = IsAdmin(frozenset({1001}))
    admin_msg = fake_message(user_id=1001)
    other_msg = fake_message(user_id=7)
    import asyncio
    assert asyncio.run(flt(admin_msg)) is True
    assert asyncio.run(flt(other_msg)) is False
