"""
config.py
Loads environment variables from .env and exposes typed settings.

Authentication note:
  Kalshi's API uses RSA key-pair auth (as of 2024).
  KALSHI_API_KEY_ID    — the key ID shown in the Kalshi dashboard

  Private key can be supplied in one of two ways:
  1. KALSHI_PRIVATE_KEY      — PEM contents as an env var (Railway/cloud deploy)
                               Newlines may be stored as literal \\n; both forms work.
  2. KALSHI_PRIVATE_KEY_PATH — path to a PEM file (local dev)
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (one level up from ingestion/)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)


@dataclass
class Settings:
    kalshi_api_key_id: str
    kalshi_private_key_path: str
    kalshi_env: str          # "prod" | "demo"
    database_url: str
    poll_interval_seconds: int
    api_key: str             # internal Bearer token for the FastAPI service


def _resolve_private_key() -> str:
    """
    Return a filesystem path to the RSA private key PEM file.

    On Railway (and other cloud platforms) the PEM content is injected via the
    KALSHI_PRIVATE_KEY env var.  We write it to a secure tempfile so the rest
    of the codebase can use a plain file path without change.

    For local development, KALSHI_PRIVATE_KEY_PATH points directly to the file.
    """
    pem_content = os.getenv("KALSHI_PRIVATE_KEY")
    if pem_content:
        # Normalise escaped newlines (e.g. Railway stores multi-line vars with \n)
        pem_content = pem_content.replace("\\n", "\n")
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".pem",
            delete=False,
            prefix="kalshi_key_",
        )
        tmp.write(pem_content)
        tmp.flush()
        tmp.close()
        return tmp.name

    # Fallback: explicit file path (local dev)
    return _require("KALSHI_PRIVATE_KEY_PATH")


def _normalise_db_url(url: str) -> str:
    """Railway's PostgreSQL plugin injects postgres:// but SQLAlchemy 2.0+ requires postgresql://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_settings() -> Settings:
    """Return validated settings from environment variables."""
    return Settings(
        kalshi_api_key_id=_require("KALSHI_API_KEY_ID"),
        kalshi_private_key_path=_resolve_private_key(),
        kalshi_env=os.getenv("KALSHI_ENV", "prod"),
        database_url=_normalise_db_url(_require("DATABASE_URL")),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        api_key=_require("API_KEY"),
    )


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value
