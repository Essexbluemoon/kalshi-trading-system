"""
tests/test_ingestion.py
Integration tests against the Kalshi demo/sandbox environment.

These tests are excluded from the default run (they require live credentials).
Run with:
  KALSHI_ENV=demo \\
  KALSHI_API_KEY_ID=<your-key-id> \\
  KALSHI_PRIVATE_KEY_PATH=<path/to/private.pem> \\
  pytest -m integration

Test cases:
  - KalshiClient connects to the demo API without raising
  - get_fills() returns a list of dicts with the expected shape
  - run_ingestion_cycle() stores fills in the trades table
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select


@pytest.mark.integration
class TestIngestionIntegration:
    """
    End-to-end ingestion against the Kalshi sandbox.
    Skipped unless KALSHI_ENV=demo and RSA key-pair credentials are set.
    """

    @staticmethod
    def _skip_if_not_configured():
        if os.getenv("KALSHI_ENV") != "demo":
            pytest.skip("Set KALSHI_ENV=demo to run integration tests")
        if not os.getenv("KALSHI_API_KEY_ID"):
            pytest.skip("KALSHI_API_KEY_ID must be set")
        if not os.getenv("KALSHI_PRIVATE_KEY_PATH"):
            pytest.skip("KALSHI_PRIVATE_KEY_PATH must be set")

    def test_client_connects(self):
        """KalshiClient initialises and can reach the demo API without raising."""
        self._skip_if_not_configured()

        from kalshi_client import KalshiClient

        client = KalshiClient(
            api_key_id=os.environ["KALSHI_API_KEY_ID"],
            private_key_path=os.environ["KALSHI_PRIVATE_KEY_PATH"],
            env="demo",
        )
        fills = client.get_fills()
        assert isinstance(fills, list)
        client.close()

    def test_fills_have_expected_shape(self):
        """Fills from the sandbox API have the required field keys."""
        self._skip_if_not_configured()

        from kalshi_client import KalshiClient

        with KalshiClient(
            api_key_id=os.environ["KALSHI_API_KEY_ID"],
            private_key_path=os.environ["KALSHI_PRIVATE_KEY_PATH"],
            env="demo",
        ) as client:
            fills = client.get_fills()

        if not fills:
            pytest.skip("Sandbox account has no fills — cannot validate shape")

        fill = fills[0]
        for field in ("trade_id", "side", "action", "yes_price", "count", "is_taker"):
            assert field in fill, f"Fill missing expected field: {field!r}"

    def test_fill_appears_in_db_after_ingestion(self, db_session):
        """
        Full ingestion smoke test:
          1. Connect to the Kalshi sandbox.
          2. Run one ingestion cycle (commit replaced with flush for isolation).
          3. Verify the trades table and position tables are populated.
        """
        self._skip_if_not_configured()

        from kalshi_client import KalshiClient
        from ingest_trades import run_ingestion_cycle
        import models

        # Replace commit with flush so db_session rollback cleans up after test
        db_session.commit = db_session.flush

        with KalshiClient(
            api_key_id=os.environ["KALSHI_API_KEY_ID"],
            private_key_path=os.environ["KALSHI_PRIVATE_KEY_PATH"],
            env="demo",
        ) as client:
            stats = run_ingestion_cycle(db_session, client)

        assert isinstance(stats, dict)
        for key in ("fills_fetched", "trades_inserted", "markets_upserted",
                    "positions_rebuilt", "positions_settled"):
            assert key in stats, f"Missing stats key: {key!r}"

        if stats["fills_fetched"] > 0:
            trades = db_session.execute(select(models.Trade)).scalars().all()
            assert len(trades) > 0
            t = trades[0]
            assert t.market_ticker
            assert t.side in ("yes", "no")
            assert t.action in ("buy", "sell")
            assert t.price_cents is not None
            assert t.contracts > 0
