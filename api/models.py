"""
models.py
SQLAlchemy ORM models matching the database schema in spec Section 2.
Indexes required by spec:
  - trades.filled_at
  - trades.market_ticker  (also the FK, but explicit index for query perf)
  - position_history.settled_at
  - daily_performance.date  (already the PK — index is implicit)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Index, Integer,
    String, Text, ForeignKey, DECIMAL,
)
from sqlalchemy.orm import relationship

from database import Base


def _now():
    return datetime.now(timezone.utc)


# ── markets ────────────────────────────────────────────────────────────────────

class Market(Base):
    __tablename__ = "markets"

    ticker        = Column(String(100), primary_key=True)
    title         = Column(Text)
    category      = Column(String(50))
    subcategory   = Column(String(100))
    event_prefix  = Column(String(50))
    status        = Column(String(20))           # open | closed | resolved
    result        = Column(String(10))           # yes | no | NULL
    close_time    = Column(DateTime(timezone=True))
    resolved_at   = Column(DateTime(timezone=True))
    created_at    = Column(DateTime(timezone=True))

    trades         = relationship("Trade",           back_populates="market")
    position       = relationship("Position",        back_populates="market", uselist=False)
    position_hist  = relationship("PositionHistory", back_populates="market")


# ── trades ─────────────────────────────────────────────────────────────────────

class Trade(Base):
    __tablename__ = "trades"

    trade_id       = Column(String(100), primary_key=True)
    market_ticker  = Column(String(100), ForeignKey("markets.ticker"), nullable=False)
    side           = Column(String(10))           # yes | no
    action         = Column(String(10))           # buy | sell
    price_cents    = Column(Integer)
    contracts      = Column(Integer)
    fee_usd        = Column(DECIMAL(10, 4))
    gross_cost_usd = Column(DECIMAL(10, 4))
    strategy       = Column(String(20))
    is_maker       = Column(Boolean)
    setup_grade    = Column(String(5))            # A/B/C/D
    edge_type      = Column(String(50))
    notes          = Column(Text)
    filled_at      = Column(DateTime(timezone=True))
    ingested_at    = Column(DateTime(timezone=True), default=_now)

    market = relationship("Market", back_populates="trades")

    __table_args__ = (
        Index("ix_trades_filled_at",    "filled_at"),
        Index("ix_trades_market_ticker", "market_ticker"),
    )


# ── positions ──────────────────────────────────────────────────────────────────

class Position(Base):
    __tablename__ = "positions"

    market_ticker       = Column(String(100), ForeignKey("markets.ticker"), primary_key=True)
    side                = Column(String(10))
    net_contracts       = Column(Integer)
    avg_price_cents     = Column(DECIMAL(10, 4))
    total_cost_usd      = Column(DECIMAL(10, 4))
    total_fees_usd      = Column(DECIMAL(10, 4))
    current_price_cents = Column(Integer)
    unrealized_pnl_usd  = Column(DECIMAL(10, 4))
    opened_at           = Column(DateTime(timezone=True))
    updated_at          = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    market = relationship("Market", back_populates="position")


# ── position_history ───────────────────────────────────────────────────────────

class PositionHistory(Base):
    __tablename__ = "position_history"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    market_ticker   = Column(String(100), ForeignKey("markets.ticker"), nullable=False)
    side            = Column(String(10))
    net_contracts   = Column(Integer)
    avg_price_cents = Column(DECIMAL(10, 4))
    total_cost_usd  = Column(DECIMAL(10, 4))
    total_fees_usd  = Column(DECIMAL(10, 4))
    result          = Column(String(10))          # yes | no
    won             = Column(Boolean)
    gross_pnl_usd   = Column(DECIMAL(10, 4))
    net_pnl_usd     = Column(DECIMAL(10, 4))
    settled_at      = Column(DateTime(timezone=True))
    days_held       = Column(DECIMAL(6, 2))

    market = relationship("Market", back_populates="position_hist")

    __table_args__ = (
        Index("ix_position_history_settled_at", "settled_at"),
    )


# ── benchmarks ─────────────────────────────────────────────────────────────────

class Benchmark(Base):
    __tablename__ = "benchmarks"

    event_prefix       = Column(String(50), primary_key=True)
    category           = Column(String(50))
    subcategory        = Column(String(100))
    expected_win_rate  = Column(DECIMAL(6, 4))
    expected_ev_per_ctr = Column(DECIMAL(10, 4))
    expected_sharpe    = Column(DECIMAL(8, 4))
    sample_trades      = Column(Integer)
    price_bucket       = Column(String(20))       # 1-2c, 3-4c, 5-6c, 7-8c
    timing_filter      = Column(String(50))
    notes              = Column(Text)


# ── daily_performance ──────────────────────────────────────────────────────────

class DailyPerformance(Base):
    __tablename__ = "daily_performance"

    date                   = Column(Date, primary_key=True)
    trades_settled         = Column(Integer, default=0)
    wins                   = Column(Integer, default=0)
    losses                 = Column(Integer, default=0)
    win_rate               = Column(DECIMAL(6, 4))
    gross_pnl_usd          = Column(DECIMAL(10, 4))
    net_pnl_usd            = Column(DECIMAL(10, 4))
    fees_usd               = Column(DECIMAL(10, 4))
    capital_deployed_usd   = Column(DECIMAL(10, 4))
    cumulative_net_pnl_usd = Column(DECIMAL(10, 4))
