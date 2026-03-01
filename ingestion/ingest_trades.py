"""
ingest_trades.py
Main ingestion loop. Fetches fills from Kalshi, upserts markets,
inserts trades, and triggers position + daily rollup updates.

Full implementation in Phase 3. See spec Section 3.3.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_ingestion_cycle(db_session, kalshi_client) -> dict:
    """
    Execute one full ingestion cycle:
      1. Fetch fills since last_ingested_at
      2. Upsert market metadata
      3. Insert new trades with category classification
      4. Rebuild open positions
      5. Fetch + apply market resolutions
      6. Move settled positions to history with P&L
      7. Update daily_performance rollup
      8. Run reconcile alerts

    Returns:
        dict with keys: fills_fetched, trades_inserted, markets_upserted,
                        positions_updated, positions_settled
    """
    raise NotImplementedError("Implemented in Phase 3")


def _get_last_ingested_at(db_session) -> datetime | None:
    """Query trades table for the most recent filled_at timestamp."""
    raise NotImplementedError


def _classify_trade(ticker: str, db_session) -> tuple[str, str, str]:
    """
    Classify a trade by matching its ticker prefix against the benchmarks table.
    Returns (category, subcategory, event_prefix).
    Flags as 'uncategorized' if prefix not found.
    """
    raise NotImplementedError


def _update_daily_performance(db_session, date: datetime) -> None:
    """Roll up today's settled positions into daily_performance."""
    raise NotImplementedError
