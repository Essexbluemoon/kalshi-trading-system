"""
routers/positions.py
Endpoints:
  GET /positions              — all open positions with unrealized P&L
  GET /positions/{ticker}     — single position detail with full trade history
Implemented in Phase 4.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db
from schemas import PositionSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[PositionSchema])
def list_positions(db: Session = Depends(get_db)):
    """All open positions with enriched fields (title, category, expected EV, days open)."""
    raise NotImplementedError("Implemented in Phase 4")


@router.get("/{ticker}", response_model=PositionSchema)
def get_position(ticker: str, db: Session = Depends(get_db)):
    """Single position detail including full trade history for that market."""
    raise NotImplementedError("Implemented in Phase 4")
