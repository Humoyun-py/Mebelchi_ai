from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsAdmin(BaseFilter):
    """Telegram-side gate for admin commands. The backend re-checks is_staff on every admin request."""

    def __init__(self, admin_ids: frozenset[int]):
        self.admin_ids = admin_ids

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and message.from_user.id in self.admin_ids
