from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.redis import check_redis
from app.database.session import check_database

router = APIRouter(tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    """Process is up. Used by the container health check."""
    return LiveResponse()


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse}},
)
async def ready(response: Response) -> ReadyResponse:
    """Dependencies reachable. Returns 503 if PostgreSQL or Redis is down."""
    db_ok = await check_database()
    redis_ok = await check_redis()
    ok = db_ok and redis_ok
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(status="ok" if ok else "degraded", database=db_ok, redis=redis_ok)
