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
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


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

def rebuild_positions(db_session, kalshi_client=None) -> int:
    """
    Recompute the positions table from the trades table.

    Algorithm:
      1. Delete all existing positions.
      2. Find all markets that have buy trades but no position_history entry
         (i.e., not yet settled).
      3. For each such market, aggregate trades into a Position row.

    Returns the number of positions written.
    """
    import models
    from sqlalchemy import select

    # Clear existing positions
    db_session.query(models.Position).delete(synchronize_session=False)

    # Tickers already settled (have a position_history row)
    settled_tickers: set[str] = {
        row[0]
        for row in db_session.execute(
            select(models.PositionHistory.market_ticker)
        )
    }

    # All tickers that have at least one trade
    all_traded: set[str] = {
        row[0]
        for row in db_session.execute(
            select(models.Trade.market_ticker.distinct())
        )
    }

    open_tickers = all_traded - settled_tickers
    written = 0

    for ticker in open_tickers:
        trades = db_session.execute(
            select(models.Trade).where(models.Trade.market_ticker == ticker)
        ).scalars().all()

        buy_trades  = [t for t in trades if t.action == "buy"]
        sell_trades = [t for t in trades if t.action == "sell"]

        if not buy_trades:
            continue

        total_buy_qty  = sum(t.contracts for t in buy_trades)
        total_sell_qty = sum(t.contracts for t in sell_trades)
        net_contracts  = total_buy_qty - total_sell_qty

        if net_contracts <= 0:
            continue  # position fully closed

        # Weighted average buy price
        avg_price = (
            sum(Decimal(str(t.price_cents)) * t.contracts for t in buy_trades)
            / total_buy_qty
        )

        side = buy_trades[0].side  # "yes" | "no"
        if side == "no":
            total_cost = calc_no_cost(net_contracts, int(avg_price))
        else:
            total_cost = calc_yes_cost(net_contracts, int(avg_price))

        total_fees = sum(Decimal(str(t.fee_usd or 0)) for t in trades)
        # Normalise to UTC-aware before min() — SQLite reads datetimes back as naive
        def _to_utc(dt):
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        opened_at  = min((_to_utc(t.filled_at) for t in buy_trades if t.filled_at), default=None)

        # Fetch live price for unrealized P&L
        current_price_cents = None
        unrealized_pnl_usd = None
        if kalshi_client is not None:
            try:
                ob = kalshi_client.get_orderbook(ticker)
                yes_bid = ob.get("yes_bid")
                if yes_bid is not None:
                    if side == "yes":
                        current_price_cents = Decimal(yes_bid)
                        unrealized_pnl_usd = (current_price_cents - avg_price) * net_contracts / 100
                    else:  # no
                        current_price_cents = Decimal(100 - yes_bid)
                        unrealized_pnl_usd = (current_price_cents - (100 - avg_price)) * net_contracts / 100
            except Exception:
                logger.exception("Failed to fetch orderbook for %s", ticker)

        pos = models.Position(
            market_ticker=ticker,
            side=side,
            net_contracts=net_contracts,
            avg_price_cents=round(avg_price, 4),
            total_cost_usd=total_cost,
            total_fees_usd=total_fees,
            current_price_cents=round(current_price_cents, 4) if current_price_cents is not None else None,
            unrealized_pnl_usd=round(unrealized_pnl_usd, 4) if unrealized_pnl_usd is not None else None,
            opened_at=opened_at,
        )
        db_session.add(pos)
        written += 1

    db_session.flush()
    logger.info("rebuild_positions: wrote %d open positions", written)
    return written


def settle_position(market_ticker: str, result: str, db_session) -> dict:
    """
    Move an open position to position_history with full P&L calculation.

    Steps:
      1. Load the Position row.
      2. Sum all trade fees for this market.
      3. Compute gross_pnl via calc_gross_pnl.
      4. net_pnl = gross_pnl - total_fees.
      5. Insert PositionHistory row; delete Position row.

    Returns a summary dict with settlement details.
    Raises ValueError if no open position exists for the ticker.
    """
    import models
    from sqlalchemy import select

    pos = db_session.get(models.Position, market_ticker)
    if pos is None:
        raise ValueError(f"No open position found for market {market_ticker!r}")

    # Sum fees across all trade fills
    trades = db_session.execute(
        select(models.Trade).where(models.Trade.market_ticker == market_ticker)
    ).scalars().all()
    total_fees = sum(Decimal(str(t.fee_usd or 0)) for t in trades)

    # P&L
    gross_pnl = calc_gross_pnl(
        pos.side,
        result,
        pos.net_contracts,
        Decimal(str(pos.avg_price_cents)),
    )
    net_pnl = gross_pnl - total_fees

    now = datetime.now(timezone.utc)
    days_held = Decimal("0")
    if pos.opened_at:
        opened = pos.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        days_held = Decimal(str(round((now - opened).total_seconds() / 86400, 2)))

    ph = models.PositionHistory(
        market_ticker=market_ticker,
        side=pos.side,
        net_contracts=pos.net_contracts,
        avg_price_cents=pos.avg_price_cents,
        total_cost_usd=pos.total_cost_usd,
        total_fees_usd=total_fees,
        result=result,
        won=(pos.side == result),
        gross_pnl_usd=round(gross_pnl, 4),
        net_pnl_usd=round(net_pnl, 4),
        settled_at=now,
        days_held=days_held,
    )
    db_session.add(ph)
    db_session.delete(pos)
    db_session.flush()

    logger.info(
        "Settled %s: side=%s result=%s net_pnl=%.4f",
        market_ticker, pos.side, result, float(net_pnl),
    )
    return {
        "market_ticker": market_ticker,
        "side": pos.side,
        "result": result,
        "won": pos.side == result,
        "gross_pnl_usd": float(gross_pnl),
        "net_pnl_usd": float(net_pnl),
    }
