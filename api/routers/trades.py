"""
routers/trades.py
Endpoints:
  GET /trades/          — fill history with optional filters
  GET /trades/summary   — aggregated stats grouped by category
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

import models
from auth import require_api_key
from database import get_db
from schemas import TradeSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[TradeSchema])
def list_trades(
    start_date: Optional[date] = Query(None, description="Filter fills on or after this date"),
    end_date:   Optional[date] = Query(None, description="Filter fills on or before this date"),
    category:   Optional[str]  = Query(None, description="Filter by benchmark category"),
    strategy:   Optional[str]  = Query(None, description="Filter by strategy name"),
    won:        Optional[bool]  = Query(None, description="Filter by whether the trade's market was won"),
    limit:      int             = Query(500, le=5000),
    offset:     int             = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Trade fill history, most recent first."""
    q = select(models.Trade).order_by(models.Trade.filled_at.desc())

    if start_date:
        q = q.where(func.date(models.Trade.filled_at) >= str(start_date))
    if end_date:
        q = q.where(func.date(models.Trade.filled_at) <= str(end_date))
    if strategy:
        q = q.where(models.Trade.strategy == strategy)

    # category filter: join through Market → Benchmark
    if category:
        q = (
            q.join(models.Market, models.Trade.market_ticker == models.Market.ticker)
             .join(models.Benchmark, models.Market.event_prefix == models.Benchmark.event_prefix)
             .where(models.Benchmark.category == category)
        )

    # won filter: join through PositionHistory
    if won is not None:
        q = (
            q.join(
                models.PositionHistory,
                models.PositionHistory.market_ticker == models.Trade.market_ticker,
                isouter=True,
            )
            .where(models.PositionHistory.won == won)
        )

    q = q.offset(offset).limit(limit)
    return db.execute(q).scalars().all()


@router.get("/summary")
def trades_summary(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Aggregated fill stats grouped by benchmark category.

    Returns a list of dicts with keys:
      category, trades, contracts, gross_cost_usd, total_fees_usd
    """
    q = (
        select(
            models.Benchmark.category,
            func.count(models.Trade.trade_id).label("trades"),
            func.sum(models.Trade.contracts).label("contracts"),
            func.sum(models.Trade.gross_cost_usd).label("gross_cost_usd"),
            func.sum(models.Trade.fee_usd).label("total_fees_usd"),
        )
        .join(models.Market,    models.Trade.market_ticker  == models.Market.ticker)
        .join(models.Benchmark, models.Market.event_prefix  == models.Benchmark.event_prefix)
        .group_by(models.Benchmark.category)
        .order_by(func.count(models.Trade.trade_id).desc())
    )

    if category:
        q = q.where(models.Benchmark.category == category)

    rows = db.execute(q).fetchall()
    return [
        {
            "category":       r.category,
            "trades":         r.trades,
            "contracts":      r.contracts,
            "gross_cost_usd": float(r.gross_cost_usd or 0),
            "total_fees_usd": float(r.total_fees_usd or 0),
        }
        for r in rows
    ]
