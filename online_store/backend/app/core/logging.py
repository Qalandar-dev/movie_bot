"""Structured logging with secret redaction.

Every log record is rendered as one JSON object (or a readable line in development).
A filter scrubs values that look like secrets: auth headers, tokens, passwords,
payment signatures and card-like numbers. It runs on every record, so a careless
``logger.info("%s", payload)`` cannot leak credentials.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "sign_string",
    "signature",
    "card",
    "cvv",
    "cookie",
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Auth schemes first, so "Authorization: Bearer <t>" loses the token, not just "Bearer".
    (re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+"), r"\1 ***"),
    # key=value / "key": "value" pairs whose key looks sensitive
    (
        re.compile(
            r"(?i)(\"?\b(?:" + "|".join(_SENSITIVE_KEYS) + r")[a-z_]*\"?\s*[:=]\s*)"
            r"(?!(?:bearer|basic) \*\*\*)"
            r"(\"[^\"]*\"|'[^']*'|[^\s,&}\"']+)"
        ),
        r"\1***",
    ),
    # Telegram bot tokens: 123456789:AA...
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "***:***"),
    # Card-like digit sequences (13-19 digits, optional separators)
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "****"),
)


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # malformed %-args: keep the raw message
            message = str(record.msg)
        record.msg = redact(message)
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    _RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
        "message",
        "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }
        if (rid := request_id_ctx.get()) is not None:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        # Values are redacted individually; redacting the serialized JSON would corrupt it.
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    for noisy in ("uvicorn.access", "aiogram.event"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Uvicorn installs its own handlers; route everything through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
