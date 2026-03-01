"""
ingest_markets.py
Fetches market metadata and resolution results from the Kalshi API
and keeps the markets table current.

Full implementation in Phase 3.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def upsert_market(market_data: dict[str, Any], db_session) -> bool:
    """
    Insert or update a market row from raw Kalshi API market dict.
    Returns True if a new market was inserted.
    """
    raise NotImplementedError


def fetch_and_apply_resolutions(db_session, kalshi_client) -> int:
    """
    Find markets that have closed since last check, fetch results,
    and update markets.result + markets.resolved_at.
    Returns number of markets resolved.
    """
    raise NotImplementedError


def _parse_event_prefix(event_ticker: str) -> str:
    """Extract the leading alpha-numeric prefix from an event ticker."""
    import re
    m = re.match(r"^([A-Z0-9]+)", (event_ticker or "").upper())
    return m.group(1) if m else ""
