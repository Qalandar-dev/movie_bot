"""Password hashing and JWT primitives.

Only cryptographic building blocks live here. The refresh-token rotation policy
(server-side token families, reuse detection, revocation) is implemented by the
auth service in Phase 5 on top of these helpers.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings
from app.core.exceptions import AuthenticationError

_hasher = PasswordHasher()  # Argon2id, library defaults follow RFC 9106 recommendations


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Hash for storing refresh tokens / idempotency keys at rest (not passwords)."""
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def create_token(
    settings: Settings,
    *,
    subject: str,
    token_type: TokenType,
    extra_claims: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> tuple[str, str, datetime]:
    """Return ``(encoded_jwt, jti, expires_at)``."""
    issued = now or datetime.now(UTC)
    ttl = (
        timedelta(minutes=settings.access_token_ttl_minutes)
        if token_type is TokenType.ACCESS
        else timedelta(days=settings.refresh_token_ttl_days)
    )
    expires = issued + ttl
    jti = uuid.uuid4().hex
    claims: dict[str, Any] = {
        **(extra_claims or {}),
        "sub": subject,
        "type": token_type.value,
        "iat": issued,
        "nbf": issued,
        "exp": expires,
        "jti": jti,
        "iss": settings.project_name,
    }
    token = jwt.encode(
        claims, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, jti, expires


def decode_token(settings: Settings, token: str, *, expected_type: TokenType) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # never trust the token's own "alg"
            issuer=settings.project_name,
            options={"require": ["exp", "iat", "sub", "type", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Sessiya muddati tugagan.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Token yaroqsiz.", code="invalid_token") from exc
    if claims.get("type") != expected_type.value:
        raise AuthenticationError("Token turi noto‘g‘ri.", code="invalid_token")
    return claims
