"""
config.py
Loads environment variables from .env and exposes typed settings.
Implemented in Phase 3.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (one level up from ingestion/)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass
class Settings:
    kalshi_api_key: str
    kalshi_api_secret: str
    kalshi_env: str          # "prod" | "demo"
    database_url: str
    poll_interval_seconds: int
    api_key: str             # internal API key for service-to-API calls


def get_settings() -> Settings:
    """Return validated settings from environment variables."""
    return Settings(
        kalshi_api_key=_require("KALSHI_API_KEY"),
        kalshi_api_secret=_require("KALSHI_API_SECRET"),
        kalshi_env=os.getenv("KALSHI_ENV", "prod"),
        database_url=_require("DATABASE_URL"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        api_key=_require("API_KEY"),
    )


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value
