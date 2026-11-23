import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.app import BOT_COMMANDS, build_dispatcher, build_storage
from bot.services.api import BackendClient
from config.settings import get_settings


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    api = BackendClient(settings.api_base_url, settings.bot_api_secret.get_secret_value(),
                        timeout=settings.request_timeout_seconds)
    bot = Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = build_storage(settings.redis_url)
    dp = build_dispatcher(api=api, storage=storage, web_app_url=settings.web_app_url,
                          max_upload_mb=settings.max_upload_mb, admin_ids=settings.admin_ids,
                          rate_limit_per_minute=settings.rate_limit_per_minute)
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in BOT_COMMANDS])
    try:
        await dp.start_polling(bot)
    finally:
        await api.close()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(run())
