"""
routers/benchmarks.py
Endpoints:
  GET  /benchmarks/        — full benchmark table
  POST /benchmarks/reload  — re-import CSVs from the benchmarks/ directory
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
from auth import require_api_key
from database import get_db
from schemas import BenchmarkSchema
from sqlalchemy import select

router = APIRouter(dependencies=[Depends(require_api_key)])

# Path to benchmark CSVs — try new container layout first, then legacy, then local dev
_BENCHMARKS_DIR = Path("/app/benchmarks")
if not _BENCHMARKS_DIR.exists():
    _BENCHMARKS_DIR = Path("/benchmarks")   # legacy docker-compose volume mount
if not _BENCHMARKS_DIR.exists():
    _BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "benchmarks"


@router.get("/", response_model=list[BenchmarkSchema])
def list_benchmarks(db: Session = Depends(get_db)):
    """Return all rows from the benchmarks table, ordered by category then event_prefix."""
    rows = db.execute(
        select(models.Benchmark).order_by(
            models.Benchmark.category,
            models.Benchmark.event_prefix,
        )
    ).scalars().all()
    return rows


@router.post("/reload")
def reload_benchmarks(db: Session = Depends(get_db)):
    """
    Re-import benchmark data from CSV files in the benchmarks/ directory.
    Clears the existing benchmarks table and reloads from all seed CSVs.
    Returns the number of rows imported.
    """
    # import_benchmarks lives in scripts/ — add scripts/ to path
    scripts_dir = Path(__file__).parent.parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        from import_benchmarks import import_benchmarks
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"import_benchmarks module not available: {exc}",
        )

    if not _BENCHMARKS_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Benchmarks directory not found: {_BENCHMARKS_DIR}",
        )

    count = import_benchmarks(_BENCHMARKS_DIR, replace=True)
    return {"imported": count, "benchmarks_dir": str(_BENCHMARKS_DIR)}
