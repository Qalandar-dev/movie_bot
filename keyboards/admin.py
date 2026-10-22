"""Admin inline keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.validators import VALID_CATEGORIES


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Kino qo'shish",   callback_data="adm:add"),
        InlineKeyboardButton(text="❌ Kino o'chirish",  callback_data="adm:delete"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Kino tahrirlash", callback_data="adm:edit"),
        InlineKeyboardButton(text="📋 Kinolar ro'yxati", callback_data="adm:list"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Statistika",      callback_data="adm:stats"),
        InlineKeyboardButton(text="📢 Xabar yuborish",  callback_data="adm:broadcast"),
    )
    return builder.as_markup()


def admin_category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in VALID_CATEGORIES:
        builder.button(text=cat, callback_data=f"adm_cat:{cat}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:cancel"))
    return builder.as_markup()


def confirm_delete_keyboard(code: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirish",  callback_data=f"adm_del_yes:{code}"),
        InlineKeyboardButton(text="❌ Yo'q, bekor",    callback_data="adm:cancel"),
    )
    return builder.as_markup()


def edit_field_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Sarlavha",    callback_data="adm_field:title"),
        InlineKeyboardButton(text="📄 Tavsif",      callback_data="adm_field:description"),
    )
    builder.row(
        InlineKeyboardButton(text="🎭 Kategoriya",  callback_data="adm_field:category"),
        InlineKeyboardButton(text="❌ Bekor",        callback_data="adm:cancel"),
    )
    return builder.as_markup()


def confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborish",    callback_data="adm_bc:confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:cancel"),
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    return builder.as_markup()
