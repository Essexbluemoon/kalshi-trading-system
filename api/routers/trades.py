"""
routers/trades.py
Endpoints:
  GET /trades              — trade history, filterable by date/category/strategy
  GET /trades/summary      — aggregated stats by category
Implemented in Phase 4.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db
from schemas import TradeSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[TradeSchema])
def list_trades(
    start_date: Optional[date] = Query(None),
    end_date:   Optional[date] = Query(None),
    category:   Optional[str]  = Query(None),
    strategy:   Optional[str]  = Query(None),
    won:        Optional[bool]  = Query(None),
    limit:      int             = Query(500, le=5000),
    offset:     int             = Query(0),
    db: Session = Depends(get_db),
):
    """Trade history with optional filters. Sorted by filled_at desc."""
    raise NotImplementedError("Implemented in Phase 4")


@router.get("/summary")
def trades_summary(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Aggregated trade stats grouped by category."""
    raise NotImplementedError("Implemented in Phase 4")
