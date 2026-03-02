"""
tests/test_api.py
Integration tests for all FastAPI endpoints.

Uses FastAPI's TestClient backed by the SQLite test DB (DATABASE_URL already
set in conftest.py). A module-scoped `seeded_data` fixture commits a minimal
dataset so the TestClient's sessions can see it; it cleans up on teardown.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# conftest.py sets DATABASE_URL=sqlite:///tests/test.db before these imports.
from database import SessionLocal
import models

# ── Constants ──────────────────────────────────────────────────────────────────

_API_KEY    = "test-api-key-phase6"
_AUTH       = {"Authorization": f"Bearer {_API_KEY}"}
_TICKER     = "TESTPHASE6-24SEP30"          # synthetic — won't collide with real benchmarks
_OPEN_TICK  = "TESTPHASE6OPEN-24OCT01"
_PREFIX     = "TESTPHASE6"
_SETTLED_AT = datetime(2024, 9, 30, 22, 0, 0, tzinfo=timezone.utc)
_SETTLED_DT = _SETTLED_AT.date()
_FILLED_AT  = datetime(2024, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


# ── Module-level fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def _set_api_key():
    """Set API_KEY env var for the duration of this module."""
    prev = os.environ.get("API_KEY")
    os.environ["API_KEY"] = _API_KEY
    yield
    if prev is None:
        os.environ.pop("API_KEY", None)
    else:
        os.environ["API_KEY"] = prev


@pytest.fixture(scope="module")
def client(create_tables) -> Generator[TestClient, None, None]:
    """FastAPI TestClient; DATABASE_URL already points at the SQLite test DB."""
    from main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded_data(create_tables):
    """
    Commit a minimal dataset visible to the TestClient's sessions.
    Inserts: Benchmark, two Markets, Trade, Position, PositionHistory,
    and DailyPerformance rows. Cleans up in FK-safe order on teardown.
    """
    db = SessionLocal()
    try:
        bmark = models.Benchmark(
            event_prefix=_PREFIX,
            category="Test Category",
            subcategory="Totals",
            expected_win_rate=Decimal("0.70"),
            expected_ev_per_ctr=Decimal("0.0025"),
            sample_trades=200,
        )
        # Resolved market (has settled position history)
        market = models.Market(
            ticker=_TICKER,
            title="Test resolved market",
            event_prefix=_PREFIX,
            status="resolved",
            result="no",
            resolved_at=_SETTLED_AT,
        )
        trade = models.Trade(
            trade_id="TID-PHASE6-001",
            market_ticker=_TICKER,
            side="no",
            action="buy",
            price_cents=5,
            contracts=100,
            fee_usd=Decimal("0.24"),
            gross_cost_usd=Decimal("0.95"),
            strategy="longshot_fade",
            is_maker=True,
            filled_at=_FILLED_AT,
        )
        pos_hist = models.PositionHistory(
            market_ticker=_TICKER,
            side="no",
            net_contracts=100,
            avg_price_cents=Decimal("5"),
            total_cost_usd=Decimal("0.95"),
            total_fees_usd=Decimal("0.24"),
            result="no",
            won=True,
            gross_pnl_usd=Decimal("4.75"),
            net_pnl_usd=Decimal("4.51"),
            settled_at=_SETTLED_AT,
        )
        daily = models.DailyPerformance(
            date=_SETTLED_DT,
            trades_settled=1,
            wins=1,
            losses=0,
            win_rate=Decimal("1.0"),
            gross_pnl_usd=Decimal("4.75"),
            net_pnl_usd=Decimal("4.51"),
            fees_usd=Decimal("0.24"),
            capital_deployed_usd=Decimal("0"),
            cumulative_net_pnl_usd=Decimal("4.51"),
        )
        # Open market + position (for list_positions tests)
        open_market = models.Market(
            ticker=_OPEN_TICK,
            event_prefix=_PREFIX,
            status="open",
        )
        open_pos = models.Position(
            market_ticker=_OPEN_TICK,
            side="no",
            net_contracts=50,
            avg_price_cents=Decimal("6"),
            total_cost_usd=Decimal("0.47"),
            total_fees_usd=Decimal("0.12"),
            unrealized_pnl_usd=Decimal("0.15"),
            opened_at=datetime(2024, 9, 10, tzinfo=timezone.utc),
        )

        db.add_all([bmark, market, trade, pos_hist, daily, open_market, open_pos])
        db.commit()
        yield {"ticker": _TICKER, "open_ticker": _OPEN_TICK, "settled_date": _SETTLED_DT}

    finally:
        # Delete in FK-safe order
        db.query(models.DailyPerformance).filter(
            models.DailyPerformance.date == _SETTLED_DT
        ).delete()
        db.query(models.PositionHistory).filter(
            models.PositionHistory.market_ticker == _TICKER
        ).delete()
        db.query(models.Position).filter(
            models.Position.market_ticker == _OPEN_TICK
        ).delete()
        db.query(models.Trade).filter(
            models.Trade.trade_id == "TID-PHASE6-001"
        ).delete()
        db.query(models.Market).filter(
            models.Market.ticker.in_([_TICKER, _OPEN_TICK])
        ).delete(synchronize_session=False)
        db.query(models.Benchmark).filter(
            models.Benchmark.event_prefix == _PREFIX
        ).delete()
        db.commit()
        db.close()


# ── Health ─────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_includes_version(self, client):
        r = client.get("/health")
        assert "version" in r.json()

    def test_no_auth_required(self, client):
        """Health check must be publicly accessible."""
        r = client.get("/health")
        assert r.status_code == 200


# ── Auth ───────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_missing_header_returns_4xx(self, client):
        r = client.get("/positions/")
        assert r.status_code in (401, 403)   # starlette version-dependent

    def test_wrong_key_returns_401(self, client):
        r = client.get("/positions/", headers={"Authorization": "Bearer bad-key"})
        assert r.status_code == 401

    def test_correct_key_allowed(self, client):
        r = client.get("/positions/", headers=_AUTH)
        assert r.status_code == 200

    def test_auth_required_on_all_protected_routes(self, client):
        routes = [
            "/positions/", "/trades/", "/performance/summary",
            "/performance/daily", "/performance/by-category",
            "/categories/", "/alerts/", "/benchmarks/",
        ]
        for route in routes:
            r = client.get(route)
            assert r.status_code in (401, 403), (
                f"{route} should require auth (got {r.status_code})"
            )


# ── Positions ──────────────────────────────────────────────────────────────────

class TestPositions:
    def test_list_returns_list(self, client, seeded_data):
        r = client.get("/positions/", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_contains_seeded_position(self, client, seeded_data):
        r = client.get("/positions/", headers=_AUTH)
        tickers = [p["market_ticker"] for p in r.json()]
        assert seeded_data["open_ticker"] in tickers

    def test_list_schema_fields(self, client, seeded_data):
        r = client.get("/positions/", headers=_AUTH)
        required = ("market_ticker", "side", "net_contracts",
                    "avg_price_cents", "total_cost_usd", "unrealized_pnl_usd")
        for pos in r.json():
            for field in required:
                assert field in pos, f"Missing field '{field}'"

    def test_get_by_ticker(self, client, seeded_data):
        ticker = seeded_data["open_ticker"]
        r = client.get(f"/positions/{ticker}", headers=_AUTH)
        assert r.status_code == 200
        data = r.json()
        assert data["market_ticker"] == ticker
        assert data["side"] == "no"
        assert data["net_contracts"] == 50

    def test_get_unknown_ticker_404(self, client, seeded_data):
        r = client.get("/positions/DOESNOTEXIST-999", headers=_AUTH)
        assert r.status_code == 404

    def test_resolved_market_not_in_open_positions(self, client, seeded_data):
        """Settled position should not appear in /positions/ list."""
        r = client.get("/positions/", headers=_AUTH)
        tickers = [p["market_ticker"] for p in r.json()]
        assert seeded_data["ticker"] not in tickers


# ── Trades ─────────────────────────────────────────────────────────────────────

class TestTrades:
    def test_list_returns_list(self, client, seeded_data):
        r = client.get("/trades/", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_contains_seeded_trade(self, client, seeded_data):
        r = client.get("/trades/", headers=_AUTH)
        ids = [t["trade_id"] for t in r.json()]
        assert "TID-PHASE6-001" in ids

    def test_start_date_filter_excludes_old_trade(self, client, seeded_data):
        r = client.get("/trades/?start_date=2025-01-01", headers=_AUTH)
        assert r.status_code == 200
        ids = [t["trade_id"] for t in r.json()]
        assert "TID-PHASE6-001" not in ids   # trade is from 2024

    def test_trade_schema_fields(self, client, seeded_data):
        r = client.get("/trades/", headers=_AUTH)
        required = ("trade_id", "market_ticker", "side", "action",
                    "price_cents", "contracts", "fee_usd", "gross_cost_usd")
        for t in r.json():
            for field in required:
                assert field in t, f"Missing field '{field}'"

    def test_summary_returns_list(self, client, seeded_data):
        r = client.get("/trades/summary", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_summary_schema_fields(self, client, seeded_data):
        r = client.get("/trades/summary", headers=_AUTH)
        for row in r.json():
            for field in ("category", "trades", "contracts", "gross_cost_usd", "total_fees_usd"):
                assert field in row, f"Missing field '{field}'"


# ── Performance ────────────────────────────────────────────────────────────────

class TestPerformance:
    def test_summary_returns_schema(self, client, seeded_data):
        r = client.get("/performance/summary", headers=_AUTH)
        assert r.status_code == 200
        required = ("total_capital_deployed_usd", "unrealized_pnl_usd",
                    "realized_pnl_usd", "win_rate", "total_settled",
                    "total_wins", "total_losses")
        for field in required:
            assert field in r.json(), f"Missing field '{field}'"

    def test_summary_win_rate_in_range(self, client, seeded_data):
        r = client.get("/performance/summary", headers=_AUTH)
        wr = float(r.json()["win_rate"])
        assert 0.0 <= wr <= 1.0

    def test_summary_settled_count_positive(self, client, seeded_data):
        r = client.get("/performance/summary", headers=_AUTH)
        assert r.json()["total_settled"] >= 1

    def test_daily_returns_list(self, client, seeded_data):
        r = client.get("/performance/daily", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_daily_contains_seeded_date(self, client, seeded_data):
        r = client.get("/performance/daily", headers=_AUTH)
        dates = [row["date"] for row in r.json()]
        assert str(seeded_data["settled_date"]) in dates

    def test_daily_schema_fields(self, client, seeded_data):
        r = client.get("/performance/daily", headers=_AUTH)
        required = ("date", "net_pnl_usd", "wins", "losses", "win_rate",
                    "trades_settled", "cumulative_net_pnl_usd")
        for row in r.json():
            for field in required:
                assert field in row, f"Missing field '{field}'"

    def test_by_category_returns_list(self, client, seeded_data):
        r = client.get("/performance/by-category", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_by_category_schema_fields(self, client, seeded_data):
        r = client.get("/performance/by-category", headers=_AUTH)
        required = ("category", "trades", "actual_win_rate",
                    "expected_win_rate", "total_net_pnl_usd")
        for row in r.json():
            for field in required:
                assert field in row, f"Missing field '{field}'"


# ── Categories ─────────────────────────────────────────────────────────────────

class TestCategories:
    def test_list_returns_list(self, client, seeded_data):
        r = client.get("/categories/", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_contains_seeded_category(self, client, seeded_data):
        r = client.get("/categories/", headers=_AUTH)
        cats = [row["category"] for row in r.json()]
        assert "Test Category" in cats

    def test_category_schema_fields(self, client, seeded_data):
        r = client.get("/categories/", headers=_AUTH)
        required = ("category", "benchmark_count", "settled_trades",
                    "avg_expected_wr", "total_net_pnl_usd")
        for row in r.json():
            for field in required:
                assert field in row, f"Missing field '{field}'"


# ── Alerts ─────────────────────────────────────────────────────────────────────

class TestAlerts:
    def test_returns_list(self, client, seeded_data):
        r = client.get("/alerts/", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_alert_schema_when_present(self, client, seeded_data):
        r = client.get("/alerts/", headers=_AUTH)
        required = ("alert_type", "title", "message", "severity")
        for alert in r.json():
            for field in required:
                assert field in alert, f"Missing field '{field}'"


# ── Benchmarks ─────────────────────────────────────────────────────────────────

class TestBenchmarks:
    def test_list_returns_list(self, client, seeded_data):
        r = client.get("/benchmarks/", headers=_AUTH)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_contains_seeded_benchmark(self, client, seeded_data):
        r = client.get("/benchmarks/", headers=_AUTH)
        prefixes = [b["event_prefix"] for b in r.json()]
        assert _PREFIX in prefixes

    def test_benchmark_schema_fields(self, client, seeded_data):
        r = client.get("/benchmarks/", headers=_AUTH)
        required = ("event_prefix", "category", "expected_win_rate", "expected_ev_per_ctr")
        for bm in r.json():
            for field in required:
                assert field in bm, f"Missing field '{field}'"

    def test_reload_imports_benchmarks(self, client):
        """Reload endpoint must call import_benchmarks and return a count."""
        r = client.post("/benchmarks/reload", headers=_AUTH)
        assert r.status_code == 200
        data = r.json()
        assert "imported" in data
        assert isinstance(data["imported"], int)
        assert data["imported"] > 0

    def test_benchmarks_populated_after_reload(self, client):
        """After reload, the list endpoint should return rows from the CSV files."""
        client.post("/benchmarks/reload", headers=_AUTH)
        r = client.get("/benchmarks/", headers=_AUTH)
        assert r.status_code == 200
        assert len(r.json()) > 100   # we imported 717 rows
