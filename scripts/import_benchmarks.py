"""
scripts/import_benchmarks.py
Reads Becker backtest CSV files from the benchmarks/ directory
and populates (or fully refreshes) the benchmarks table.

Each CSV has a different schema depending on which drill it came from.
This script normalises all of them into the common benchmarks schema:
  (event_prefix, category, subcategory, expected_win_rate,
   expected_ev_per_ctr, expected_sharpe, sample_trades,
   price_bucket, timing_filter, notes)

Only rows with a non-null event_prefix are importable.
Category-level CSVs without event_prefix are skipped (they don't map to
a single prefix and can't be matched to live trades).

Usage:
    python scripts/import_benchmarks.py [benchmarks_dir]
    docker-compose exec api python scripts/import_benchmarks.py /benchmarks
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pandas as pd

# Allow importing from api/
_API_DIR = Path(__file__).parent.parent / "api"
sys.path.insert(0, str(_API_DIR))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy import text                                      # noqa: E402
from database import engine, SessionLocal                        # noqa: E402
import models  # noqa: F401, E402


# ── CSV source definitions ──────────────────────────────────────────────────────
# Each entry: (filename, parser_function)
# Parser returns an iterable of dicts matching the benchmarks table columns.

def _parse_politics(df: pd.DataFrame) -> Iterator[dict]:
    """politics_drill.csv — has event_prefix."""
    for _, row in df.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            row.get("subgroup", row.get("category", "Politics")),
            "subcategory":         f"{row['category']} / {row['subcat']}",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               f"median_days={row.get('median_days')}, p90={row.get('p90_days')}",
        }


def _parse_world_events(df: pd.DataFrame) -> Iterator[dict]:
    """world_events_drill.csv — has event_prefix."""
    for _, row in df.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            "World Events",
            "subcategory":         f"{row['category']} / {row['subcat']}",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               f"median_days={row.get('median_days')}",
        }


def _parse_business(df: pd.DataFrame) -> Iterator[dict]:
    """business_drill.csv — has event_prefix; biz_type is the actionable category."""
    for _, row in df.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            row.get("biz_type", "Business"),
            "subcategory":         f"{row['category']} / {row['subcat']}",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               f"median_days={row.get('median_days')}",
        }


def _parse_other_sports(df: pd.DataFrame) -> Iterator[dict]:
    """other_sports_drill.csv — has event_prefix."""
    for _, row in df.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            "Sports",
            "subcategory":         row.get("subcat", "Other Sports"),
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               None,
        }


def _parse_tennis_deep(df: pd.DataFrame) -> Iterator[dict]:
    """
    tennis_deep_drill.csv — has event_prefix but multiple rows per prefix
    (pre-game / in-game split). Aggregate across timing splits,
    storing timing breakdown in notes.
    """
    # Collapse to one row per event_prefix using weighted mean
    agg = _weighted_aggregate(df, group_cols=["tier", "tour", "tournament", "event_prefix"])
    for _, row in agg.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            f"Tennis / {row['tier']}",
            "subcategory":         f"{row['tour']} / {row['tournament']}",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       "all",
            "notes":               f"median_days={_safe_float(row.get('median_days'))}, tour={row['tour']}",
        }


def _parse_sp500(df: pd.DataFrame) -> Iterator[dict]:
    """sp500_addition_markets.csv — has event_prefix."""
    for _, row in df.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            "Finance",
            "subcategory":         "S&P 500 Additions",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               (
                f"low_sample=True, "
                f"earliest={row.get('earliest_trade')}, latest={row.get('latest_trade')}"
            ),
        }


def _parse_indian_wells(df: pd.DataFrame) -> Iterator[dict]:
    """
    indian_wells.csv — event_prefix + timing + price_bucket.
    Aggregate to one row per (event_prefix, price_bucket), noting timing in filter.
    """
    agg = _weighted_aggregate(df, group_cols=["event_prefix", "tour", "price_bucket"])
    for _, row in agg.iterrows():
        yield {
            "event_prefix":        row["event_prefix"],
            "category":            "Tennis / Masters 1000",
            "subcategory":         f"Indian Wells ({row['tour']})",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        str(row.get("price_bucket")) if pd.notna(row.get("price_bucket")) else None,
            "timing_filter":       "all",
            "notes":               f"tour={row['tour']}, 2025 only (n={_safe_int(row.get('trades'))})",
        }


def _parse_kx_eco(df: pd.DataFrame) -> Iterator[dict]:
    """
    kx_vs_nonkx_dates.csv — prefix column is the event_prefix.
    Useful for storing KX economic indicator benchmarks.
    Only import KX variants (stronger signal).
    """
    kx_only = df[df["variant"] == "KX"].copy()
    for _, row in kx_only.iterrows():
        yield {
            "event_prefix":        row["prefix"],
            "category":            "Finance",
            "subcategory":         f"Economic Indicators / {row['indicator']}",
            "expected_win_rate":   _safe_float(row.get("win_rate")),
            "expected_ev_per_ctr": _safe_float(row.get("ev_per_ctr")),
            "expected_sharpe":     _safe_float(row.get("sharpe")),
            "sample_trades":       _safe_int(row.get("trades")),
            "price_bucket":        None,
            "timing_filter":       None,
            "notes":               (
                f"KX variant, active since {row.get('earliest_trade')}, "
                f"median_days={row.get('median_days')}"
            ),
        }


# ── Source registry ─────────────────────────────────────────────────────────────
# (filename, parser)  — order matters for upsert priority (later files win on conflict)
SOURCES = [
    ("kx_vs_nonkx_dates.csv",    _parse_kx_eco),
    ("sp500_addition_markets.csv",_parse_sp500),
    ("other_sports_drill.csv",   _parse_other_sports),
    ("world_events_drill.csv",   _parse_world_events),
    ("business_drill.csv",       _parse_business),
    ("tennis_deep_drill.csv",    _parse_tennis_deep),
    ("indian_wells.csv",         _parse_indian_wells),
    ("politics_drill.csv",       _parse_politics),   # highest priority (most granular)
]


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else round(f, 6)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _weighted_aggregate(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """
    Collapse multiple rows per group into one using trade-weighted means
    for win_rate, ev_per_ctr, sharpe; sum for trades.
    """
    rows = []
    for keys, grp in df.groupby(group_cols, observed=True):
        key_dict = dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,)))
        total_trades = grp["trades"].sum()
        w = grp["trades"] / total_trades if total_trades > 0 else pd.Series([1 / len(grp)] * len(grp), index=grp.index)
        row = {**key_dict, "trades": total_trades}
        for col in ("win_rate", "ev_per_ctr", "sharpe", "median_days", "p90_days"):
            if col in grp.columns:
                row[col] = (grp[col] * w).sum()
        rows.append(row)
    return pd.DataFrame(rows)


# ── Main import logic ────────────────────────────────────────────────────────────

def import_benchmarks(benchmarks_dir: Path, replace: bool = True) -> int:
    """
    Load all CSVs from benchmarks_dir and upsert into the benchmarks table.

    Args:
        benchmarks_dir: directory containing benchmark CSV files
        replace: if True, delete all existing rows first (full refresh)

    Returns:
        total rows written
    """
    all_rows: dict[str, dict] = {}   # event_prefix → row (later sources win on conflict)

    for filename, parser in SOURCES:
        path = benchmarks_dir / filename
        if not path.exists():
            print(f"  [SKIP]  {filename} (not found)")
            continue

        df = pd.read_csv(path)
        parsed = 0
        for row in parser(df):
            prefix = row.get("event_prefix")
            if not prefix or pd.isna(prefix):
                continue
            all_rows[str(prefix).strip().upper()] = row
            parsed += 1
        print(f"  [OK]    {filename}: {parsed} rows parsed")

    if not all_rows:
        print("No rows to import.")
        return 0

    # Normalise event_prefix keys back into rows
    rows_to_write = list(all_rows.values())
    for r in rows_to_write:
        r["event_prefix"] = str(r["event_prefix"]).strip().upper()

    with engine.begin() as conn:
        if replace:
            conn.execute(text("DELETE FROM benchmarks"))
            print(f"\n  Cleared existing benchmarks table.")

        # Batch insert
        conn.execute(
            models.Benchmark.__table__.insert(),
            rows_to_write,
        )

    print(f"  Inserted {len(rows_to_write):,} benchmark rows.")
    return len(rows_to_write)


def verify(expected_prefixes: list[str] | None = None) -> None:
    """Print a summary of the benchmarks table contents."""
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM benchmarks")).scalar()
        cats  = conn.execute(
            text("SELECT category, COUNT(*) as n FROM benchmarks GROUP BY category ORDER BY n DESC")
        ).fetchall()

    print(f"\nBenchmarks table: {total:,} total rows")
    print(f"{'Category':<40} {'Rows':>6}")
    print("-" * 48)
    for cat, n in cats:
        print(f"  {(cat or 'NULL'):<38} {n:>6,}")

    if expected_prefixes:
        from sqlalchemy import select
        with SessionLocal() as session:
            found = {
                row[0]
                for row in session.execute(
                    select(models.Benchmark.event_prefix).where(
                        models.Benchmark.event_prefix.in_(expected_prefixes)
                    )
                )
            }
        missing = set(expected_prefixes) - found
        if missing:
            print(f"\nWARNING: Expected prefixes missing from table: {sorted(missing)}")
        else:
            print(f"\nAll {len(expected_prefixes)} expected prefixes verified present.")


def main(benchmarks_dir: Path) -> None:
    import models  # ensure models are registered  # noqa: F401

    print(f"Importing benchmarks from: {benchmarks_dir.resolve()}")
    print(f"Target database: {engine.url!r}")
    print()

    total = import_benchmarks(benchmarks_dir, replace=True)

    verify(expected_prefixes=[
        "KXGOVSHUTLENGTH", "KXCPIYOY", "KXGDP", "KXPAYROLLS",
        "CABINETMUSK", "KXATPMATCH", "KXWTAMATCH",
    ])

    print(f"\nDone — {total:,} benchmark rows imported.")


if __name__ == "__main__":
    bdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "benchmarks"
    main(bdir)
