"""
Entry point — initialise DB, register routers, start polling.
Run with: python bot.py
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonCommands

# ── Config validation happens at import time ─────────────────────────────────
try:
    from config import config
except ValueError as exc:
    print(f"[CONFIG ERROR] {exc}")
    sys.exit(1)

import database as db
from handlers import admin, movies, start

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Startup / shutdown hooks ──────────────────────────────────────────────────

async def on_startup() -> None:
    logger.info("Initialising database …")
    await db.init_db()
    logger.info("Bot started. Admin IDs: %s", config.admin_ids)


async def on_shutdown() -> None:
    logger.info("Bot stopped.")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Set menu button
    await bot.set_my_commands([
        {"command": "start", "description": "Botni boshlash"},
        {"command": "menu", "description": "Bosh menyu"},
        {"command": "help", "description": "Yordam"},
        {"command": "about", "description": "Bot haqida"},
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands(commands=["start", "menu", "help", "about"]))

    dp = Dispatcher(storage=MemoryStorage())

    # Register startup / shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Register routers — admin FIRST so IsAdmin filter runs before generic handlers
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(movies.router)

    # Drop any pending updates that arrived while the bot was offline
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Starting polling …")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
