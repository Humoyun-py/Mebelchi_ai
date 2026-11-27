from aiogram.fsm.state import State, StatesGroup


class LinkStates(StatesGroup):
    code = State()


class ProjectStates(StatesGroup):
    new_name = State()
    rename = State()


class CalcStates(StatesGroup):
    """One state per cabinet parameter. data['mode'] is 'calc' or 'cutting'."""

    width = State()
    height = State()
    depth = State()
    thickness = State()
    shelves = State()
    doors = State()
    project = State()


class BroadcastStates(StatesGroup):
    text = State()


class OrderStates(StatesGroup):
    reject_reason = State()
