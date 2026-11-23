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


class RoomStates(StatesGroup):
    """The room flow itself lives on the server. These states only say what kind of message the bot waits for."""

    photo = State()    # a room photo
    number = State()   # a typed number: a form field or an opening's offset/width. data['mode'] is 'group' or 'opening'
