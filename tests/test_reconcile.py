"""
tests/test_reconcile.py
Verifies the core accounting identity, benchmark-drift math, and all five
DB-backed reconcile checks (benchmark drift, uncategorized, position age,
concentration, loss streak).

Accounting identity (spec Section 5.2):
  sum(trades.gross_cost_usd)              — total capital ever deployed
  == sum(positions.total_cost_usd)        — cost of current open positions
   + sum(position_history.total_cost_usd) — cost of settled positions

Benchmark drift (spec Section 5.2, Panel 5):
  |actual_win_rate − expected_win_rate| / expected_win_rate > 0.05  → alert
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

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


# ── DB-backed reconcile check tests ───────────────────────────────────────────

class TestReconcileChecks:
    """
    Tests for the five _check_* functions in reconcile.py, each exercised
    against the SQLite test DB via db_session.

    Each test inserts its own isolated data; the function-scoped rollback in
    db_session ensures full isolation between tests.
    """

    # Unique prefixes / tickers to keep test data identifiable
    _NOW = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)

    # ── Benchmark drift ───────────────────────────────────────────────────────

    def test_drift_alert_fires_when_far_from_benchmark(self, db_session):
        """
        10 settled trades, 5 wins → actual WR = 50%.
        Expected WR = 70% → 28.6% relative drift → alert fires.
        """
        from reconcile import _check_benchmark_drift

        mkt = models.Market(ticker="RCDRFT-MKT", event_prefix="RCDRFT", status="resolved")
        bmark = models.Benchmark(
            event_prefix="RCDRFT", category="Test",
            expected_win_rate=Decimal("0.70"),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()

        for i in range(10):
            db_session.add(models.PositionHistory(
                market_ticker="RCDRFT-MKT", side="no",
                net_contracts=100, avg_price_cents=Decimal("5"),
                total_cost_usd=Decimal("0.95"), total_fees_usd=Decimal("0"),
                result="no" if i < 5 else "yes",
                won=(i < 5),
                gross_pnl_usd=Decimal("0"), net_pnl_usd=Decimal("0"),
                settled_at=self._NOW,
            ))
        db_session.flush()

        alerts = _check_benchmark_drift(db_session)
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "benchmark_drift"
        assert alerts[0].severity in ("warning", "critical")

    def test_drift_no_alert_when_within_threshold(self, db_session):
        """10 settled, 7 wins → actual WR = 70% == expected → drift = 0%, no alert."""
        from reconcile import _check_benchmark_drift

        mkt = models.Market(ticker="RCDRFT2-MKT", event_prefix="RCDRFT2", status="resolved")
        bmark = models.Benchmark(
            event_prefix="RCDRFT2", category="Test",
            expected_win_rate=Decimal("0.70"),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()

        for i in range(10):
            db_session.add(models.PositionHistory(
                market_ticker="RCDRFT2-MKT", side="no",
                net_contracts=100, avg_price_cents=Decimal("5"),
                total_cost_usd=Decimal("0.95"), total_fees_usd=Decimal("0"),
                result="no", won=(i < 7),    # 7 wins, 3 losses → 70%
                gross_pnl_usd=Decimal("0"), net_pnl_usd=Decimal("0"),
                settled_at=self._NOW,
            ))
        db_session.flush()

        alerts = _check_benchmark_drift(db_session)
        assert alerts == []

    def test_drift_no_alert_below_minimum_sample(self, db_session):
        """
        Only 4 settled trades (threshold is 5) → excluded by HAVING clause
        even if drift is 100%.
        """
        from reconcile import _check_benchmark_drift

        mkt = models.Market(ticker="RCDRFT3-MKT", event_prefix="RCDRFT3", status="resolved")
        bmark = models.Benchmark(
            event_prefix="RCDRFT3", category="Test",
            expected_win_rate=Decimal("0.70"),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()

        for _ in range(4):  # one below the minimum of 5
            db_session.add(models.PositionHistory(
                market_ticker="RCDRFT3-MKT", side="no",
                net_contracts=100, avg_price_cents=Decimal("5"),
                total_cost_usd=Decimal("0.95"), total_fees_usd=Decimal("0"),
                result="yes", won=False,        # all losses
                gross_pnl_usd=Decimal("0"), net_pnl_usd=Decimal("0"),
                settled_at=self._NOW,
            ))
        db_session.flush()

        alerts = _check_benchmark_drift(db_session)
        assert alerts == []

    # ── Uncategorized trades ──────────────────────────────────────────────────

    def test_uncategorized_fires_when_no_benchmark_match(self, db_session):
        """A trade whose market has no benchmark entry triggers the alert."""
        from reconcile import _check_uncategorized

        mkt = models.Market(ticker="UNCAT-MKT", event_prefix="RCUNCAT", status="open")
        trade = models.Trade(
            trade_id="UNCAT-T001", market_ticker="UNCAT-MKT",
            side="no", action="buy", price_cents=5, contracts=100,
            fee_usd=Decimal("0"), gross_cost_usd=Decimal("0.95"),
            filled_at=self._NOW,
        )
        # No Benchmark row for event_prefix="RCUNCAT"
        db_session.add_all([mkt, trade])
        db_session.flush()

        alerts = _check_uncategorized(db_session)
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "uncategorized_trade"

    def test_uncategorized_no_alert_when_benchmark_matches(self, db_session):
        """A trade whose market has a matching benchmark produces no alert."""
        from reconcile import _check_uncategorized

        mkt = models.Market(ticker="CATD-MKT", event_prefix="RCCATD", status="open")
        bmark = models.Benchmark(
            event_prefix="RCCATD", category="Test",
            expected_win_rate=Decimal("0.70"),
        )
        trade = models.Trade(
            trade_id="CATD-T001", market_ticker="CATD-MKT",
            side="no", action="buy", price_cents=5, contracts=100,
            fee_usd=Decimal("0"), gross_cost_usd=Decimal("0.95"),
            filled_at=self._NOW,
        )
        db_session.add_all([mkt, bmark, trade])
        db_session.flush()

        alerts = _check_uncategorized(db_session)
        assert alerts == []

    # ── Concentration ─────────────────────────────────────────────────────────

    def test_concentration_fires_when_position_exceeds_10pct(self, db_session):
        """
        Position A = $90, Position B = $10 → total $100.
        A is 90% of capital → alert fires (>10% threshold).
        B is exactly 10% → does NOT fire (check is strictly >10%).
        """
        from reconcile import _check_concentration

        mkt_a = models.Market(ticker="CONCA-MKT", status="open")
        mkt_b = models.Market(ticker="CONCB-MKT", status="open")
        db_session.add_all([mkt_a, mkt_b])
        db_session.flush()

        pos_a = models.Position(
            market_ticker="CONCA-MKT", side="no", net_contracts=100,
            avg_price_cents=Decimal("5"), total_cost_usd=Decimal("90"),
            total_fees_usd=Decimal("0"),
        )
        pos_b = models.Position(
            market_ticker="CONCB-MKT", side="no", net_contracts=100,
            avg_price_cents=Decimal("5"), total_cost_usd=Decimal("10"),
            total_fees_usd=Decimal("0"),
        )
        db_session.add_all([pos_a, pos_b])
        db_session.flush()

        alerts = _check_concentration(db_session)
        alerted_tickers = {a.market_ticker for a in alerts}

        assert "CONCA-MKT" in alerted_tickers   # 90% > 10% threshold
        assert "CONCB-MKT" not in alerted_tickers  # exactly 10% → not strictly >

    def test_concentration_no_alert_when_all_below_threshold(self, db_session):
        """20 equal-sized positions ($5 each = 5% of $100 total) — none exceed 10%."""
        from reconcile import _check_concentration

        for i in range(20):
            ticker = f"CONCSMALL-{i}"
            db_session.add(models.Market(ticker=ticker, status="open"))
            db_session.flush()
            db_session.add(models.Position(
                market_ticker=ticker, side="no", net_contracts=100,
                avg_price_cents=Decimal("5"), total_cost_usd=Decimal("5"),
                total_fees_usd=Decimal("0"),
            ))
        db_session.flush()

        alerts = _check_concentration(db_session)
        assert alerts == []

    # ── Loss streak ───────────────────────────────────────────────────────────

    def test_loss_streak_fires_on_3_consecutive_losses(self, db_session):
        """3 consecutive losses in the same prefix triggers the alert."""
        from reconcile import _check_loss_streak

        mkt = models.Market(ticker="STRK-MKT", event_prefix="RCSTRK", status="resolved")
        db_session.add(mkt)
        db_session.flush()

        for i in range(3):
            db_session.add(models.PositionHistory(
                market_ticker="STRK-MKT", side="no",
                net_contracts=100, avg_price_cents=Decimal("5"),
                total_cost_usd=Decimal("0.95"), total_fees_usd=Decimal("0"),
                result="yes", won=False,
                gross_pnl_usd=Decimal("-0.95"), net_pnl_usd=Decimal("-0.95"),
                settled_at=self._NOW - timedelta(days=i),   # day 0, -1, -2
            ))
        db_session.flush()

        alerts = _check_loss_streak(db_session)
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "loss_streak"
        assert alerts[0].severity == "warning"

    def test_loss_streak_no_alert_when_win_breaks_streak(self, db_session):
        """
        Most-recent result = win, then two losses.
        history[:3] = [win, loss, loss] → not all losses → no alert.
        """
        from reconcile import _check_loss_streak

        mkt = models.Market(ticker="STRK2-MKT", event_prefix="RCSTRK2", status="resolved")
        db_session.add(mkt)
        db_session.flush()

        outcomes = [(True, "no"), (False, "yes"), (False, "yes")]   # win, loss, loss
        for i, (won, result) in enumerate(outcomes):
            db_session.add(models.PositionHistory(
                market_ticker="STRK2-MKT", side="no",
                net_contracts=100, avg_price_cents=Decimal("5"),
                total_cost_usd=Decimal("0.95"), total_fees_usd=Decimal("0"),
                result=result, won=won,
                gross_pnl_usd=Decimal("0"), net_pnl_usd=Decimal("0"),
                settled_at=self._NOW - timedelta(days=i),  # most recent = i=0 (win)
            ))
        db_session.flush()

        alerts = _check_loss_streak(db_session)
        assert alerts == []

    # ── Position age ──────────────────────────────────────────────────────────

    def test_position_age_fires_when_open_past_median(self, db_session):
        """
        Position open 30 days, benchmark median = 7 days → alert fires.
        """
        from reconcile import _check_position_age

        now = datetime.now(timezone.utc)
        mkt = models.Market(ticker="AGE-MKT", event_prefix="RCAGE", status="open")
        bmark = models.Benchmark(
            event_prefix="RCAGE", category="Test",
            expected_win_rate=Decimal("0.70"),
            notes="median_days=7.0",
        )
        pos = models.Position(
            market_ticker="AGE-MKT", side="no", net_contracts=100,
            avg_price_cents=Decimal("5"), total_cost_usd=Decimal("0.95"),
            total_fees_usd=Decimal("0"),
            opened_at=now - timedelta(days=30),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()
        db_session.add(pos)
        db_session.flush()

        alerts = _check_position_age(db_session)
        assert len(alerts) == 1
        assert alerts[0].alert_type.value == "position_age"
        assert alerts[0].market_ticker == "AGE-MKT"

    def test_position_age_no_alert_when_within_median(self, db_session):
        """Position open 1 day, benchmark median = 7 days → no alert."""
        from reconcile import _check_position_age

        now = datetime.now(timezone.utc)
        mkt = models.Market(ticker="AGE2-MKT", event_prefix="RCAGE2", status="open")
        bmark = models.Benchmark(
            event_prefix="RCAGE2", category="Test",
            expected_win_rate=Decimal("0.70"),
            notes="median_days=7.0",
        )
        pos = models.Position(
            market_ticker="AGE2-MKT", side="no", net_contracts=100,
            avg_price_cents=Decimal("5"), total_cost_usd=Decimal("0.95"),
            total_fees_usd=Decimal("0"),
            opened_at=now - timedelta(days=1),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()
        db_session.add(pos)
        db_session.flush()

        alerts = _check_position_age(db_session)
        assert alerts == []

    def test_position_age_no_alert_without_median_in_notes(self, db_session):
        """Benchmark with no median_days in notes → age check is skipped."""
        from reconcile import _check_position_age

        now = datetime.now(timezone.utc)
        mkt = models.Market(ticker="AGE3-MKT", event_prefix="RCAGE3", status="open")
        bmark = models.Benchmark(
            event_prefix="RCAGE3", category="Test",
            expected_win_rate=Decimal("0.70"),
            notes="some_other_note=42",   # no median_days key
        )
        pos = models.Position(
            market_ticker="AGE3-MKT", side="no", net_contracts=100,
            avg_price_cents=Decimal("5"), total_cost_usd=Decimal("0.95"),
            total_fees_usd=Decimal("0"),
            opened_at=now - timedelta(days=30),
        )
        db_session.add_all([mkt, bmark])
        db_session.flush()
        db_session.add(pos)
        db_session.flush()

        alerts = _check_position_age(db_session)
        assert alerts == []
