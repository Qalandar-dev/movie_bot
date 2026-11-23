"""Application configuration.

All configuration comes from environment variables (optionally a ``.env`` file in
development). Secrets are typed as ``SecretStr`` so they are never printed by
``repr()`` or written to logs by accident.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Self

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class PaymentMode(StrEnum):
    """How payment providers behave.

    ``mock``     — no external calls; payments are simulated and always flagged
                   ``is_simulated=True`` so they can never be confused with real money.
    ``sandbox``  — provider test environment with test merchant credentials.
    ``live``     — real merchant credentials, real money.
    """

    MOCK = "mock"
    SANDBOX = "sandbox"
    LIVE = "live"


_INSECURE_SECRET_MARKERS = ("change-me", "changeme", "secret", "placeholder")


def _split_csv(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # Validation errors must never echo raw env values (they contain secrets).
        hide_input_in_errors=True,
    )

    # --- General -------------------------------------------------------------
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    project_name: str = "Online Store"
    timezone: str = "Asia/Tashkent"
    default_language: str = "uz"
    default_currency: str = "UZS"
    log_level: str = "INFO"
    log_json: bool = True

    # --- HTTP API ------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    public_base_url: str = "http://localhost:8000"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    trusted_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])

    # --- Database ------------------------------------------------------------
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://store:store@localhost:5432/online_store"
    )
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_echo: bool = False

    # --- Redis ---------------------------------------------------------------
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    # --- Auth ----------------------------------------------------------------
    jwt_secret_key: SecretStr = SecretStr("change-me-in-development-only-0123456789abcdef")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_ttl_days: int = Field(default=14, ge=1, le=90)
    # Base URL the bot uses to reach the API over the internal Docker network.
    api_internal_url: str = "http://api:8000"
    # Shared secret the bot uses to call customer endpoints on behalf of a Telegram user.
    bot_api_secret: SecretStr = SecretStr("change-me-bot-api-secret-0123456789abcdef")

    # --- Telegram ------------------------------------------------------------
    bot_token: SecretStr | None = None
    # Telegram IDs allowed to receive staff notifications from the bot.
    telegram_admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # --- Uploads / storage ---------------------------------------------------
    storage_backend: str = "local"
    media_root: str = "/app/media"
    media_url: str = "/media"
    max_upload_size_mb: int = Field(default=5, ge=1, le=50)

    # --- Payments ------------------------------------------------------------
    payment_mode: PaymentMode = PaymentMode.MOCK
    click_service_id: str | None = None
    click_merchant_id: str | None = None
    click_merchant_user_id: str | None = None
    click_secret_key: SecretStr | None = None
    payme_merchant_id: str | None = None
    payme_secret_key: SecretStr | None = None
    payme_checkout_url: str | None = None

    # --- Orders --------------------------------------------------------------
    # Unpaid online-payment orders release their stock reservation after this.
    order_reservation_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)

    # --- Rate limiting -------------------------------------------------------
    rate_limit_login_per_minute: int = Field(default=10, ge=1)

    @field_validator(
        "bot_token",
        "click_service_id",
        "click_merchant_id",
        "click_merchant_user_id",
        "click_secret_key",
        "payme_merchant_id",
        "payme_secret_key",
        "payme_checkout_url",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        # `BOT_TOKEN=` in a .env file must mean "not configured", not an empty secret.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="before")
    @classmethod
    def _parse_csv_lists(cls, data: object) -> object:
        if isinstance(data, dict):
            for key in ("cors_origins", "trusted_hosts", "telegram_admin_ids"):
                for k in (key, key.upper()):
                    if k in data:
                        data[k] = _split_csv(data[k])
        return data

    @model_validator(mode="after")
    def _validate_production(self) -> Self:
        if self.environment is not Environment.PRODUCTION:
            return self
        problems: list[str] = []
        for name in ("jwt_secret_key", "bot_api_secret"):
            secret: SecretStr = getattr(self, name)
            raw = secret.get_secret_value()
            if len(raw) < 32 or any(m in raw.lower() for m in _INSECURE_SECRET_MARKERS):
                problems.append(f"{name.upper()} must be a random value of 32+ characters")
        if self.debug:
            problems.append("DEBUG must be false in production")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list explicit origins in production")
        if self.payment_mode is PaymentMode.LIVE:
            if not (self.click_service_id and self.click_merchant_id and self.click_secret_key):
                problems.append("Click credentials are required when PAYMENT_MODE=live")
            if not (self.payme_merchant_id and self.payme_secret_key):
                problems.append("Payme credentials are required when PAYMENT_MODE=live")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def database_url_str(self) -> str:
        return str(self.database_url)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
