"""Async engine and session management.

Transaction boundaries are explicit: API routes get a session through
``get_session`` and services call ``session.commit()`` / use ``session.begin()``
themselves. Nothing auto-commits.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url_str,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        echo=settings.database_echo,
        connect_args={"server_settings": {"timezone": "UTC", "application_name": "online_store"}},
    )


def init_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_engine(settings or get_settings())
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        init_engine()
    if _sessionmaker is None:  # pragma: no cover - init_engine always sets it
        raise RuntimeError("Database engine is not initialised")
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back if not committed."""
    async with get_sessionmaker()() as session:
        yield session


async def check_database() -> bool:
    try:
        async with init_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
