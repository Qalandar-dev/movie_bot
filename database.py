"""
Database layer — async SQLite via aiosqlite.
All queries use parameterised statements to prevent SQL injection.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite

from config import config

logger = logging.getLogger(__name__)

DB_PATH = config.db_path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT,
    joined_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS movies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL COLLATE NOCASE,
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT,
    channel_id  INTEGER NOT NULL,
    message_id  INTEGER NOT NULL,
    file_id     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS movie_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    movie_id     INTEGER NOT NULL REFERENCES movies(id),
    requested_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_movies_code        ON movies(code);
CREATE INDEX IF NOT EXISTS idx_movies_category    ON movies(category);
CREATE INDEX IF NOT EXISTS idx_movie_requests_uid ON movie_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_movie_requests_mid ON movie_requests(movie_id);
"""


async def init_db() -> None:
    """Create all tables and indexes on first run."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()
    logger.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

async def upsert_user(telegram_id: int, username: Optional[str], full_name: str) -> None:
    """Insert user on first visit; update username / full_name on subsequent visits."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
            """,
            (telegram_id, username, full_name),
        )
        await db.commit()


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_total_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_all_user_ids() -> List[int]:
    """Return list of telegram_ids for broadcast."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Movie helpers
# ---------------------------------------------------------------------------

async def add_movie(
    code: str,
    title: str,
    description: str,
    category: str,
    channel_id: int,
    message_id: int,
    file_id: Optional[str] = None,
) -> bool:
    """Returns True on success, False if code already exists."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO movies (code, title, description, category, channel_id, message_id, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (code.upper(), title, description, category, channel_id, message_id, file_id),
            )
            await db.commit()
        return True
    except aiosqlite.IntegrityError:
        return False


async def get_movie_by_code(code: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE code = ? COLLATE NOCASE", (code,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_movie_by_id(movie_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM movies WHERE id = ?", (movie_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_movies() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM movies ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_movies_by_category(category: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM movies WHERE category = ? ORDER BY title", (category,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def delete_movie(code: str) -> bool:
    """Returns True if a movie was deleted."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM movies WHERE code = ? COLLATE NOCASE", (code,))
        await db.commit()
        return cur.rowcount > 0


async def update_movie(
    code: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    category: Optional[str] = None,
) -> bool:
    """Partial update — only non-None fields are changed."""
    fields, values = [], []
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if not fields:
        return False

    values.append(code)
    sql = f"UPDATE movies SET {', '.join(fields)} WHERE code = ? COLLATE NOCASE"
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, values)
        await db.commit()
        return cur.rowcount > 0


async def get_total_movies() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM movies") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# ---------------------------------------------------------------------------
# Request / stats helpers
# ---------------------------------------------------------------------------

async def log_movie_request(telegram_id: int, movie_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cur:
            user_row = await cur.fetchone()
        if not user_row:
            return
        await db.execute(
            "INSERT INTO movie_requests (user_id, movie_id) VALUES (?, ?)",
            (user_row["id"], movie_id),
        )
        await db.commit()


async def get_total_requests() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM movie_requests") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_top_movies(limit: int = 5) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT m.code, m.title, COUNT(mr.id) AS requests
            FROM movie_requests mr
            JOIN movies m ON m.id = mr.movie_id
            GROUP BY mr.movie_id
            ORDER BY requests DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
