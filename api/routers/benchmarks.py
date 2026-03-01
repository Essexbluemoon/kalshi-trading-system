"""
routers/benchmarks.py
Endpoints:
  GET  /benchmarks          — full benchmark table
  POST /benchmarks/reload   — re-import CSV from benchmarks/ directory
Implemented in Phase 4.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db
from schemas import BenchmarkSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[BenchmarkSchema])
def list_benchmarks(db: Session = Depends(get_db)):
    """Return all rows from the benchmarks table."""
    raise NotImplementedError("Implemented in Phase 4")


@router.post("/reload")
def reload_benchmarks(db: Session = Depends(get_db)):
    """Re-import benchmark data from CSV files in the benchmarks/ directory."""
    raise NotImplementedError("Implemented in Phase 4")
