"""
ingest_markets.py
Fetches market metadata and resolution results from the Kalshi API
and keeps the markets table current.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def upsert_market(market_data: dict[str, Any], db_session) -> bool:
    """
    Insert or update a market row from a raw Kalshi API market dict.

    Uses a get-or-create pattern so it is safe to call with every fill
    even if the market already exists.

    Returns True if a new market was inserted, False if updated.
    """
    import models

    ticker = (market_data.get("ticker") or "").upper()
    if not ticker:
        return False

    existing = db_session.get(models.Market, ticker)
    is_new = existing is None

    event_ticker = market_data.get("event_ticker") or ""
    event_prefix = _parse_event_prefix(event_ticker) or _parse_event_prefix(ticker)

    status_raw = market_data.get("status")
    status_str = status_raw.value if hasattr(status_raw, "value") else (status_raw or "")

    close_time  = _parse_dt(market_data.get("close_time") or market_data.get("expiration_time"))
    created_at  = _parse_dt(market_data.get("created_time"))

    result = market_data.get("result")
    if result and hasattr(result, "value"):
        result = result.value

    resolved_at = None
    if status_str in ("finalized", "settled", "resolved") and result:
        resolved_at = _parse_dt(market_data.get("expiration_time") or market_data.get("close_time"))

    if is_new:
        mkt = models.Market(
            ticker=ticker,
            title=market_data.get("title"),
            event_prefix=event_prefix,
            status=_normalise_status(status_str),
            result=result,
            close_time=close_time,
            resolved_at=resolved_at,
            created_at=created_at,
        )
        db_session.add(mkt)
    else:
        if status_str:
            existing.status = _normalise_status(status_str)
        if result:
            existing.result = result
        if resolved_at:
            existing.resolved_at = resolved_at
        if close_time and not existing.close_time:
            existing.close_time = close_time
        if event_prefix and not existing.event_prefix:
            existing.event_prefix = event_prefix

    return is_new


def fetch_and_apply_resolutions(db_session, kalshi_client) -> int:
    """
    Pull settlement records from the portfolio, update market results in DB,
    and return the number of markets newly marked as resolved.
    """
    import models
    from sqlalchemy import select

    open_markets = db_session.execute(
        select(models.Market).where(
            models.Market.status.notin_(["resolved", "finalized"])
        )
    ).scalars().all()

    if not open_markets:
        return 0

    open_tickers = {m.ticker for m in open_markets}
    settlements = kalshi_client.get_settlements()
    resolved = 0

    for s in settlements:
        ticker = (s.get("ticker") or "").upper()
        if ticker not in open_tickers:
            continue

        result = s.get("market_result")  # "yes" | "no"
        if not result:
            continue

        mkt = db_session.get(models.Market, ticker)
        if mkt and mkt.result != result:
            mkt.result = result
            mkt.status = "resolved"
            if s.get("settled_time"):
                mkt.resolved_at = _parse_dt(s["settled_time"])
            resolved += 1
            logger.info("Market resolved: %s -> %s", ticker, result)

    return resolved


def _parse_event_prefix(event_ticker: str) -> str:
    """Extract the leading uppercase alpha-numeric prefix from an event ticker.

    Examples:
      "KXATPMATCH-2025-FEDERER-DJOKOVIC" -> "KXATPMATCH"
      "CABINETMUSK-WEEK3"               -> "CABINETMUSK"
    """
    m = re.match(r"^([A-Z0-9]+)", (event_ticker or "").upper())
    return m.group(1) if m else ""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_status(raw: str) -> str:
    """Map Kalshi API status strings to our schema values: open | closed | resolved."""
    mapping = {
        "open":      "open",
        "active":    "open",
        "closed":    "closed",
        "settled":   "resolved",
        "finalized": "resolved",
        "resolved":  "resolved",
    }
    return mapping.get((raw or "").lower(), raw or "open")


def _parse_dt(ts: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp string to a timezone-aware datetime."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
