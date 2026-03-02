"""
routers/categories.py
Endpoints:
  GET /categories/   — high-level summary of all categories with trade counts
                       and actual vs expected performance
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

import models
from auth import require_api_key
from database import get_db

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    """
    All categories from the benchmarks table, each enriched with:
      - benchmark_count: number of distinct event_prefixes in this category
      - settled_trades:  actual settled positions we have
      - actual_win_rate: from position_history (null if no trades yet)
      - expected_win_rate: trade-weighted average of benchmark expected_win_rate

    Sorted by settled_trades descending so active categories appear first.
    """
    # All categories from benchmarks with aggregate expected metrics
    bmark_rows = db.execute(
        select(
            models.Benchmark.category,
            func.count(models.Benchmark.event_prefix).label("benchmark_count"),
            func.avg(models.Benchmark.expected_win_rate).label("avg_expected_wr"),
            func.avg(models.Benchmark.expected_ev_per_ctr).label("avg_expected_ev"),
        )
        .where(models.Benchmark.category.isnot(None))
        .group_by(models.Benchmark.category)
        .order_by(models.Benchmark.category)
    ).fetchall()

    # Actual performance by category (from settled positions)
    actual_rows = db.execute(
        select(
            models.Benchmark.category,
            func.count(models.PositionHistory.id).label("trades"),
            func.sum(models.PositionHistory.won).label("wins"),
            func.sum(models.PositionHistory.net_pnl_usd).label("net_pnl"),
        )
        .join(models.Market, models.PositionHistory.market_ticker == models.Market.ticker)
        .join(models.Benchmark, models.Market.event_prefix == models.Benchmark.event_prefix)
        .group_by(models.Benchmark.category)
    ).fetchall()

    actual_map = {r.category: r for r in actual_rows}

    result = []
    for b in bmark_rows:
        actual = actual_map.get(b.category)
        trades    = int(actual.trades) if actual else 0
        wins      = int(actual.wins or 0) if actual else 0
        actual_wr = (
            Decimal(str(round(wins / trades, 4))) if trades > 0 else None
        )
        net_pnl = Decimal(str(actual.net_pnl or 0)) if actual else Decimal("0")

        result.append({
            "category":           b.category,
            "benchmark_count":    b.benchmark_count,
            "avg_expected_wr":    float(b.avg_expected_wr)   if b.avg_expected_wr  else None,
            "avg_expected_ev":    float(b.avg_expected_ev)   if b.avg_expected_ev  else None,
            "settled_trades":     trades,
            "actual_win_rate":    float(actual_wr) if actual_wr is not None else None,
            "total_net_pnl_usd":  float(net_pnl),
        })

    result.sort(key=lambda r: r["settled_trades"], reverse=True)
    return result
