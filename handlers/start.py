"""
/start handler and main-menu callback handlers.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

import database as db
from keyboards.user import (
    back_to_main_keyboard,
    categories_keyboard,
    main_menu_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()

WELCOME_TEXT = (
    "🎬 <b>Kino Botga xush kelibsiz!</b>\n\n"
    "Sevimli kinongizni topish uchun uning maxsus kodini yuboring.\n\n"
    "🔎 <b>Masalan:</b> <code>101</code>\n\n"
    "🍿 Sifatli kinolar — bir joyda!"
)

ABOUT_TEXT = (
    "ℹ️ <b>Bot haqida</b>\n\n"
    "Bu bot sizga eng yaxshi kinolarni topish imkonini beradi.\n\n"
    "📌 <b>Qanday foydalanish:</b>\n"
    "1️⃣ Kino kodini yuboring (masalan: <code>101</code>)\n"
    "2️⃣ Bot kinoni avtomatik yuboradi\n\n"
    "📂 <b>Kategoriyalar bo'yicha qidirish uchun</b> «Kategoriyalar» tugmasini bosing.\n\n"
    "🔥 <b>Mashhur kinolarni ko'rish uchun</b> «Mashhur kinolar» tugmasini bosing."
)

HELP_TEXT = (
    "❓ <b>Yordam</b>\n\n"
    "📋 <b>Mavjud buyruqlar:</b>\n"
    "/start - Botni boshlash\n"
    "/menu - Bosh menyu\n"
    "/help - Yordam\n"
    "/about - Bot haqida\n\n"
    "🔍 <b>Kino qidirish:</b>\n"
    "Kino kodini to'g'ridan-to'g'ri yuboring (masalan: <code>101</code>)\n\n"
    "🎭 <b>Kategoriyalar:</b>\n"
    "Kategoriyalar bo'yicha qidirish uchun «Kategoriyalar» tugmasini bosing."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await db.upsert_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        HELP_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(
        ABOUT_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


# ── Callback: back to main menu ─────────────────────────────────────────────

@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery) -> None:
    await call.message.edit_text(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Callback: popular movies ─────────────────────────────────────────────────

@router.callback_query(F.data == "popular_movies")
async def cb_popular_movies(call: CallbackQuery) -> None:
    top = await db.get_top_movies(limit=10)
    if not top:
        text = "📭 Hali so'rovlar yo'q. Birinchi bo'ling!"
    else:
        lines = ["🔥 <b>Eng mashhur kinolar:</b>\n"]
        for i, m in enumerate(top, 1):
            lines.append(f"{i}. <code>{m['code']}</code> — {m['title']} ({m['requests']} marta)")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=back_to_main_keyboard(), parse_mode="HTML")
    await call.answer()


# ── Callback: search hint ───────────────────────────────────────────────────

@router.callback_query(F.data == "search_movie")
async def cb_search_movie(call: CallbackQuery) -> None:
    text = (
        "🔍 <b>Kino qidirish</b>\n\n"
        "Kino kodini to'g'ridan-to'g'ri yuboring.\n"
        "Masalan: <code>101</code> yoki <code>AVENGERS</code>"
    )
    await call.message.edit_text(text, reply_markup=back_to_main_keyboard(), parse_mode="HTML")
    await call.answer()


# ── Callback: categories list ────────────────────────────────────────────────

@router.callback_query(F.data == "categories")
async def cb_categories(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🎭 <b>Kategoriyani tanlang:</b>",
        reply_markup=categories_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


# ── Callback: about bot ──────────────────────────────────────────────────────

@router.callback_query(F.data == "about_bot")
async def cb_about(call: CallbackQuery) -> None:
    await call.message.edit_text(ABOUT_TEXT, reply_markup=back_to_main_keyboard(), parse_mode="HTML")
    await call.answer()
