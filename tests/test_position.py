"""
tests/test_position.py
Verifies position aggregation logic.

Phase 2.5 tests the pure math layer — trade-weighted average price,
net-contracts accounting, and cost-basis adjustments — without touching
the database.  The Phase 3 `rebuild_positions` / `settle_position` functions
will wire this math into the DB; these tests define the expected behaviour.

Test cases:
  - Multiple fills on same market aggregate correctly (weighted avg price)
  - Partial close reduces net_contracts; cost basis of remaining contracts correct
  - Full close produces net_contracts == 0
  - Gross P&L from settlement chains correctly from position state
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from position_manager import calc_no_cost, calc_yes_cost, calc_gross_pnl


# ── Helpers that mirror the Phase-3 aggregation logic ────────────────────────

def _weighted_avg_price(buy_fills: list[dict]) -> Decimal:
    """
    Compute trade-count-weighted average buy price.

    Each fill dict must have keys: contracts (int), price_cents (int).
    This is the formula `rebuild_positions` will use in Phase 3.
    """
    total_qty = sum(f["contracts"] for f in buy_fills)
    if total_qty == 0:
        return Decimal("0")
    return (
        sum(Decimal(f["price_cents"]) * f["contracts"] for f in buy_fills)
        / total_qty
    )


def _net_contracts(trades: list[dict]) -> int:
    """Sum buys, subtract sells."""
    net = 0
    for t in trades:
        if t["action"] == "buy":
            net += t["contracts"]
        elif t["action"] == "sell":
            net -= t["contracts"]
    return net


# ── Test classes ──────────────────────────────────────────────────────────────

class TestPositionAggregation:
    def test_multiple_fills_same_market(self):
        """Two buy fills on the same market must be aggregated correctly.

        Fill 1: 100 contracts @ 5¢  →  contribution = 500
        Fill 2: 200 contracts @ 7¢  →  contribution = 1400
        Total:  300 contracts, avg = 1900/300 ≈ 6.333…¢
        Total cost: calc_no_cost(100, 5) + calc_no_cost(200, 7) = 95 + 186 = 281
        """
        fills = [
            {"contracts": 100, "price_cents": 5, "action": "buy"},
            {"contracts": 200, "price_cents": 7, "action": "buy"},
        ]

        avg = _weighted_avg_price(fills)
        expected_avg = Decimal("1900") / Decimal("300")
        assert avg == pytest.approx(expected_avg), "Weighted avg price incorrect"

        assert _net_contracts(fills) == 300

        # Total cost must equal the sum of individual No-costs
        total_cost = calc_no_cost(100, 5) + calc_no_cost(200, 7)
        assert total_cost == pytest.approx(Decimal("281"))

    def test_partial_close(self):
        """Selling a subset of contracts reduces net_contracts but leaves
        the average buy price unchanged (we don't re-average on sells).

        Buy 100 @ 5¢  →  net = 100, avg_price = 5¢, cost_basis = 95
        Sell 40        →  net = 60,  avg_price = 5¢  (unchanged)
        Remaining cost = calc_no_cost(60, 5) = 57
        """
        trades = [
            {"contracts": 100, "price_cents": 5, "action": "buy"},
            {"contracts": 40,  "price_cents": 6, "action": "sell"},
        ]

        assert _net_contracts(trades) == 60

        buy_fills = [t for t in trades if t["action"] == "buy"]
        avg = _weighted_avg_price(buy_fills)
        assert avg == pytest.approx(Decimal("5")), "Avg price should not change on partial sell"

        remaining_cost = calc_no_cost(60, int(avg))
        assert remaining_cost == pytest.approx(Decimal("57"))

    def test_full_close(self):
        """Buying then selling all contracts yields net_contracts == 0."""
        trades = [
            {"contracts": 100, "price_cents": 5, "action": "buy"},
            {"contracts": 100, "price_cents": 6, "action": "sell"},
        ]
        assert _net_contracts(trades) == 0

    def test_gross_pnl_from_position_state(self):
        """Verify the P&L computed from aggregated position state is correct.

        100 No contracts @ 5¢ Yes price, settled as No (we win):
          cost  = calc_no_cost(100, 5) = 95
          gross = calc_gross_pnl("no", "no", 100, 5) = 5
        """
        contracts = 100
        avg_price = Decimal("5")
        gross = calc_gross_pnl("no", "no", contracts, avg_price)
        cost  = calc_no_cost(contracts, int(avg_price))
        # gross == contracts - cost
        assert gross == pytest.approx(contracts - cost)

    def test_aggregation_three_fills(self):
        """Three fills of different sizes all aggregate into one position correctly."""
        fills = [
            {"contracts": 50,  "price_cents": 4, "action": "buy"},
            {"contracts": 150, "price_cents": 6, "action": "buy"},
            {"contracts": 100, "price_cents": 5, "action": "buy"},
        ]
        # Expected avg: (50*4 + 150*6 + 100*5) / 300 = (200+900+500)/300 = 1600/300
        expected_avg = Decimal("1600") / Decimal("300")
        assert _weighted_avg_price(fills) == pytest.approx(expected_avg)
        assert _net_contracts(fills) == 300
