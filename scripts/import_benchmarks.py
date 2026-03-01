"""
scripts/import_benchmarks.py
Reads Becker backtest CSV files from the benchmarks/ directory
and populates (or refreshes) the benchmarks table.

The expected CSV columns match the output of backtest_four_drills.py:
  event_prefix, category, subcategory, subgroup (politics only),
  trades, win_rate, ev_per_ctr, total_pnl, sharpe,
  median_days, p90_days, low_sample

Usage:
    python scripts/import_benchmarks.py [benchmarks_dir]
    docker-compose exec api python scripts/import_benchmarks.py /benchmarks

Implemented in Phase 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

def main(benchmarks_dir: Path) -> None:
    raise NotImplementedError("Implemented in Phase 2")

if __name__ == "__main__":
    bdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "benchmarks"
    main(bdir)
