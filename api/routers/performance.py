"""
routers/performance.py
Endpoints:
  GET /performance/summary        — overall P&L, win rate, Sharpe vs benchmarks
  GET /performance/daily          — daily P&L time series for chart
  GET /performance/by-category    — per-category actual vs benchmark breakdown
Implemented in Phase 4.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db
from schemas import CategoryPerformanceSchema, DailyPerformanceSchema, PerformanceSummarySchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/summary", response_model=PerformanceSummarySchema)
def performance_summary(db: Session = Depends(get_db)):
    """Total capital deployed, unrealized + realized P&L, overall win rate."""
    raise NotImplementedError("Implemented in Phase 4")


@router.get("/daily", response_model=list[DailyPerformanceSchema])
def performance_daily(db: Session = Depends(get_db)):
    """Daily P&L time series from daily_performance table for cumulative chart."""
    raise NotImplementedError("Implemented in Phase 4")


@router.get("/by-category", response_model=list[CategoryPerformanceSchema])
def performance_by_category(db: Session = Depends(get_db)):
    """
    Per-category comparison of actual vs Becker benchmark performance.
    Includes win rate drift and EV drift, color-coded by deviation.
    """
    raise NotImplementedError("Implemented in Phase 4")
