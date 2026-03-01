"""
reconcile.py
Compares actual trading performance against Becker backtest benchmarks
and generates alerts for significant drift.

Alert types (spec Section 5.2 Panel 5):
  - Benchmark Drift     : win rate or EV drifting >5% from backtest
  - Uncategorized Trade : new prefix not in benchmarks table
  - Position Age        : open longer than category median resolution time
  - Concentration       : single market > 10% of total deployed capital
  - Loss Streak         : 3+ consecutive losses in any category

Full implementation in Phase 3.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    BENCHMARK_DRIFT = "benchmark_drift"
    UNCATEGORIZED = "uncategorized_trade"
    POSITION_AGE = "position_age"
    CONCENTRATION = "concentration"
    LOSS_STREAK = "loss_streak"


@dataclass
class Alert:
    alert_type: AlertType
    title: str
    message: str
    severity: str   # "info" | "warning" | "critical"
    category: str | None = None
    market_ticker: str | None = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


def run_reconcile(db_session) -> list[Alert]:
    """
    Run all reconciliation checks and return a list of active alerts.
    Full implementation in Phase 3.
    """
    raise NotImplementedError


def _check_benchmark_drift(db_session) -> list[Alert]:
    """Flag categories where actual win rate or EV deviates >5% from benchmark."""
    raise NotImplementedError


def _check_uncategorized(db_session) -> list[Alert]:
    """Return alerts for any trades with category='uncategorized'."""
    raise NotImplementedError


def _check_position_age(db_session) -> list[Alert]:
    """Alert for positions open longer than the category's median days-to-resolution."""
    raise NotImplementedError


def _check_concentration(db_session) -> list[Alert]:
    """Alert if any single market > 10% of total deployed capital."""
    raise NotImplementedError


def _check_loss_streak(db_session) -> list[Alert]:
    """Alert if 3+ consecutive losses in any category."""
    raise NotImplementedError
