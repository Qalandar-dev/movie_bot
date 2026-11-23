"""Shared Redis client (cache, rate limiting, idempotency locks)."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings, get_settings

_redis: Redis | None = None


def get_redis(settings: Settings | None = None) -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            str((settings or get_settings()).redis_url),
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


async def check_redis() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False
