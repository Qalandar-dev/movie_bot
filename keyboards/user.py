"""User-facing inline keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.validators import VALID_CATEGORIES


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Mashhur kinolar", callback_data="popular_movies"),
        InlineKeyboardButton(text="🔍 Kino qidirish",  callback_data="search_movie"),
    )
    builder.row(
        InlineKeyboardButton(text="🎭 Kategoriyalar",  callback_data="categories"),
        InlineKeyboardButton(text="ℹ️ Bot haqida",     callback_data="about_bot"),
    )
    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    icons = {
        "Action":    "💥",
        "Comedy":    "😂",
        "Drama":     "🎭",
        "Horror":    "😱",
        "Sci-Fi":    "🚀",
        "Animation": "🎨",
        "Uzbek":     "🇺🇿",
    }
    for cat in VALID_CATEGORIES:
        builder.button(
            text=f"{icons.get(cat, '🎬')} {cat}",
            callback_data=f"cat:{cat}",
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Bosh menyu", callback_data="back_main")
    return builder.as_markup()


def movie_action_keyboard(code: str) -> InlineKeyboardMarkup:
    """Keyboard shown after a movie is delivered."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Bosh menyu",   callback_data="back_main")
    builder.button(text="🎭 Kategoriyalar", callback_data="categories")
    builder.adjust(2)
    return builder.as_markup()
