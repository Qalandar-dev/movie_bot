import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Environment, PaymentMode, Settings

STRONG = "x7Rk2pQ9vL4mN8bT1cY6wZ3hJ5fG0dSaE"


def test_csv_env_values_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://admin.example.uz, https://example.uz")
    monkeypatch.setenv("TELEGRAM_ADMIN_IDS", "111,222")
    s = Settings(_env_file=None)
    assert s.cors_origins == ["https://admin.example.uz", "https://example.uz"]
    assert s.telegram_admin_ids == [111, 222]


def test_secrets_are_not_exposed_in_repr() -> None:
    s = Settings(_env_file=None, jwt_secret_key=SecretStr("super-sensitive-value"))
    assert "super-sensitive-value" not in repr(s)


def test_production_rejects_default_secrets() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            cors_origins=["https://admin.example.uz"],
        )


def test_production_rejects_wildcard_cors_and_debug() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            jwt_secret_key=SecretStr(STRONG),
            bot_api_secret=SecretStr(STRONG + "b"),
            cors_origins=["*"],
            debug=True,
        )
    assert "CORS_ORIGINS" in str(exc.value)
    assert "DEBUG" in str(exc.value)


def test_live_payments_require_credentials() -> None:
    with pytest.raises(ValidationError, match="Click credentials"):
        Settings(
            _env_file=None,
            environment=Environment.PRODUCTION,
            jwt_secret_key=SecretStr(STRONG),
            bot_api_secret=SecretStr(STRONG + "b"),
            cors_origins=["https://admin.example.uz"],
            payment_mode=PaymentMode.LIVE,
        )


def test_valid_production_config() -> None:
    s = Settings(
        _env_file=None,
        environment=Environment.PRODUCTION,
        jwt_secret_key=SecretStr(STRONG),
        bot_api_secret=SecretStr(STRONG + "b"),
        cors_origins=["https://admin.example.uz"],
    )
    assert s.is_production
    assert s.payment_mode is PaymentMode.MOCK


def test_blank_optional_secrets_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "")
    monkeypatch.setenv("CLICK_SECRET_KEY", "  ")
    s = Settings(_env_file=None)
    assert s.bot_token is None
    assert s.click_secret_key is None


def test_validation_errors_do_not_echo_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    # Secrets arrive as plain env strings, exactly as in a container.
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    monkeypatch.setenv("PAYME_SECRET_KEY", "payme-key-must-not-leak")
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    message = str(exc.value)
    assert "must-not-leak" not in message  # pydantic truncates, so check a fragment
    assert "input_value" not in message
