from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage


def fake_message(text: str | None = None, user_id: int = 42, language_code: str | None = "uz") -> AsyncMock:
    message = AsyncMock()
    message.text = text
    message.from_user = SimpleNamespace(id=user_id, username="tester", language_code=language_code)
    message.answer = AsyncMock()
    message.answer_document = AsyncMock()
    return message


def fake_callback(data_user_id: int = 42, language_code: str | None = "uz") -> AsyncMock:
    cb = AsyncMock()
    cb.from_user = SimpleNamespace(id=data_user_id, username="tester", language_code=language_code)
    cb.message = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def fsm(user_id: int = 42) -> FSMContext:
    storage = MemoryStorage()
    return FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=user_id, user_id=user_id))


def last_text(mock: AsyncMock) -> str:
    return mock.await_args.args[0]
