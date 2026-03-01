"""
tests/test_reconcile.py
Verifies the core accounting identity and benchmark-drift alert logic.

Accounting identity (spec Section 5.2):
  sum(trades.gross_cost_usd)              — total capital ever deployed
  == sum(positions.total_cost_usd)        — cost of current open positions
   + sum(position_history.total_cost_usd) — cost of settled positions

Benchmark drift (spec Section 5.2, Panel 5):
  |actual_win_rate − expected_win_rate| / expected_win_rate > 0.05  → alert
"""
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

import pytest

import models


# ── Helper: the drift check extracted as a pure function ─────────────────────
# Phase 3 will implement _check_benchmark_drift(db_session) against the DB;
# here we test the underlying math without the DB dependency.

def _drift_frac(actual: float, expected: float) -> float:
    """Relative drift as a fraction of the expected value."""
    if expected == 0:
        return 0.0
    return abs(actual - expected) / expected


# ── Accounting identity ───────────────────────────────────────────────────────

class TestAccountingIdentity:
    def test_accounting_identity(self, db_session):
        """
        Create two markets with known trades:
          Market A (open):    200 No @ 5¢  → gross_cost = (1−0.05)×200 = 190
          Market B (settled): 100 No @ 7¢  → gross_cost = (1−0.07)×100 = 93
          Total fills cost = 283

        Position for A:           total_cost = 190
        PositionHistory for B:    total_cost = 93
        Identity: 190 + 93 == 283 ✓
        """
        from sqlalchemy import select, func

        now = datetime(2025, 1, 1, tzinfo=timezone.utc)

        # Markets
        mkt_a = models.Market(ticker="RECON-A", status="open",     event_prefix="RECTEST")
        mkt_b = models.Market(ticker="RECON-B", status="resolved", event_prefix="RECTEST",
                               result="no")
        db_session.add_all([mkt_a, mkt_b])
        db_session.flush()

        # Trades
        trade_a = models.Trade(
            trade_id="RECON-T001", market_ticker="RECON-A",
            side="no", action="buy", price_cents=5, contracts=200,
            gross_cost_usd=Decimal("190"), fee_usd=Decimal("0"),
            filled_at=now,
        )
        trade_b = models.Trade(
            trade_id="RECON-T002", market_ticker="RECON-B",
            side="no", action="buy", price_cents=7, contracts=100,
            gross_cost_usd=Decimal("93"), fee_usd=Decimal("0"),
            filled_at=now,
        )
        db_session.add_all([trade_a, trade_b])
        db_session.flush()

        # Open position for market A
        pos = models.Position(
            market_ticker="RECON-A", side="no",
            net_contracts=200, avg_price_cents=Decimal("5"),
            total_cost_usd=Decimal("190"), total_fees_usd=Decimal("0"),
            opened_at=now,
        )
        db_session.add(pos)
        db_session.flush()

        # Settled position for market B (resolved No — we won)
        ph = models.PositionHistory(
            market_ticker="RECON-B", side="no",
            net_contracts=100, avg_price_cents=Decimal("7"),
            total_cost_usd=Decimal("93"), total_fees_usd=Decimal("0"),
            result="no", won=True,
            gross_pnl_usd=Decimal("7"), net_pnl_usd=Decimal("7"),
            settled_at=now, days_held=Decimal("1"),
        )
        db_session.add(ph)
        db_session.flush()

        # ── Assert identity ────────────────────────────────────────────────────
        fills_total = db_session.execute(
            select(func.sum(models.Trade.gross_cost_usd))
        ).scalar()

        open_cost = db_session.execute(
            select(func.sum(models.Position.total_cost_usd))
        ).scalar()

        settled_cost = db_session.execute(
            select(func.sum(models.PositionHistory.total_cost_usd))
        ).scalar()

        assert fills_total == pytest.approx(Decimal("283"))
        assert open_cost   == pytest.approx(Decimal("190"))
        assert settled_cost == pytest.approx(Decimal("93"))
        assert fills_total == pytest.approx(open_cost + settled_cost), (
            "Accounting identity violated: fills != open_cost + settled_cost"
        )


# ── Benchmark drift alerts ────────────────────────────────────────────────────

class TestDriftAlerts:
    """
    Verify the drift-threshold logic that _check_benchmark_drift will use.

    Threshold (spec): alert if relative drift > 5%.
    """

    def test_no_alert_within_threshold(self):
        """4.3 % relative drift — below the 5 % threshold, no alert."""
        actual   = 0.67
        expected = 0.70
        drift = _drift_frac(actual, expected)
        assert drift < 0.05, f"Expected no alert but drift={drift:.3f}"

    def test_alert_fires_above_threshold(self):
        """28.6 % relative drift — well above the 5 % threshold, alert fires."""
        actual   = 0.50
        expected = 0.70
        drift = _drift_frac(actual, expected)
        assert drift > 0.05, f"Expected alert to fire but drift={drift:.3f}"

    def test_near_threshold_cases(self):
        """4.9 % drift should not trigger; 5.1 % drift should trigger."""
        # Slightly under 5 %: actual win rate is 4.9 % below expected
        assert _drift_frac(0.70 * (1 - 0.049), 0.70) < 0.05
        # Slightly over 5 %: actual win rate is 5.1 % below expected
        assert _drift_frac(0.70 * (1 - 0.051), 0.70) > 0.05

    def test_zero_expected_does_not_crash(self):
        """If expected win rate is 0, drift check must not divide by zero."""
        assert _drift_frac(0.50, 0.0) == 0.0

    def test_perfect_match_no_alert(self):
        """Actual == expected → drift == 0."""
        assert _drift_frac(0.65, 0.65) == pytest.approx(0.0)
