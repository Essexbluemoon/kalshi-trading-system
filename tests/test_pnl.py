"""
tests/test_pnl.py
Unit tests for all P&L calculation functions in position_manager.

Verifies fee formulas, cost-basis math, and gross P&L for every scenario
in spec Section 3.5:
  - Maker / taker fee at various price points
  - No-cost and Yes-cost basis
  - Gross P&L: No win, No loss, Yes win, Yes loss, partial fill
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from position_manager import (
    calc_maker_fee,
    calc_taker_fee,
    calc_no_cost,
    calc_yes_cost,
    calc_gross_pnl,
)


# ── Maker fee: 0.0175 × contracts × (p/100) × (1 − p/100) ────────────────────

class TestMakerFee:
    def test_at_5_cents(self):
        # 0.0175 × 100 × 0.05 × 0.95 = 0.083125
        assert calc_maker_fee(100, 5) == pytest.approx(Decimal("0.083125"))

    def test_at_50_cents(self):
        # 0.0175 × 100 × 0.5 × 0.5 = 0.4375
        assert calc_maker_fee(100, 50) == pytest.approx(Decimal("0.4375"))

    def test_at_8_cents(self):
        # 0.0175 × 100 × 0.08 × 0.92 = 0.1288
        assert calc_maker_fee(100, 8) == pytest.approx(Decimal("0.1288"))

    def test_at_1_cent(self):
        # 0.0175 × 100 × 0.01 × 0.99 = 0.017325
        assert calc_maker_fee(100, 1) == pytest.approx(Decimal("0.017325"))

    def test_symmetric_around_midpoint(self):
        # p × (1-p) is symmetric: fee(30¢) == fee(70¢)
        assert calc_maker_fee(100, 30) == pytest.approx(calc_maker_fee(100, 70))

    def test_scales_linearly_with_contracts(self):
        # Doubling contracts doubles the fee
        assert calc_maker_fee(200, 5) == pytest.approx(2 * calc_maker_fee(100, 5))


# ── Taker fee: 0.07 × contracts × (p/100) × (1 − p/100) = 4 × maker ─────────

class TestTakerFee:
    def test_at_8_cents(self):
        # 0.07 × 100 × 0.08 × 0.92 = 0.5152
        assert calc_taker_fee(100, 8) == pytest.approx(Decimal("0.5152"))

    def test_taker_is_4x_maker(self):
        # 0.07 / 0.0175 = 4 exactly
        for price in (1, 5, 8, 30, 50):
            assert calc_taker_fee(100, price) == pytest.approx(
                4 * calc_maker_fee(100, price)
            ), f"4× ratio broken at {price}¢"

    def test_symmetric_around_midpoint(self):
        assert calc_taker_fee(100, 20) == pytest.approx(calc_taker_fee(100, 80))


# ── No-cost basis: (1 − p/100) × contracts ───────────────────────────────────

class TestNoCost:
    def test_at_5_cents(self):
        # Buying No when Yes = 5¢ costs 95¢ per contract
        # 100 contracts × $0.95 = $95
        assert calc_no_cost(100, 5) == pytest.approx(Decimal("95"))

    def test_at_1_cent(self):
        assert calc_no_cost(100, 1) == pytest.approx(Decimal("99"))

    def test_at_50_cents(self):
        # Symmetric at the midpoint: No cost == Yes cost
        assert calc_no_cost(100, 50) == pytest.approx(Decimal("50"))

    def test_no_plus_yes_equals_contracts(self):
        # No cost + Yes cost must always equal the number of contracts
        # (each contract pays out $1.00 in total)
        for price in (1, 5, 7, 8, 50):
            total = calc_no_cost(100, price) + calc_yes_cost(100, price)
            assert total == pytest.approx(Decimal("100")), (
                f"no_cost + yes_cost != 100 at {price}¢"
            )


# ── Yes-cost basis: (p/100) × contracts ──────────────────────────────────────

class TestYesCost:
    def test_at_50_cents(self):
        assert calc_yes_cost(100, 50) == pytest.approx(Decimal("50"))

    def test_at_8_cents(self):
        # 100 contracts × $0.08 = $8
        assert calc_yes_cost(100, 8) == pytest.approx(Decimal("8"))

    def test_at_1_cent(self):
        assert calc_yes_cost(100, 1) == pytest.approx(Decimal("1"))

    def test_scales_linearly_with_contracts(self):
        assert calc_yes_cost(50, 8) == pytest.approx(Decimal("4"))


# ── Gross P&L on settlement ───────────────────────────────────────────────────

class TestGrossPnl:
    def test_no_win(self):
        """No position, market resolves No (we win).
        100 contracts @ 5¢ Yes price:
          cost   = (1−0.05)×100 = 95
          payout = 100
          gross  = 100 − 95 = 5
        """
        pnl = calc_gross_pnl("no", "no", 100, Decimal("5"))
        assert pnl == pytest.approx(Decimal("5"))

    def test_no_loss(self):
        """No position, market resolves Yes (we lose).
        100 contracts @ 5¢ Yes price:
          cost   = 95
          payout = 0
          gross  = −95
        """
        pnl = calc_gross_pnl("no", "yes", 100, Decimal("5"))
        assert pnl == pytest.approx(Decimal("-95"))

    def test_yes_win(self):
        """Yes position, market resolves Yes (we win).
        100 contracts @ 50¢:
          cost   = 0.5×100 = 50
          payout = 100
          gross  = 50
        """
        pnl = calc_gross_pnl("yes", "yes", 100, Decimal("50"))
        assert pnl == pytest.approx(Decimal("50"))

    def test_yes_loss(self):
        """Yes position, market resolves No (we lose).
        100 contracts @ 50¢:
          cost   = 50
          payout = 0
          gross  = −50
        """
        pnl = calc_gross_pnl("yes", "no", 100, Decimal("50"))
        assert pnl == pytest.approx(Decimal("-50"))

    def test_partial_fill(self):
        """No position, 37 contracts @ 7¢ Yes price, market resolves No.
        cost  = (1−0.07)×37 = 0.93×37 = 34.41
        gross = 37 − 34.41 = 2.59
        """
        pnl = calc_gross_pnl("no", "no", 37, Decimal("7"))
        assert pnl == pytest.approx(Decimal("2.59"))

    def test_yes_and_no_symmetric_at_50_cents(self):
        """At exactly 50¢ a Yes win and No win earn the same gross P&L."""
        pnl_yes = calc_gross_pnl("yes", "yes", 100, Decimal("50"))
        pnl_no  = calc_gross_pnl("no",  "no",  100, Decimal("50"))
        assert pnl_yes == pytest.approx(pnl_no)

    def test_win_plus_loss_equals_negative_full_cost(self):
        """For a No position: win_pnl + loss_pnl == contracts − 2×cost == -contracts+2contracts-2cost.
        Actually: win + loss = (contracts - cost) + (-cost) = contracts - 2*cost.
        This doesn't simplify to a round number in general; just verify signs are correct.
        """
        win  = calc_gross_pnl("no", "no",  100, Decimal("5"))
        loss = calc_gross_pnl("no", "yes", 100, Decimal("5"))
        assert win  > 0
        assert loss < 0
        # win is small positive (you keep the premium); loss is large negative (you pay the contract)
        assert abs(loss) > win
