"""Telegram bot entrypoint: ``python -m app.bot.main``.

Phase 2 scope: process wiring only (Redis FSM storage, routers, graceful shutdown).
Catalog, cart, checkout and order handlers are added in Phase 6 and call the
backend services. No business logic will live in handlers.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

from app.bot.handlers import router as root_router
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("app.bot")


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)

    if settings.bot_token is None:
        logger.critical("BOT_TOKEN is not set; the bot cannot start.")
        sys.exit(2)

    storage = RedisStorage.from_url(
        str(settings.redis_url),
        key_builder=DefaultKeyBuilder(prefix="fsm", with_destiny=True),
        state_ttl=60 * 60 * 24,  # abandoned checkouts expire after a day
        data_ttl=60 * 60 * 24,
    )
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)
    dp.include_router(root_router)

    logger.info("Bot polling started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await storage.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
