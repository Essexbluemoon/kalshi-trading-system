"""
tests/test_pipeline.py
Unit-level integration tests for the ingestion pipeline (run_ingestion_cycle).

Uses a FakeKalshiClient with pre-canned fills — no live credentials needed.
Each test uses the `db_session` fixture (rollback isolation). Because
run_ingestion_cycle calls session.commit() at step 8, we replace commit with
flush so the rollback fixture cleans up all data after each test while still
letting assertions query flushed rows within the transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

import models


# ── Fake Kalshi client ─────────────────────────────────────────────────────────

_TICKER = "MLBNYY-24SEP30-T42.5"

_FILLS_2 = [
    {
        "trade_id": "PIPE-001",
        "ticker": _TICKER,
        "side":   "no",
        "action": "buy",
        "yes_price": 5,
        "count":  100,
        "is_taker": False,
        "fee_cost": "0.24",
        "created_time": "2024-09-15T12:00:00Z",
    },
    {
        "trade_id": "PIPE-002",
        "ticker": _TICKER,
        "side":   "no",
        "action": "buy",
        "yes_price": 5,
        "count":  50,
        "is_taker": False,
        "fee_cost": "0.12",
        "created_time": "2024-09-16T10:00:00Z",
    },
]

_MARKET_DATA = [
    {
        "ticker": _TICKER,
        "title":  "Yankees total runs > 42.5 on Sep 30",
        "event_ticker": "MLBNYY",
        "status": "open",
    }
]

_SETTLEMENT_NO = {
    "ticker": _TICKER,
    "market_result": "no",
    "settled_time": "2024-09-30T22:00:00Z",
}


class FakeKalshiClient:
    """Deterministic Kalshi mock for pipeline tests."""

    def __init__(self, fills=None, settlements=None, markets=None):
        self._fills       = _FILLS_2 if fills       is None else fills
        self._settlements = []       if settlements  is None else settlements
        self._markets     = _MARKET_DATA if markets is None else markets

    def get_fills(self, since=None):
        return self._fills

    def get_markets_batch(self, tickers):
        by_ticker = {m["ticker"]: m for m in self._markets}
        return [by_ticker.get(t) or {"ticker": t, "status": "open"} for t in tickers]

    def get_settlements(self, since=None):
        return self._settlements


# ── Helper ─────────────────────────────────────────────────────────────────────

def _safe_session(db_session):
    """Replace commit with flush so the rollback fixture still cleans up."""
    db_session.commit = db_session.flush
    return db_session


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestIngestionPipeline:

    def test_empty_fills_returns_early(self, db_session):
        """No fills → cycle returns zero stats without touching the DB."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        stats = run_ingestion_cycle(db, FakeKalshiClient(fills=[], settlements=[]))

        assert stats["fills_fetched"]   == 0
        assert stats["trades_inserted"] == 0
        assert stats["markets_upserted"] == 0
        assert stats["positions_rebuilt"] == 0

    def test_basic_cycle_stats(self, db_session):
        """Two fills → 2 trades inserted, 1 market upserted, 1 position rebuilt."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        stats = run_ingestion_cycle(db, FakeKalshiClient())

        assert stats["fills_fetched"]    == 2
        assert stats["trades_inserted"]  == 2
        assert stats["markets_upserted"] == 1
        assert stats["positions_rebuilt"] == 1
        assert stats["positions_settled"] == 0

    def test_trades_written_to_db(self, db_session):
        """Trade rows are present in the session after the cycle."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        run_ingestion_cycle(db, FakeKalshiClient())

        trade_ids = {row[0] for row in db.execute(select(models.Trade.trade_id))}
        assert "PIPE-001" in trade_ids
        assert "PIPE-002" in trade_ids

    def test_position_aggregated_correctly(self, db_session):
        """Position table reflects the aggregated No position (100 + 50 = 150 contracts)."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        run_ingestion_cycle(db, FakeKalshiClient())

        pos = db.get(models.Position, _TICKER)
        assert pos is not None
        assert pos.side == "no"
        assert pos.net_contracts == 150

    def test_idempotent_second_cycle(self, db_session):
        """Running the cycle twice with the same fills inserts 0 new trades."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        client = FakeKalshiClient()
        run_ingestion_cycle(db, client)
        stats2 = run_ingestion_cycle(db, client)

        assert stats2["trades_inserted"] == 0

    def test_settlement_moves_position_to_history(self, db_session):
        """
        When the fake client returns a settlement for an open position,
        the position is moved to position_history and removed from positions.
        """
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        stats = run_ingestion_cycle(
            db, FakeKalshiClient(settlements=[_SETTLEMENT_NO])
        )

        assert stats["positions_settled"] == 1
        # Position should be gone
        assert db.get(models.Position, _TICKER) is None
        # PositionHistory should exist
        hist = db.execute(
            select(models.PositionHistory).where(
                models.PositionHistory.market_ticker == _TICKER
            )
        ).scalars().first()
        assert hist is not None
        assert hist.won is True          # side=no, result=no → won

    def test_settlement_pnl_positive_for_no_win(self, db_session):
        """No side wins when result=no; net P&L must be positive."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        run_ingestion_cycle(db, FakeKalshiClient(settlements=[_SETTLEMENT_NO]))

        hist = db.execute(
            select(models.PositionHistory).where(
                models.PositionHistory.market_ticker == _TICKER
            )
        ).scalars().first()
        assert hist is not None
        assert Decimal(str(hist.net_pnl_usd)) > 0

    def test_daily_performance_created_after_settlement(self, db_session):
        """At least one DailyPerformance row is created after a settlement cycle."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        run_ingestion_cycle(db, FakeKalshiClient(settlements=[_SETTLEMENT_NO]))

        rows = db.execute(select(models.DailyPerformance)).scalars().all()
        assert len(rows) >= 1

    def test_market_upserted_with_event_prefix(self, db_session):
        """The upserted Market row has the event_prefix parsed from the event_ticker."""
        db = _safe_session(db_session)
        from ingest_trades import run_ingestion_cycle

        run_ingestion_cycle(db, FakeKalshiClient())

        mkt = db.get(models.Market, _TICKER)
        assert mkt is not None
        assert mkt.event_prefix == "MLBNYY"
