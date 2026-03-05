"""
routers/performance.py
Endpoints:
  GET /performance/summary        — overall P&L, win rate, capital deployed
  GET /performance/daily          — daily P&L time series
  GET /performance/by-category    — actual vs benchmark comparison per event_prefix
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, cast, select, func
from sqlalchemy.orm import Session

import models
from auth import require_api_key
from database import get_db
from schemas import (
    CategoryPerformanceSchema,
    DailyPerformanceSchema,
    PerformanceSummarySchema,
)

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/summary", response_model=PerformanceSummarySchema)
def performance_summary(db: Session = Depends(get_db)):
    """Total capital deployed, unrealized + realized P&L, overall win rate."""

    # Open positions
    deployed = db.execute(
        select(func.sum(models.Position.total_cost_usd))
    ).scalar() or Decimal("0")

    unrealized = db.execute(
        select(func.sum(models.Position.unrealized_pnl_usd))
    ).scalar() or Decimal("0")

    # Settled
    realized = db.execute(
        select(func.sum(models.PositionHistory.net_pnl_usd))
    ).scalar() or Decimal("0")

    total_settled = db.execute(
        select(func.count(models.PositionHistory.id))
    ).scalar() or 0

    total_wins = db.execute(
        select(func.sum(cast(models.PositionHistory.won, Integer)))
    ).scalar() or 0

    win_rate = (
        Decimal(str(int(total_wins))) / Decimal(str(total_settled))
        if total_settled > 0
        else Decimal("0")
    )

    return PerformanceSummarySchema(
        total_capital_deployed_usd=Decimal(str(deployed)),
        unrealized_pnl_usd=Decimal(str(unrealized)),
        realized_pnl_usd=Decimal(str(realized)),
        win_rate=win_rate,
        total_settled=total_settled,
        total_wins=int(total_wins),
        total_losses=total_settled - int(total_wins),
    )


@router.get("/daily", response_model=list[DailyPerformanceSchema])
def performance_daily(db: Session = Depends(get_db)):
    """Daily P&L time series from daily_performance table, oldest first."""
    rows = db.execute(
        select(models.DailyPerformance).order_by(models.DailyPerformance.date.asc())
    ).scalars().all()
    return rows


@router.get("/by-category", response_model=list[CategoryPerformanceSchema])
def performance_by_category(db: Session = Depends(get_db)):
    """
    Per-event-prefix comparison of actual vs Becker benchmark performance.
    Only includes prefixes with at least one settled position.
    Sorted by total net P&L descending.
    """
    rows = db.execute(
        select(
            models.Market.event_prefix,
            models.Benchmark.category,
            models.Benchmark.subcategory,
            func.count(models.PositionHistory.id).label("trades"),
            func.sum(cast(models.PositionHistory.won, Integer)).label("wins"),
            func.sum(models.PositionHistory.net_pnl_usd).label("total_net_pnl"),
            func.sum(models.PositionHistory.net_contracts).label("total_contracts"),
            models.Benchmark.expected_win_rate,
            models.Benchmark.expected_ev_per_ctr,
        )
        .join(models.Market, models.PositionHistory.market_ticker == models.Market.ticker)
        .outerjoin(
            models.Benchmark,
            models.Market.event_prefix == models.Benchmark.event_prefix,
        )
        .where(models.Market.event_prefix.isnot(None))
        .group_by(
            models.Market.event_prefix,
            models.Benchmark.category,
            models.Benchmark.subcategory,
            models.Benchmark.expected_win_rate,
            models.Benchmark.expected_ev_per_ctr,
        )
        .order_by(func.sum(models.PositionHistory.net_pnl_usd).desc())
    ).fetchall()

    result = []
    for row in rows:
        trades          = int(row.trades or 0)
        wins            = int(row.wins or 0)
        total_net_pnl   = Decimal(str(row.total_net_pnl or 0))
        total_contracts = int(row.total_contracts or 1)

        actual_wr       = Decimal(str(wins / trades)) if trades > 0 else Decimal("0")
        actual_ev       = total_net_pnl / total_contracts if total_contracts > 0 else Decimal("0")

        expected_wr  = Decimal(str(row.expected_win_rate))   if row.expected_win_rate  else None
        expected_ev  = Decimal(str(row.expected_ev_per_ctr)) if row.expected_ev_per_ctr else None

        wr_drift = (
            abs(actual_wr - expected_wr) / expected_wr
            if expected_wr and expected_wr != 0
            else None
        )
        ev_drift = (
            abs(actual_ev - expected_ev) / abs(expected_ev)
            if expected_ev and expected_ev != 0
            else None
        )

        result.append(CategoryPerformanceSchema(
            category=row.category or "Uncategorized",
            subcategory=row.subcategory,
            trades=trades,
            actual_win_rate=actual_wr,
            expected_win_rate=expected_wr,
            win_rate_drift=wr_drift,
            actual_ev_per_ctr=actual_ev,
            expected_ev_per_ctr=expected_ev,
            ev_drift=ev_drift,
            total_net_pnl_usd=total_net_pnl,
        ))

    return result
