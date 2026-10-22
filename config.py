"""
Configuration module — loads and validates all environment variables.
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Config:
    bot_token: str
    admin_ids: List[int]
    channel_id: int
    db_path: str = "bot.db"

    @classmethod
    def from_env(cls) -> "Config":
        """Load and validate configuration from environment variables."""
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ValueError("BOT_TOKEN environment variable is required.")

        raw_admins = os.getenv("ADMIN_IDS", "").strip()
        if not raw_admins:
            raise ValueError("ADMIN_IDS environment variable is required.")
        try:
            admin_ids = [int(x.strip()) for x in raw_admins.split(",") if x.strip()]
        except ValueError:
            raise ValueError("ADMIN_IDS must be a comma-separated list of integers.")
        if not admin_ids:
            raise ValueError("ADMIN_IDS must contain at least one admin ID.")

        raw_channel = os.getenv("CHANNEL_ID", "").strip()
        if not raw_channel:
            raise ValueError("CHANNEL_ID environment variable is required.")
        try:
            channel_id = int(raw_channel)
        except ValueError:
            raise ValueError("CHANNEL_ID must be an integer (e.g. -1001234567890).")

        db_path = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"

        return cls(
            bot_token=bot_token,
            admin_ids=admin_ids,
            channel_id=channel_id,
            db_path=db_path,
        )

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


# Singleton — imported everywhere
config = Config.from_env()
