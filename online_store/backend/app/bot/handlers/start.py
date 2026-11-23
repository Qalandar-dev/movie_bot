"""/start handler. Phase 6 replaces this with registration and the main menu."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="start")

MAINTENANCE_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "Do‘konimiz hozirda ishga tushirilmoqda. Tez orada shu yerda mahsulotlarni "
    "ko‘rib chiqishingiz va buyurtma berishingiz mumkin bo‘ladi."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(MAINTENANCE_TEXT)
