"""
kalshi_client.py
Thin wrapper around pykalshi that provides only the API surface the ingestion
service needs, returning plain dicts so callers never depend on pykalshi models.

Authentication:
    Kalshi uses RSA key-pair auth. You need:
      - api_key_id: the key ID from the Kalshi dashboard
      - private_key_path: path to the downloaded PEM file

Usage:
    client = KalshiClient(api_key_id="...", private_key_path="...", env="prod")
    fills = client.get_fills(since=datetime(2025, 1, 1, tzinfo=timezone.utc))
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class KalshiClient:
    """
    Thin wrapper around pykalshi that provides only the API surface
    the ingestion service needs.
    """

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        env: str = "prod",
    ) -> None:
        from pykalshi import KalshiClient as _Pykalshi

        self._client = _Pykalshi(
            api_key_id=api_key_id,
            private_key_path=private_key_path,
            demo=(env == "demo"),
        )
        self.env = env
        logger.info("KalshiClient initialised (env=%s)", env)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KalshiClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ── Fills ──────────────────────────────────────────────────────────────────

    def get_fills(self, since: datetime | None = None) -> list[dict[str, Any]]:
        """
        Fetch all portfolio fills, optionally since `since`.

        Returns a list of dicts with keys:
          trade_id, ticker, order_id, side, action, count, yes_price,
          no_price, is_taker, fee_cost, created_time, ts
        """
        min_ts = int(since.timestamp()) if since else None
        fills = self._client.portfolio.get_fills(
            min_ts=min_ts,
            limit=200,
            fetch_all=True,
        )
        return [f.model_dump() for f in fills]

    # ── Market metadata ────────────────────────────────────────────────────────

    def get_market(self, ticker: str) -> dict[str, Any]:
        """
        Fetch metadata for a single market.
        Returns a dict matching MarketModel fields.
        """
        market = self._client.get_market(ticker)
        return market.model.model_dump()

    def get_markets_batch(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Fetch metadata for multiple markets in one paginated call."""
        if not tickers:
            return []
        markets = self._client.get_markets(tickers=tickers, limit=200, fetch_all=True)
        return [m.model.model_dump() for m in markets]

    # ── Settlements ────────────────────────────────────────────────────────────

    def get_settlements(self, since: datetime | None = None) -> list[dict[str, Any]]:
        """
        Fetch settled positions from the portfolio.

        Returns a list of dicts with keys:
          ticker, event_ticker, market_result, yes_count, no_count,
          yes_total_cost, no_total_cost, revenue, value, fee_cost, settled_time
        """
        settlements = self._client.portfolio.get_settlements(fetch_all=True)
        result = [s.model_dump() for s in settlements]
        if since:
            since_ts = since.timestamp()
            result = [
                s for s in result
                if s.get("settled_time") and
                _parse_ts(s["settled_time"]) >= since_ts
            ]
        return result

    # ── Current prices ─────────────────────────────────────────────────────────

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """
        Return current best-bid/ask for a market.
        Keys: yes_bid, yes_ask, no_bid, no_ask  (int cents; any may be None)
        """
        market = self._client.get_market(ticker)
        m = market.model
        return {
            "yes_bid": m.yes_bid,
            "yes_ask": m.yes_ask,
            "no_bid":  m.no_bid,
            "no_ask":  m.no_ask,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_ts(ts_str: str) -> float:
    """Parse an ISO-8601 timestamp string to a Unix timestamp float."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0
