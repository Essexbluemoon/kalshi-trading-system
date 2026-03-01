"""
schemas.py
Pydantic models for API request/response serialization.
Implemented in Phase 4.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Markets ────────────────────────────────────────────────────────────────────

class MarketSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    title: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    event_prefix: Optional[str]
    status: Optional[str]
    result: Optional[str]
    close_time: Optional[datetime]


# ── Trades ─────────────────────────────────────────────────────────────────────

class TradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trade_id: str
    market_ticker: str
    side: str
    action: str
    price_cents: int
    contracts: int
    fee_usd: Decimal
    gross_cost_usd: Decimal
    strategy: Optional[str]
    is_maker: Optional[bool]
    setup_grade: Optional[str]
    edge_type: Optional[str]
    notes: Optional[str]
    filled_at: datetime
    ingested_at: datetime


# ── Positions ──────────────────────────────────────────────────────────────────

class PositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_ticker: str
    side: str
    net_contracts: int
    avg_price_cents: Decimal
    total_cost_usd: Decimal
    total_fees_usd: Decimal
    current_price_cents: Optional[int]
    unrealized_pnl_usd: Optional[Decimal]
    opened_at: Optional[datetime]
    updated_at: Optional[datetime]
    # Enriched fields (joined from markets + benchmarks)
    title: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    expected_ev_per_ctr: Optional[Decimal] = None
    days_open: Optional[float] = None


# ── Performance ────────────────────────────────────────────────────────────────

class PerformanceSummarySchema(BaseModel):
    total_capital_deployed_usd: Decimal
    unrealized_pnl_usd: Decimal
    realized_pnl_usd: Decimal
    win_rate: Decimal
    total_settled: int
    total_wins: int
    total_losses: int

class DailyPerformanceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    trades_settled: int
    wins: int
    losses: int
    win_rate: Optional[Decimal]
    net_pnl_usd: Optional[Decimal]
    cumulative_net_pnl_usd: Optional[Decimal]


class CategoryPerformanceSchema(BaseModel):
    category: str
    subcategory: Optional[str]
    trades: int
    actual_win_rate: Decimal
    expected_win_rate: Optional[Decimal]
    win_rate_drift: Optional[Decimal]
    actual_ev_per_ctr: Decimal
    expected_ev_per_ctr: Optional[Decimal]
    ev_drift: Optional[Decimal]
    total_net_pnl_usd: Decimal


# ── Benchmarks ─────────────────────────────────────────────────────────────────

class BenchmarkSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_prefix: str
    category: Optional[str]
    subcategory: Optional[str]
    expected_win_rate: Optional[Decimal]
    expected_ev_per_ctr: Optional[Decimal]
    expected_sharpe: Optional[Decimal]
    sample_trades: Optional[int]
    price_bucket: Optional[str]
    timing_filter: Optional[str]
    notes: Optional[str]


# ── Alerts ─────────────────────────────────────────────────────────────────────

class AlertSchema(BaseModel):
    alert_type: str
    title: str
    message: str
    severity: str        # info | warning | critical
    category: Optional[str] = None
    market_ticker: Optional[str] = None
    created_at: datetime
