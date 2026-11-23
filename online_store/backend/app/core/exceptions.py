"""Domain exceptions and the API's single error response format.

Every error returned by the API has the shape::

    {"error": {"code": "not_found", "message": "...", "details": {...}, "request_id": "..."}}

Services raise ``AppError`` subclasses; they never import FastAPI. The handlers
registered here translate them to HTTP responses.

Note: Click and Payme webhooks use provider-mandated response formats and handle
their own errors; they do not go through this format.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "So‘rov noto‘g‘ri."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Ma’lumot topilmadi."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Amalni bajarib bo‘lmadi: ma’lumotlar ziddiyati."


class BusinessRuleError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "business_rule_violation"
    message = "Amalni bajarib bo‘lmaydi."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Avtorizatsiya talab qilinadi."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    message = "Bu amal uchun ruxsat yo‘q."


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "So‘rovlar juda ko‘p. Birozdan so‘ng qayta urinib ko‘ring."


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    if (rid := request_id_ctx.get()) is not None:
        body["request_id"] = rid
    return {"error": body}


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=exc.status_code,
        headers=headers,
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
        for err in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "Kiritilgan ma’lumotlar noto‘g‘ri.", details),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    401: ("unauthorized", "Avtorizatsiya talab qilinadi."),
    403: ("forbidden", "Bu amal uchun ruxsat yo‘q."),
    404: ("not_found", "Sahifa yoki ma’lumot topilmadi."),
    405: ("method_not_allowed", "Bu so‘rov usuli qo‘llab-quvvatlanmaydi."),
    413: ("payload_too_large", "Yuborilgan fayl yoki so‘rov hajmi juda katta."),
}


async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, default_message = _HTTP_ERRORS.get(exc.status_code, ("http_error", "So‘rov bajarilmadi."))
    # Starlette's default details are English reason phrases ("Not Found"); show Uzbek instead.
    try:
        is_default_detail = exc.detail == HTTPStatus(exc.status_code).phrase
    except ValueError:
        is_default_detail = False
    message = default_message if is_default_detail else str(exc.detail)
    return JSONResponse(
        error_body(code, message),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        error_body("internal_error", "Ichki xatolik yuz berdi. Keyinroq urinib ko‘ring."),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)
