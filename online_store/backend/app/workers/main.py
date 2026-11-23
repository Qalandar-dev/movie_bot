"""Background worker (arq on Redis): ``arq app.workers.main.WorkerSettings``.

Phase 2 scope: worker process, Redis connection and a heartbeat job so the
container health check has something real to verify. Jobs for notifications,
reservation expiry, low-stock alerts and scheduled reports arrive in Phase 10.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger("app.worker")

HEARTBEAT_KEY = "worker:heartbeat"


async def heartbeat(ctx: dict[str, Any]) -> str:
    now = datetime.now(UTC).isoformat()
    await ctx["redis"].set(HEARTBEAT_KEY, now, ex=180)
    return now


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_json)
    await heartbeat(ctx)
    logger.info("Worker started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Worker stopped")


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    functions: ClassVar[list[Any]] = []
    cron_jobs: ClassVar[list[Any]] = [cron(heartbeat, second=0, run_at_startup=False)]
    on_startup = on_startup
    on_shutdown = on_shutdown
    max_jobs = 20
    job_timeout = 300
    health_check_interval = 30
