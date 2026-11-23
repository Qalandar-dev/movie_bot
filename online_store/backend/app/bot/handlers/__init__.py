from aiogram import Router

from app.bot.handlers import start

router = Router(name="root")
router.include_router(start.router)
