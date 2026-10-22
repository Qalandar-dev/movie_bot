"""
Movie lookup and category browsing handlers.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, Message

import database as db
from config import config
from keyboards.user import back_to_main_keyboard, categories_keyboard, movie_action_keyboard
from utils.validators import is_valid_code, normalise_code

logger = logging.getLogger(__name__)
router = Router()


# ── Movie code lookup ────────────────────────────────────────────────────────

@router.message(F.text)
async def handle_movie_code(message: Message) -> None:
    """Any plain-text message is treated as a potential movie code."""
    raw = (message.text or "").strip()

    # Skip command-like messages
    if raw.startswith("/"):
        return

    if not is_valid_code(raw):
        await message.answer(
            "⚠️ Noto'g'ri kod formati.\n"
            "Faqat harflar, raqamlar va tire (-) ishlatilishi mumkin (1–20 ta belgi).\n\n"
            "Masalan: <code>101</code> yoki <code>ACTION-01</code>",
            parse_mode="HTML",
        )
        return

    code = normalise_code(raw)
    movie = await db.get_movie_by_code(code)

    if not movie:
        await message.answer(
            "❌ <b>Bu kod bo'yicha kino topilmadi.</b>\n"
            "Kodni tekshirib qayta yuboring.",
            reply_markup=back_to_main_keyboard(),
            parse_mode="HTML",
        )
        return

    # Log the request
    await db.log_movie_request(message.from_user.id, movie["id"])

    # Build caption
    caption = _build_caption(movie)

    # Attempt to copy/forward the channel message
    sent = await _deliver_movie(message, movie, caption)
    if sent:
        await message.answer(
            "✅ Kino yuborildi!",
            reply_markup=movie_action_keyboard(code),
        )
    else:
        await message.answer(
            "⚠️ Kino topildi, lekin uni yuborishda xatolik yuz berdi.\n"
            "Iltimos, keyinroq urinib ko'ring.",
            reply_markup=back_to_main_keyboard(),
        )


async def _deliver_movie(message: Message, movie: dict, caption: str) -> bool:
    """Copy the channel message to the user. Returns True on success."""
    channel_id  = movie["channel_id"]
    msg_id      = movie["message_id"]

    try:
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=channel_id,
            message_id=msg_id,
            caption=caption,
            parse_mode="HTML",
        )
        return True
    except TelegramBadRequest as exc:
        logger.warning("copy_message failed (bad request) for code %s: %s", movie["code"], exc)
    except TelegramForbiddenError as exc:
        logger.warning("copy_message forbidden for code %s: %s", movie["code"], exc)
    except Exception as exc:
        logger.exception("Unexpected error delivering movie %s: %s", movie["code"], exc)
    return False


def _build_caption(movie: dict) -> str:
    parts = [f"🎬 <b>{movie['title']}</b>"]
    if movie.get("description"):
        parts.append(f"\n📄 {movie['description']}")
    if movie.get("category"):
        parts.append(f"\n🎭 <b>Kategoriya:</b> {movie['category']}")
    parts.append(f"\n🔑 <b>Kod:</b> <code>{movie['code']}</code>")
    return "\n".join(parts)


# ── Category browsing ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:"))
async def cb_category(call: CallbackQuery) -> None:
    category = call.data.split(":", 1)[1]
    movies = await db.get_movies_by_category(category)

    if not movies:
        text = f"📭 <b>{category}</b> kategoriyasida hozircha kinolar yo'q."
    else:
        lines = [f"🎭 <b>{category}</b> kategoriyasidagi kinolar:\n"]
        for m in movies:
            lines.append(f"• <code>{m['code']}</code> — {m['title']}")
        lines.append("\n👆 Kino kodini yuboring va tomosha qiling!")
        text = "\n".join(lines)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Kategoriyalar", callback_data="categories"),
        InlineKeyboardButton(text="🏠 Bosh menyu",   callback_data="back_main"),
    )

    await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await call.answer()
