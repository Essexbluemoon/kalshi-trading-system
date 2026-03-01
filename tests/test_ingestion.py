"""
tests/test_ingestion.py
Integration tests against the Kalshi demo/sandbox environment.

Requires:
  KALSHI_ENV=demo
  KALSHI_API_KEY and KALSHI_API_SECRET set for sandbox account

Test cases (spec Phase 2.5):
  - Place a known trade in sandbox
  - Run ingestion cycle
  - Verify database entry matches fill from API

Implemented in Phase 2.5.
"""
import pytest


@pytest.mark.integration
class TestIngestionIntegration:
    def test_fill_appears_in_db_after_ingestion(self):
        pytest.skip("Implemented in Phase 2.5 — requires Kalshi sandbox credentials")
