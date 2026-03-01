"""
position_manager.py
Aggregates individual trade fills into positions,
calculates P&L on settlement, and manages position lifecycle.

P&L formulas (spec Section 3.5):
  No position cost  = (1 - price/100) * contracts
  Win payout        = contracts * 1.00
  Gross P&L on win  = contracts - cost
  Gross P&L on loss = -cost
  Net P&L           = gross_pnl - fees

  Maker fee = 0.0175 * contracts * (price/100) * (1 - price/100)
  Taker fee = 0.07   * contracts * (price/100) * (1 - price/100)

Full implementation in Phase 3.
"""
from __future__ import annotations

from decimal import Decimal


# ── Fee calculations ───────────────────────────────────────────────────────────

def calc_maker_fee(contracts: int, price_cents: int) -> Decimal:
    """Maker fee = 0.0175 * contracts * (p/100) * (1 - p/100)"""
    p = Decimal(price_cents) / 100
    return Decimal("0.0175") * contracts * p * (1 - p)


def calc_taker_fee(contracts: int, price_cents: int) -> Decimal:
    """Taker fee = 0.07 * contracts * (p/100) * (1 - p/100)"""
    p = Decimal(price_cents) / 100
    return Decimal("0.07") * contracts * p * (1 - p)


# ── Cost basis ─────────────────────────────────────────────────────────────────

def calc_no_cost(contracts: int, price_cents: int) -> Decimal:
    """Cost to buy `contracts` No contracts at `price_cents`."""
    p = Decimal(price_cents) / 100
    return (1 - p) * contracts


def calc_yes_cost(contracts: int, price_cents: int) -> Decimal:
    """Cost to buy `contracts` Yes contracts at `price_cents`."""
    p = Decimal(price_cents) / 100
    return p * contracts


# ── Gross P&L ──────────────────────────────────────────────────────────────────

def calc_gross_pnl(
    side: str,           # "yes" | "no"
    result: str,         # "yes" | "no"
    contracts: int,
    avg_price_cents: Decimal,
) -> Decimal:
    """
    Calculate gross P&L for a settled position.
    For a No position that wins (result == "no"):
        gross = contracts - cost
    For a No position that loses (result == "yes"):
        gross = -cost
    """
    won = side == result
    if side == "no":
        cost = calc_no_cost(contracts, int(avg_price_cents))
        return (Decimal(contracts) - cost) if won else -cost
    else:  # side == "yes"
        cost = calc_yes_cost(contracts, int(avg_price_cents))
        return (Decimal(contracts) - cost) if won else -cost


# ── Position aggregation ───────────────────────────────────────────────────────

def rebuild_positions(db_session) -> int:
    """
    Recompute the positions table from the trades table.
    Deletes all rows in positions and re-inserts based on open markets.
    Returns number of positions written.
    Full implementation in Phase 3.
    """
    raise NotImplementedError


def settle_position(market_ticker: str, result: str, db_session) -> dict:
    """
    Move a position from positions → position_history with full P&L.
    Returns the position_history row dict.
    Full implementation in Phase 3.
    """
    raise NotImplementedError
