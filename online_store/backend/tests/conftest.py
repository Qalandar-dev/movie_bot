"""Test configuration.

Tests use a separate database (``TEST_DATABASE_URL``, default ``online_store_test``)
and a separate Redis DB index so they can never touch development data.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://store:store@localhost:5432/online_store_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["LOG_JSON"] = "false"

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.redis import close_redis
from app.database.session import dispose_engine
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as c,
    ):
        yield c
    await close_redis()
    await dispose_engine()
