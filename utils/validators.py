"""Input validation utilities."""
from __future__ import annotations

import re

# Movie codes: 1–20 alphanumeric characters (letters, digits, hyphens)
_CODE_RE = re.compile(r'^[A-Za-z0-9\-]{1,20}$')

VALID_CATEGORIES = [
    "Action",
    "Comedy",
    "Drama",
    "Horror",
    "Sci-Fi",
    "Animation",
    "Uzbek",
]


def is_valid_code(code: str) -> bool:
    """Return True if *code* matches the allowed movie-code pattern."""
    return bool(_CODE_RE.match(code.strip()))


def normalise_code(code: str) -> str:
    return code.strip().upper()


def is_valid_category(category: str) -> bool:
    return category in VALID_CATEGORIES


def is_valid_message_id(value: str) -> bool:
    try:
        n = int(value.strip())
        return n > 0
    except ValueError:
        return False
