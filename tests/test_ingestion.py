"""
tests/test_ingestion.py
Integration tests against the Kalshi demo/sandbox environment.

These tests are intentionally excluded from the default test run.
They require live sandbox credentials and a running Kalshi demo account:

  KALSHI_ENV=demo
  KALSHI_API_KEY=<your sandbox key>
  KALSHI_API_SECRET=<your sandbox secret>

Run with:
  pytest -m integration

Test cases:
  - Kalshi API client authenticates successfully
  - Trade fills returned from the API are non-empty and have expected fields
  - Ingestion cycle inserts the fills into the database without errors
"""
from __future__ import annotations

import os

import pytest


@pytest.mark.integration
class TestIngestionIntegration:
    """
    End-to-end ingestion tests.  Skipped unless KALSHI_ENV=demo is set and
    live sandbox credentials are available.
    """

    def test_fill_appears_in_db_after_ingestion(self):
        """
        Smoke-test the full ingestion pipeline:
          1. Connect to Kalshi sandbox.
          2. Fetch recent fills.
          3. Run one ingestion cycle.
          4. Confirm the fills appear in the `trades` table.

        Requires a sandbox account with at least one historical trade.
        Full implementation in Phase 3 alongside the ingestion service.
        """
        if os.getenv("KALSHI_ENV") != "demo":
            pytest.skip("Set KALSHI_ENV=demo and provide sandbox credentials to run")

        # Phase 3 will implement:
        #   from ingestion.kalshi_client import KalshiClient
        #   from ingestion.ingest_trades import ingest_one_cycle
        #   client = KalshiClient()
        #   ingest_one_cycle(client, db_session)
        #   trade = db_session.query(Trade).order_by(Trade.filled_at.desc()).first()
        #   assert trade is not None
        raise NotImplementedError("Implement in Phase 3 alongside ingest_trades.py")
