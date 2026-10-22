"""
Admin handlers — protected by IsAdmin filter.
Covers: /admin, /addmovie, /deletemovie, /editmovie, /movies, /stats, /broadcast
and all related FSM flows + inline-keyboard callbacks.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import config
from keyboards.admin import (
    admin_category_keyboard,
    admin_panel_keyboard,
    cancel_keyboard,
    confirm_broadcast_keyboard,
    confirm_delete_keyboard,
    edit_field_keyboard,
)
from states.admin import (
    AddMovieStates,
    BroadcastStates,
    DeleteMovieStates,
    EditMovieStates,
)
from utils.validators import (
    VALID_CATEGORIES,
    is_valid_category,
    is_valid_code,
    is_valid_message_id,
    normalise_code,
)

logger = logging.getLogger(__name__)


# ── Authorization filter ─────────────────────────────────────────────────────

class IsAdmin(BaseFilter):
    """Passes only for users whose Telegram ID is in ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return user is not None and config.is_admin(user.id)


router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ── Helper ───────────────────────────────────────────────────────────────────

async def _cancel_state(fsm: FSMContext, message: Message, text: str = "❌ Bekor qilindi.") -> None:
    await fsm.clear()
    await message.answer(text, reply_markup=admin_panel_keyboard())


# ── /admin ───────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🛠 <b>Admin paneli</b>\n\nBir amalni tanlang:",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML",
    )


# ── /stats ───────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
@router.callback_query(F.data == "adm:stats")
async def cmd_stats(event: Message | CallbackQuery) -> None:
    total_users    = await db.get_total_users()
    total_movies   = await db.get_total_movies()
    total_requests = await db.get_total_requests()
    top_movies     = await db.get_top_movies(5)

    top_lines = ""
    if top_movies:
        top_lines = "\n\n🏆 <b>Top kinolar:</b>\n" + "\n".join(
            f"  {i}. <code>{m['code']}</code> — {m['title']} ({m['requests']} ta)"
            for i, m in enumerate(top_movies, 1)
        )

    text = (
        "📊 <b>Bot statistikasi</b>\n\n"
        f"👤 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"🎬 Kinolar: <b>{total_movies}</b>\n"
        f"📥 Jami so'rovlar: <b>{total_requests}</b>"
        f"{top_lines}"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")


# ── /movies ──────────────────────────────────────────────────────────────────

@router.message(Command("movies"))
@router.callback_query(F.data == "adm:list")
async def cmd_movies(event: Message | CallbackQuery) -> None:
    movies = await db.get_all_movies()
    if not movies:
        text = "📭 Hozircha kinolar yo'q."
    else:
        lines = ["🎬 <b>Barcha kinolar:</b>\n"]
        for m in movies:
            lines.append(
                f"• <code>{m['code']}</code> | {m['title']} | {m['category'] or '—'}"
            )
        text = "\n".join(lines)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=admin_panel_keyboard(), parse_mode="HTML")


# ── ADD MOVIE ─────────────────────────────────────────────────────────────────

@router.message(Command("addmovie"))
@router.callback_query(F.data == "adm:add")
async def start_add_movie(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddMovieStates.waiting_for_code)
    text = "➕ <b>Yangi kino qo'shish</b>\n\nKino kodini yuboring (masalan: <code>101</code>):"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=cancel_keyboard(), parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(text, reply_markup=cancel_keyboard(), parse_mode="HTML")


@router.message(AddMovieStates.waiting_for_code)
async def add_movie_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    if not is_valid_code(code):
        await message.answer(
            "⚠️ Noto'g'ri kod. Faqat harflar, raqamlar va tire ishlating (1–20 belgi).\n"
            "Qayta kiriting:",
            reply_markup=cancel_keyboard(),
        )
        return
    # Check uniqueness
    existing = await db.get_movie_by_code(code)
    if existing:
        await message.answer(
            f"⚠️ <code>{code.upper()}</code> kodi allaqachon mavjud!\n"
            "Boshqa kod kiriting:",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return
    await state.update_data(code=normalise_code(code))
    await state.set_state(AddMovieStates.waiting_for_title)
    await message.answer("📝 Kino sarlavhasini kiriting:", reply_markup=cancel_keyboard())


@router.message(AddMovieStates.waiting_for_title)
async def add_movie_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("⚠️ Sarlavha bo'sh bo'lishi mumkin emas. Qayta kiriting:", reply_markup=cancel_keyboard())
        return
    await state.update_data(title=title)
    await state.set_state(AddMovieStates.waiting_for_description)
    await message.answer(
        "📄 Tavsif kiriting (yoki /skip yuboring):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddMovieStates.waiting_for_description)
async def add_movie_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    description = "" if text.lower() in ("/skip", "skip") else text
    await state.update_data(description=description)
    await state.set_state(AddMovieStates.waiting_for_category)
    await message.answer(
        "🎭 Kategoriyani tanlang:",
        reply_markup=admin_category_keyboard(),
    )


@router.callback_query(AddMovieStates.waiting_for_category, F.data.startswith("adm_cat:"))
async def add_movie_category(call: CallbackQuery, state: FSMContext) -> None:
    category = call.data.split(":", 1)[1]
    if not is_valid_category(category):
        await call.answer("Noto'g'ri kategoriya!", show_alert=True)
        return
    await state.update_data(category=category)
    await state.set_state(AddMovieStates.waiting_for_message_id)
    await call.message.edit_text(
        "📨 Kanal xabari ID sini kiriting.\n\n"
        "<i>Kanaldan xabarni botga forward qiling yoki xabar ID sini kiriting:</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(AddMovieStates.waiting_for_message_id)
async def add_movie_message_id(message: Message, state: FSMContext) -> None:
    """Accept either a forwarded channel post or a raw message_id integer."""
    msg_id: Optional[int] = None

    # Forwarded message from a channel
    if message.forward_from_chat and message.forward_from_message_id:
        msg_id = message.forward_from_message_id
        channel_id = message.forward_from_chat.id
        data = await state.get_data()
        await state.update_data(channel_id=channel_id, message_id=msg_id)
    else:
        raw = (message.text or "").strip()
        if not is_valid_message_id(raw):
            await message.answer(
                "⚠️ Noto'g'ri xabar ID. Musbat son kiriting yoki kanaldan forward qiling:",
                reply_markup=cancel_keyboard(),
            )
            return
        msg_id = int(raw)
        data = await state.get_data()
        channel_id = config.channel_id
        await state.update_data(channel_id=channel_id, message_id=msg_id)

    data = await state.get_data()

    # Validate the message is actually accessible
    try:
        await message.bot.forward_message(
            chat_id=message.chat.id,
            from_chat_id=data["channel_id"],
            message_id=data["message_id"],
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(
            f"⚠️ Xabarni olishda xatolik: {exc}\n"
            "Kanal ID va xabar ID ni tekshirib qayta yuboring.",
            reply_markup=cancel_keyboard(),
        )
        await state.set_state(AddMovieStates.waiting_for_message_id)
        return

    # Save to DB
    ok = await db.add_movie(
        code=data["code"],
        title=data["title"],
        description=data.get("description", ""),
        category=data["category"],
        channel_id=data["channel_id"],
        message_id=data["message_id"],
    )
    await state.clear()
    if ok:
        await message.answer(
            f"✅ <b>Kino muvaffaqiyatli qo'shildi!</b>\n\n"
            f"🔑 Kod: <code>{data['code']}</code>\n"
            f"🎬 Sarlavha: {data['title']}\n"
            f"🎭 Kategoriya: {data['category']}",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Xatolik: bu kod allaqachon mavjud.",
            reply_markup=admin_panel_keyboard(),
        )


# ── DELETE MOVIE ─────────────────────────────────────────────────────────────

@router.message(Command("deletemovie"))
@router.callback_query(F.data == "adm:delete")
async def start_delete_movie(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DeleteMovieStates.waiting_for_code)
    text = "❌ O'chirish uchun kino kodini kiriting:"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=cancel_keyboard())
        await event.answer()
    else:
        await event.answer(text, reply_markup=cancel_keyboard())


@router.message(DeleteMovieStates.waiting_for_code)
async def delete_movie_code(message: Message, state: FSMContext) -> None:
    code = normalise_code(message.text or "")
    movie = await db.get_movie_by_code(code)
    if not movie:
        await message.answer(
            f"❌ <code>{code}</code> kodi bo'yicha kino topilmadi.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return
    await state.update_data(code=code, title=movie["title"])
    await state.set_state(DeleteMovieStates.waiting_for_confirm)
    await message.answer(
        f"⚠️ <b>Rostdan ham o'chirmoqchimisiz?</b>\n\n"
        f"🎬 {movie['title']} (<code>{code}</code>)",
        reply_markup=confirm_delete_keyboard(code),
        parse_mode="HTML",
    )


@router.callback_query(DeleteMovieStates.waiting_for_confirm, F.data.startswith("adm_del_yes:"))
async def confirm_delete(call: CallbackQuery, state: FSMContext) -> None:
    code = call.data.split(":", 1)[1]
    deleted = await db.delete_movie(code)
    await state.clear()
    if deleted:
        await call.message.edit_text(
            f"✅ <code>{code}</code> kino o'chirildi.",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )
    else:
        await call.message.edit_text(
            "❌ O'chirishda xatolik yuz berdi.",
            reply_markup=admin_panel_keyboard(),
        )
    await call.answer()


# ── EDIT MOVIE ────────────────────────────────────────────────────────────────

@router.message(Command("editmovie"))
@router.callback_query(F.data == "adm:edit")
async def start_edit_movie(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(EditMovieStates.waiting_for_code)
    text = "✏️ Tahrirlash uchun kino kodini kiriting:"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=cancel_keyboard())
        await event.answer()
    else:
        await event.answer(text, reply_markup=cancel_keyboard())


@router.message(EditMovieStates.waiting_for_code)
async def edit_movie_code(message: Message, state: FSMContext) -> None:
    code = normalise_code(message.text or "")
    movie = await db.get_movie_by_code(code)
    if not movie:
        await message.answer(
            f"❌ <code>{code}</code> topilmadi.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return
    await state.update_data(code=code)
    await state.set_state(EditMovieStates.waiting_for_field)
    await message.answer(
        f"✏️ <b>{movie['title']}</b> — qaysi maydonni tahrirlash?",
        reply_markup=edit_field_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(EditMovieStates.waiting_for_field, F.data.startswith("adm_field:"))
async def edit_movie_field(call: CallbackQuery, state: FSMContext) -> None:
    field = call.data.split(":", 1)[1]
    await state.update_data(field=field)
    await state.set_state(EditMovieStates.waiting_for_new_value)

    if field == "category":
        await call.message.edit_text(
            "🎭 Yangi kategoriyani tanlang:",
            reply_markup=admin_category_keyboard(),
        )
    else:
        label = {"title": "sarlavha", "description": "tavsif"}.get(field, field)
        await call.message.edit_text(
            f"📝 Yangi {label}ni kiriting:",
            reply_markup=cancel_keyboard(),
        )
    await call.answer()


@router.message(EditMovieStates.waiting_for_new_value)
async def edit_movie_new_value_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("field")
    new_value = (message.text or "").strip()

    if not new_value:
        await message.answer("⚠️ Qiymat bo'sh bo'lishi mumkin emas.", reply_markup=cancel_keyboard())
        return

    await _apply_edit(message, state, data["code"], field, new_value)


@router.callback_query(EditMovieStates.waiting_for_new_value, F.data.startswith("adm_cat:"))
async def edit_movie_new_category(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    category = call.data.split(":", 1)[1]
    if not is_valid_category(category):
        await call.answer("Noto'g'ri kategoriya!", show_alert=True)
        return
    await _apply_edit(call.message, state, data["code"], "category", category)
    await call.answer()


async def _apply_edit(
    message: Message, state: FSMContext, code: str, field: str, value: str
) -> None:
    kwargs: Dict[str, Any] = {field: value}
    updated = await db.update_movie(code, **kwargs)
    await state.clear()
    if updated:
        await message.answer(
            f"✅ <code>{code}</code> kinosi yangilandi.",
            reply_markup=admin_panel_keyboard(),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Yangilashda xatolik yuz berdi.",
            reply_markup=admin_panel_keyboard(),
        )


# ── BROADCAST ─────────────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
@router.callback_query(F.data == "adm:broadcast")
async def start_broadcast(event: Message | CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_for_message)
    text = "📢 Yubormoqchi bo'lgan xabarni kiriting:"
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=cancel_keyboard())
        await event.answer()
    else:
        await event.answer(text, reply_markup=cancel_keyboard())


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_message(message: Message, state: FSMContext) -> None:
    text = message.text or message.caption or ""
    if not text.strip():
        await message.answer("⚠️ Xabar bo'sh bo'lishi mumkin emas.", reply_markup=cancel_keyboard())
        return
    await state.update_data(bc_text=text)
    await state.set_state(BroadcastStates.waiting_for_confirm)
    await message.answer(
        f"📋 <b>Xabar ko'rinishi:</b>\n\n{text}\n\n"
        "Barcha foydalanuvchilarga yuborasizmi?",
        reply_markup=confirm_broadcast_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(BroadcastStates.waiting_for_confirm, F.data == "adm_bc:confirm")
async def confirm_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    bc_text = data.get("bc_text", "")
    await state.clear()
    await call.message.edit_text("📤 Xabar yuborilmoqda...")
    await call.answer()

    user_ids = await db.get_all_user_ids()
    sent = failed = 0

    for uid in user_ids:
        try:
            await call.message.bot.send_message(uid, bc_text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # ~20 msg/s to respect rate limits
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await call.message.bot.send_message(uid, bc_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception as exc:
            logger.exception("Broadcast error to %s: %s", uid, exc)
            failed += 1

    await call.message.answer(
        f"✅ Xabar yuborildi!\n"
        f"📤 Muvaffaqiyatli: {sent}\n"
        f"❌ Xato: {failed}",
        reply_markup=admin_panel_keyboard(),
    )


# ── Global cancel ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "❌ Bekor qilindi.\n\n🛠 Admin paneli:",
        reply_markup=admin_panel_keyboard(),
    )
    await call.answer()
