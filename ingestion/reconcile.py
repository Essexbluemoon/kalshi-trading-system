"""
reconcile.py
Compares actual trading performance against Becker backtest benchmarks
and generates alerts for significant drift.

Alert types (spec Section 5.2 Panel 5):
  - Benchmark Drift     : win rate deviating >5% from backtest
  - Uncategorized Trade : trades whose prefix is not in the benchmarks table
  - Position Age        : position open longer than the category median days
  - Concentration       : single market > 10% of total deployed capital
  - Loss Streak         : 3+ consecutive losses in any category
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from itertools import groupby

from sqlalchemy import select, func

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    BENCHMARK_DRIFT = "benchmark_drift"
    UNCATEGORIZED   = "uncategorized_trade"
    POSITION_AGE    = "position_age"
    CONCENTRATION   = "concentration"
    LOSS_STREAK     = "loss_streak"


@dataclass
class Alert:
    alert_type:    AlertType
    title:         str
    message:       str
    severity:      str               # "info" | "warning" | "critical"
    category:      str | None = None
    market_ticker: str | None = None
    created_at:    datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Public entry point ────────────────────────────────────────────────────────

def run_reconcile(db_session) -> list[Alert]:
    """Run all reconciliation checks and return a combined list of alerts."""
    alerts: list[Alert] = []
    for check in (
        _check_benchmark_drift,
        _check_uncategorized,
        _check_position_age,
        _check_concentration,
        _check_loss_streak,
    ):
        try:
            alerts.extend(check(db_session))
        except Exception:
            logger.exception("Reconcile check %s failed (non-fatal)", check.__name__)
    return alerts


# ── Individual checks ─────────────────────────────────────────────────────────

def _check_benchmark_drift(db_session) -> list[Alert]:
    """
    For every event_prefix with >= 5 settled positions, compare the actual
    win rate to benchmark.expected_win_rate.  Alert if relative drift > 5%.
    """
    import models

    rows = db_session.execute(
        select(
            models.Market.event_prefix,
            models.Market.category,
            func.count(models.PositionHistory.id).label("total"),
            func.sum(models.PositionHistory.won).label("wins"),
        )
        .join(models.Market, models.PositionHistory.market_ticker == models.Market.ticker)
        .where(models.Market.event_prefix.isnot(None))
        .group_by(models.Market.event_prefix, models.Market.category)
        .having(func.count(models.PositionHistory.id) >= 5)
    ).fetchall()

    alerts: list[Alert] = []
    for event_prefix, category, total, wins_raw in rows:
        wins = int(wins_raw or 0)
        actual_wr = wins / total if total > 0 else 0.0

        bmark = db_session.get(models.Benchmark, event_prefix)
        if bmark is None or bmark.expected_win_rate is None:
            continue

        expected = float(bmark.expected_win_rate)
        if expected == 0:
            continue
        drift = abs(actual_wr - expected) / expected

        if drift > 0.05:
            severity = "critical" if drift > 0.20 else "warning"
            alerts.append(Alert(
                alert_type=AlertType.BENCHMARK_DRIFT,
                title=f"Win rate drift: {event_prefix}",
                message=(
                    f"Actual {actual_wr:.1%} vs expected {expected:.1%} "
                    f"({drift:.1%} drift, n={total})"
                ),
                severity=severity,
                category=category,
            ))

    return alerts


def _check_uncategorized(db_session) -> list[Alert]:
    """Alert if any trades belong to a market with no benchmark entry."""
    import models

    tickers = db_session.execute(
        select(models.Market.ticker, models.Market.event_prefix)
        .join(models.Trade, models.Trade.market_ticker == models.Market.ticker)
        .outerjoin(
            models.Benchmark,
            models.Market.event_prefix == models.Benchmark.event_prefix,
        )
        .where(models.Benchmark.event_prefix.is_(None))
        .distinct()
    ).fetchall()

    if not tickers:
        return []

    sample = [t[0] for t in tickers[:5]]
    return [Alert(
        alert_type=AlertType.UNCATEGORIZED,
        title=f"{len(tickers)} uncategorized market(s)",
        message=(
            f"No benchmark entry for: {', '.join(sample)}"
            + ("..." if len(tickers) > 5 else "")
        ),
        severity="info",
    )]


def _check_position_age(db_session) -> list[Alert]:
    """
    Alert for any open position held longer than the benchmark's median
    days-to-resolution.
    """
    import models

    rows = db_session.execute(
        select(
            models.Position,
            models.Market.event_prefix,
            models.Market.category,
        )
        .join(models.Market, models.Position.market_ticker == models.Market.ticker)
    ).fetchall()

    now = datetime.now(timezone.utc)
    alerts: list[Alert] = []

    for pos, event_prefix, category in rows:
        if not pos.opened_at or not event_prefix:
            continue

        bmark = db_session.get(models.Benchmark, event_prefix)
        if bmark is None:
            continue

        median_days = _extract_median_days(bmark.notes)
        if median_days is None:
            continue

        opened = pos.opened_at
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        days_open = (now - opened).total_seconds() / 86400

        if days_open > median_days:
            alerts.append(Alert(
                alert_type=AlertType.POSITION_AGE,
                title=f"Position age: {pos.market_ticker}",
                message=(
                    f"Open {days_open:.1f} days "
                    f"(median {median_days:.1f} days for {event_prefix})"
                ),
                severity="warning",
                category=category,
                market_ticker=pos.market_ticker,
            ))

    return alerts


def _check_concentration(db_session) -> list[Alert]:
    """Alert if any single market's deployed cost exceeds 10% of total."""
    import models

    total_raw = db_session.execute(
        select(func.sum(models.Position.total_cost_usd))
    ).scalar()

    if not total_raw or float(total_raw) <= 0:
        return []

    total_deployed = float(total_raw)
    positions = db_session.execute(select(models.Position)).scalars().all()

    alerts: list[Alert] = []
    for pos in positions:
        pct = float(pos.total_cost_usd or 0) / total_deployed
        if pct > 0.10:
            alerts.append(Alert(
                alert_type=AlertType.CONCENTRATION,
                title=f"Concentration: {pos.market_ticker}",
                message=(
                    f"{pos.market_ticker} is {pct:.1%} of deployed capital "
                    f"(${float(pos.total_cost_usd):.2f} of ${total_deployed:.2f})"
                ),
                severity="warning" if pct < 0.25 else "critical",
                market_ticker=pos.market_ticker,
            ))

    return alerts


def _check_loss_streak(db_session) -> list[Alert]:
    """Alert if 3+ consecutive losses in any event_prefix category."""
    import models

    rows = db_session.execute(
        select(
            models.Market.event_prefix,
            models.Market.category,
            models.PositionHistory.won,
            models.PositionHistory.settled_at,
        )
        .join(models.Market, models.PositionHistory.market_ticker == models.Market.ticker)
        .where(models.Market.event_prefix.isnot(None))
        .order_by(models.Market.event_prefix, models.PositionHistory.settled_at.desc())
    ).fetchall()

    alerts: list[Alert] = []
    for prefix, group in groupby(rows, key=lambda r: r[0]):
        history = list(group)
        if len(history) < 3:
            continue
        recent = history[:3]
        if all(not r[2] for r in recent):   # r[2] is won
            category = recent[0][1]
            alerts.append(Alert(
                alert_type=AlertType.LOSS_STREAK,
                title=f"Loss streak: {prefix}",
                message=f"3+ consecutive losses in {prefix} (category: {category})",
                severity="warning",
                category=category,
            ))

    return alerts


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_median_days(notes: str | None) -> float | None:
    """Parse 'median_days=X.X' from a benchmark notes string."""
    if not notes:
        return None
    m = re.search(r"median_days=([\d.]+)", notes)
    return float(m.group(1)) if m else None
