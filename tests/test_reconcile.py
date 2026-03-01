"""
tests/test_reconcile.py
Verifies the core accounting identity:
  sum(open position costs) + sum(settled net_pnl) == sum(all fill gross costs)

Also verifies that benchmark drift alerts fire correctly.

Implemented in Phase 2.5.
"""
import pytest


class TestAccountingIdentity:
    def test_accounting_identity(self):
        """Open positions + settled P&L must equal sum of all fills."""
        pytest.skip("Implemented in Phase 2.5")


class TestDriftAlerts:
    def test_no_alert_within_threshold(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_alert_fires_above_threshold(self):
        pytest.skip("Implemented in Phase 2.5")
