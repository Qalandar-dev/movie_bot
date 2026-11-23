"""Aggregates all v1 routers. Feature routers are added here phase by phase."""

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
