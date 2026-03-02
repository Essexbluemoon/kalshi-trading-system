"""
routers/alerts.py
Endpoints:
  GET /alerts/   — run all reconcile checks and return active alerts
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_api_key
from database import get_db
from schemas import AlertSchema

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/", response_model=list[AlertSchema])
def list_alerts(db: Session = Depends(get_db)):
    """
    Run all reconcile checks in real time and return active alerts:
      - Benchmark drift (win rate >5% off expected)
      - Uncategorized trades (no benchmark entry)
      - Position age (held longer than category median)
      - Concentration (>10% of capital in one market)
      - Loss streaks (3+ consecutive losses per prefix)
    """
    from reconcile import run_reconcile

    alerts = run_reconcile(db)
    return [
        AlertSchema(
            alert_type=a.alert_type.value,
            title=a.title,
            message=a.message,
            severity=a.severity,
            category=a.category,
            market_ticker=a.market_ticker,
            created_at=a.created_at,
        )
        for a in alerts
    ]
