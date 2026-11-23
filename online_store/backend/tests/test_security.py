from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    TokenType,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("To‘g‘ri-parol-123")
    assert hashed.startswith("$argon2id$")
    assert verify_password("To‘g‘ri-parol-123", hashed)
    assert not verify_password("noto‘g‘ri", hashed)
    assert not verify_password("anything", "not-a-hash")


def test_access_token_roundtrip(settings: Settings) -> None:
    token, jti, _ = create_token(
        settings, subject="admin-1", token_type=TokenType.ACCESS, extra_claims={"role": "manager"}
    )
    claims = decode_token(settings, token, expected_type=TokenType.ACCESS)
    assert claims["sub"] == "admin-1"
    assert claims["jti"] == jti
    assert claims["role"] == "manager"


def test_refresh_token_cannot_be_used_as_access(settings: Settings) -> None:
    token, _, _ = create_token(settings, subject="admin-1", token_type=TokenType.REFRESH)
    with pytest.raises(AuthenticationError):
        decode_token(settings, token, expected_type=TokenType.ACCESS)


def test_expired_token_rejected(settings: Settings) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    token, _, _ = create_token(settings, subject="a", token_type=TokenType.ACCESS, now=past)
    with pytest.raises(AuthenticationError) as exc:
        decode_token(settings, token, expected_type=TokenType.ACCESS)
    assert exc.value.code == "token_expired"


def test_token_signed_with_other_key_rejected(settings: Settings) -> None:
    forged = jwt.encode(
        {"sub": "a", "type": "access", "jti": "x", "iat": 0, "exp": 9999999999},
        "attacker-key-attacker-key-attacker-key",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        decode_token(settings, forged, expected_type=TokenType.ACCESS)


def test_alg_none_rejected(settings: Settings) -> None:
    unsigned = jwt.encode(
        {"sub": "a", "type": "access", "jti": "x", "iat": 0, "exp": 9999999999},
        key=None,
        algorithm="none",
    )
    with pytest.raises(AuthenticationError):
        decode_token(settings, unsigned, expected_type=TokenType.ACCESS)
