"""
routers/categories.py
Endpoints:
  GET /categories     — all categories with trade counts and EV vs benchmark
Implemented in Phase 4.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/")
def list_categories(db: Session = Depends(get_db)):
    """All categories with trade counts and current EV vs Becker benchmark."""
    raise NotImplementedError("Implemented in Phase 4")
