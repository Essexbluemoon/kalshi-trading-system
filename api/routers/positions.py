"""
routers/positions.py
Endpoints:
  GET /positions/           — all open positions enriched with market + benchmark data
  GET /positions/{ticker}   — single position with full fill history
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from auth import require_api_key
from database import get_db
from schemas import PositionSchema, TradeSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


def _enrich_position(pos: models.Position, db: Session) -> PositionSchema:
    """Build a PositionSchema from an ORM position, joining market + benchmark."""
    mkt    = db.get(models.Market, pos.market_ticker)
    prefix = mkt.event_prefix if mkt else None
    bmark  = db.get(models.Benchmark, prefix) if prefix else None

    days_open: float | None = None
    if pos.opened_at:
        opened = pos.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        days_open = round((datetime.now(timezone.utc) - opened).total_seconds() / 86400, 2)

    return PositionSchema(
        market_ticker=pos.market_ticker,
        side=pos.side,
        net_contracts=pos.net_contracts,
        avg_price_cents=pos.avg_price_cents,
        total_cost_usd=pos.total_cost_usd,
        total_fees_usd=pos.total_fees_usd,
        current_price_cents=pos.current_price_cents,
        unrealized_pnl_usd=pos.unrealized_pnl_usd,
        opened_at=pos.opened_at,
        updated_at=pos.updated_at,
        title=mkt.title if mkt else None,
        category=bmark.category if bmark else (mkt.category if mkt else None),
        subcategory=bmark.subcategory if bmark else (mkt.subcategory if mkt else None),
        expected_ev_per_ctr=bmark.expected_ev_per_ctr if bmark else None,
        days_open=days_open,
    )


@router.get("/", response_model=list[PositionSchema])
def list_positions(db: Session = Depends(get_db)):
    """All open positions sorted by days_open descending (oldest first)."""
    positions = db.execute(select(models.Position)).scalars().all()
    enriched  = [_enrich_position(p, db) for p in positions]
    enriched.sort(key=lambda p: p.days_open or 0, reverse=True)
    return enriched


@router.get("/{ticker}", response_model=PositionSchema)
def get_position(ticker: str, db: Session = Depends(get_db)):
    """Single open position by market ticker. 404 if not found or already settled."""
    pos = db.get(models.Position, ticker.upper())
    if pos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No open position for ticker {ticker!r}",
        )
    return _enrich_position(pos, db)
