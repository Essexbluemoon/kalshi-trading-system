"""
ingest_trades.py
Main ingestion loop. Fetches fills from Kalshi, upserts markets,
inserts trades, and triggers position + daily rollup updates.

One cycle (run_ingestion_cycle):
  1. Fetch fills since last filled_at in DB
  2. Batch-upsert market metadata for any new tickers
  3. Insert new trades (idempotent on trade_id)
  4. Rebuild open positions from all trades
  5. Fetch portfolio settlements → resolve markets + settle positions
  6. Update daily_performance rollup for affected dates
  7. Run reconcile checks (log alerts)
  8. Commit
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func

logger = logging.getLogger(__name__)


def run_ingestion_cycle(db_session, kalshi_client) -> dict:
    """
    Execute one full ingestion cycle.

    Returns a dict with:
      fills_fetched, trades_inserted, markets_upserted,
      positions_rebuilt, positions_settled
    """
    import models
    from ingest_markets import upsert_market, fetch_and_apply_resolutions
    from position_manager import rebuild_positions, settle_position
    from reconcile import run_reconcile

    stats: dict[str, int] = {
        "fills_fetched": 0,
        "trades_inserted": 0,
        "markets_upserted": 0,
        "positions_rebuilt": 0,
        "positions_settled": 0,
    }

    # ── 1. Fetch fills ─────────────────────────────────────────────────────────
    last_ts = _get_last_ingested_at(db_session)
    fills   = kalshi_client.get_fills(since=last_ts)
    stats["fills_fetched"] = len(fills)
    logger.info("Fetched %d fills (since=%s)", len(fills), last_ts)

    if not fills:
        return stats

    # ── 2. Batch-upsert market metadata ────────────────────────────────────────
    unique_tickers = list({(f.get("ticker") or f.get("market_ticker") or "").upper()
                           for f in fills} - {""})
    if unique_tickers:
        market_datas = kalshi_client.get_markets_batch(unique_tickers)
        # Index by ticker for fast lookup; fall back to minimal stub if missing
        market_map: dict[str, dict] = {
            (m.get("ticker") or "").upper(): m for m in market_datas
        }
        for ticker in unique_tickers:
            mdata = market_map.get(ticker) or {"ticker": ticker, "status": "open"}
            if upsert_market(mdata, db_session):
                stats["markets_upserted"] += 1
    db_session.flush()

    # ── 3. Insert new trades ───────────────────────────────────────────────────
    existing_ids: set[str] = {
        row[0]
        for row in db_session.execute(select(models.Trade.trade_id))
    }

    for fill in fills:
        tid = fill.get("trade_id") or ""
        if not tid or tid in existing_ids:
            continue

        ticker = (fill.get("ticker") or fill.get("market_ticker") or "").upper()

        side_raw   = fill.get("side")
        side       = side_raw.value.lower() if hasattr(side_raw, "value") else str(side_raw or "").lower()
        action_raw = fill.get("action")
        action     = action_raw.value.lower() if hasattr(action_raw, "value") else str(action_raw or "").lower()

        yes_price  = int(fill.get("yes_price") or 0)
        contracts  = int(fill.get("count") or 0)
        is_taker   = fill.get("is_taker") or False
        fee_str    = fill.get("fee_cost") or "0"

        # gross_cost_usd: cost of buying this position
        if side == "no":
            from position_manager import calc_no_cost
            gross_cost = calc_no_cost(contracts, yes_price)
        else:
            from position_manager import calc_yes_cost
            gross_cost = calc_yes_cost(contracts, yes_price)

        filled_at = _parse_dt(fill.get("created_time") or fill.get("ts"))

        category, subcategory, event_prefix = _classify_trade(ticker, db_session)

        trade = models.Trade(
            trade_id=tid,
            market_ticker=ticker,
            side=side,
            action=action,
            price_cents=yes_price,
            contracts=contracts,
            fee_usd=Decimal(str(fee_str)),
            gross_cost_usd=gross_cost,
            strategy="longshot_fade",
            is_maker=not is_taker,
            setup_grade=None,
            edge_type=None,
            notes=None,
            filled_at=filled_at,
        )
        db_session.add(trade)
        existing_ids.add(tid)
        stats["trades_inserted"] += 1

    db_session.flush()

    # ── 4. Rebuild open positions ──────────────────────────────────────────────
    stats["positions_rebuilt"] = rebuild_positions(db_session)

    # ── 5. Resolve markets + settle positions ─────────────────────────────────
    fetch_and_apply_resolutions(db_session, kalshi_client)
    db_session.flush()  # persist resolution status before querying

    resolved_markets = db_session.execute(
        select(models.Market).where(
            models.Market.status == "resolved",
            models.Market.result.isnot(None),
        )
    ).scalars().all()

    # Only settle markets that have an open position
    open_position_tickers: set[str] = {
        row[0]
        for row in db_session.execute(select(models.Position.market_ticker))
    }
    affected_dates: set[date] = set()

    for mkt in resolved_markets:
        if mkt.ticker not in open_position_tickers:
            continue
        try:
            settle_position(mkt.ticker, mkt.result, db_session)
            stats["positions_settled"] += 1
            if mkt.resolved_at:
                affected_dates.add(mkt.resolved_at.date())
        except ValueError as exc:
            logger.warning("settle_position skipped: %s", exc)

    # ── 6. Update daily performance ────────────────────────────────────────────
    affected_dates.add(datetime.now(timezone.utc).date())
    for d in affected_dates:
        _update_daily_performance(db_session, d)

    # ── 7. Reconcile alerts (log only — UI surfaced via API in Phase 4) ────────
    try:
        alerts = run_reconcile(db_session)
        for alert in alerts:
            logger.warning("ALERT [%s] %s: %s", alert.severity, alert.title, alert.message)
    except Exception:
        logger.exception("Reconcile check failed (non-fatal)")

    # ── 8. Commit ──────────────────────────────────────────────────────────────
    db_session.commit()
    logger.info("Ingestion cycle complete: %s", stats)
    return stats


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_last_ingested_at(db_session) -> datetime | None:
    """Return the most recent filled_at timestamp from the trades table."""
    import models
    ts = db_session.execute(select(func.max(models.Trade.filled_at))).scalar()
    return ts


def _classify_trade(ticker: str, db_session) -> tuple[str, str, str]:
    """
    Match the trade's ticker prefix against the benchmarks table.

    Returns (category, subcategory, event_prefix).
    Falls back to ("Uncategorized", "Unknown", derived_prefix) if no match.
    """
    import models
    from ingest_markets import _parse_event_prefix

    # First try the market's stored event_prefix
    mkt = db_session.get(models.Market, ticker)
    prefix = (mkt.event_prefix if mkt and mkt.event_prefix else None) or \
             _parse_event_prefix(ticker)

    if prefix:
        bmark = db_session.get(models.Benchmark, prefix)
        if bmark:
            return (
                bmark.category or "Uncategorized",
                bmark.subcategory or "Unknown",
                prefix,
            )

    return ("Uncategorized", "Unknown", prefix or "")


def _update_daily_performance(db_session, settlement_date: date) -> None:
    """
    Roll up all position_history rows settled on `settlement_date` into
    the daily_performance table. Upserts by date (primary key).
    """
    import models
    from sqlalchemy import and_

    rows = db_session.execute(
        select(models.PositionHistory).where(
            func.date(models.PositionHistory.settled_at) == str(settlement_date)
        )
    ).scalars().all()

    if not rows:
        return

    wins        = sum(1 for r in rows if r.won)
    losses      = len(rows) - wins
    gross_pnl   = sum(Decimal(str(r.gross_pnl_usd or 0)) for r in rows)
    net_pnl     = sum(Decimal(str(r.net_pnl_usd   or 0)) for r in rows)
    fees        = sum(Decimal(str(r.total_fees_usd or 0)) for r in rows)
    win_rate    = Decimal(str(wins / len(rows))) if rows else Decimal("0")

    # Capital deployed = cost of ALL open positions at end of day
    deployed = db_session.execute(
        select(func.sum(models.Position.total_cost_usd))
    ).scalar() or Decimal("0")

    # Cumulative net P&L = sum of all settled net_pnl up to and including this date
    cumulative = db_session.execute(
        select(func.sum(models.PositionHistory.net_pnl_usd)).where(
            func.date(models.PositionHistory.settled_at) <= str(settlement_date)
        )
    ).scalar() or Decimal("0")

    existing = db_session.get(models.DailyPerformance, settlement_date)
    if existing is None:
        dp = models.DailyPerformance(
            date=settlement_date,
            trades_settled=len(rows),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            gross_pnl_usd=gross_pnl,
            net_pnl_usd=net_pnl,
            fees_usd=fees,
            capital_deployed_usd=Decimal(str(deployed)),
            cumulative_net_pnl_usd=Decimal(str(cumulative)),
        )
        db_session.add(dp)
    else:
        existing.trades_settled = len(rows)
        existing.wins = wins
        existing.losses = losses
        existing.win_rate = win_rate
        existing.gross_pnl_usd = gross_pnl
        existing.net_pnl_usd = net_pnl
        existing.fees_usd = fees
        existing.capital_deployed_usd = Decimal(str(deployed))
        existing.cumulative_net_pnl_usd = Decimal(str(cumulative))

    db_session.flush()


def _parse_dt(ts: Any) -> datetime | None:
    """Parse an ISO-8601 string or Unix-int timestamp to a UTC datetime."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None
