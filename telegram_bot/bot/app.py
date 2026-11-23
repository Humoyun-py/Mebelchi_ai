"""Builds the dispatcher. Kept separate from main.py so tests can construct the exact production wiring."""
from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import admin, calculator, errors, files, menu, projects, start
from bot.middlewares import ServicesMiddleware, ThrottlingMiddleware
from bot.services.api import BackendClient


def build_storage(redis_url: str) -> BaseStorage:
    if redis_url:
        from aiogram.fsm.storage.redis import RedisStorage
        from redis.asyncio import Redis
        return RedisStorage(Redis.from_url(redis_url))
    return MemoryStorage()


def build_dispatcher(*, api: BackendClient, storage: BaseStorage, web_app_url: str, max_upload_mb: int,
                     admin_ids: frozenset[int], rate_limit_per_minute: int) -> Dispatcher:
    dp = Dispatcher(storage=storage)
    services = ServicesMiddleware(api, web_app_url=web_app_url, max_upload_mb=max_upload_mb)
    throttle = ThrottlingMiddleware(rate_limit_per_minute)
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(services)
        observer.outer_middleware(throttle)

    # Error handlers first so they can see exceptions from every router below.
    dp.include_router(errors.router)
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(projects.router)
    dp.include_router(calculator.router)
    dp.include_router(files.router)
    dp.include_router(admin.register_admin_handlers(admin_ids))
    return dp


BOT_COMMANDS = [
    ("start", "Menu"),
    ("link", "Link account"),
    ("projects", "My projects"),
    ("calc", "Material calculator"),
    ("cutting", "Cutting list"),
    ("help", "Help"),
    ("cancel", "Cancel"),
]
