"""
kalshi_client.py
Wrapper around the pykalshi library.
Provides typed methods for fills, market metadata, and settlement results.
Fully implemented in Phase 3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Phase 3: import pykalshi and implement all methods
# from pykalshi import KalshiClient as _KalshiClient


class KalshiClient:
    """
    Thin wrapper around pykalshi that provides only the API surface
    the ingestion service needs.
    """

    def __init__(self, api_key: str, api_secret: str, env: str = "prod") -> None:
        """
        Args:
            api_key: Kalshi API key
            api_secret: Kalshi API secret
            env: "prod" or "demo"
        """
        self.env = env
        # Phase 3: initialise pykalshi client here
        raise NotImplementedError("KalshiClient implemented in Phase 3")

    # ── Fills ──────────────────────────────────────────────────────────────────

    def get_fills(self, since: datetime | None = None) -> list[dict[str, Any]]:
        """
        Fetch all portfolio fills since `since`.
        Returns a list of raw fill dicts from the Kalshi API.
        Endpoint: GET /portfolio/fills
        """
        raise NotImplementedError

    # ── Market metadata ────────────────────────────────────────────────────────

    def get_market(self, ticker: str) -> dict[str, Any]:
        """
        Fetch metadata for a single market.
        Endpoint: GET /markets/{ticker}
        """
        raise NotImplementedError

    def get_markets_batch(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Fetch metadata for multiple markets in one or more API calls."""
        raise NotImplementedError

    # ── Settlement / results ───────────────────────────────────────────────────

    def get_settled_markets(self, since: datetime | None = None) -> list[dict[str, Any]]:
        """
        Fetch markets that have resolved (result=yes|no) since `since`.
        Endpoint: GET /markets?status=resolved&...
        """
        raise NotImplementedError

    # ── Current prices ─────────────────────────────────────────────────────────

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """
        Fetch current order book for mark-to-market pricing.
        Returns yes_bid, yes_ask, no_bid, no_ask.
        """
        raise NotImplementedError
