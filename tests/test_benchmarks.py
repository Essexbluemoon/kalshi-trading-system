"""
tests/test_benchmarks.py
Verifies benchmark import from Becker CSV files.

Uses the same SQLite test database as the rest of the suite (set up in
conftest.py).  The `populated_benchmarks` fixture runs `import_benchmarks()`
once for the module, then tears down the benchmarks table afterward so
other test modules start clean.

Test cases:
  - Known prefixes present after import (spot-check key categories)
  - EV values are plausible numbers (within physically possible range)
  - No null event_prefix rows survive the import filter
  - Total row count is consistent with source CSVs
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select, func, text

from database import engine
import models

_BENCHMARKS_DIR = Path(__file__).parent.parent / "benchmarks"

# Prefixes we know must be present from the seed CSVs
_EXPECTED_PREFIXES = [
    "KXATPMATCH",    # tennis deep drill — generic ATP
    "KXWTAMATCH",    # tennis deep drill — generic WTA
    "KXCPIYOY",      # KX economic indicator
    "KXGDP",         # KX economic indicator
    "KXPAYROLLS",    # KX economic indicator
    "KXGOVSHUTLENGTH",  # politics drill
    "CABINETMUSK",   # politics drill — executive nominations
]


@pytest.fixture(scope="module")
def populated_benchmarks(create_tables):
    """
    Import all benchmark CSVs into the test DB exactly once for this module.
    Cleans up the benchmarks table on teardown.
    """
    from import_benchmarks import import_benchmarks

    if not _BENCHMARKS_DIR.exists():
        pytest.skip(f"Benchmarks directory not found: {_BENCHMARKS_DIR}")

    count = import_benchmarks(_BENCHMARKS_DIR, replace=True)
    yield count

    # Teardown: wipe benchmarks so other modules start from a clean state
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM benchmarks"))


class TestBenchmarkImport:
    def test_known_prefixes_present(self, populated_benchmarks):
        """All spot-check prefixes must survive the import and de-dup pass."""
        with engine.connect() as conn:
            rows = conn.execute(select(models.Benchmark.event_prefix)).fetchall()
        present = {r[0] for r in rows}

        missing = [p for p in _EXPECTED_PREFIXES if p not in present]
        assert not missing, f"Expected prefixes missing from benchmarks table: {missing}"

    def test_ev_values_in_range(self, populated_benchmarks):
        """All non-null EV values must be physically plausible.

        EV per contract is bounded by [−1.00, 1.00] since each contract
        pays out at most $1.00.  Values outside this range indicate a data
        or unit error in the source CSV.
        """
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    models.Benchmark.event_prefix,
                    models.Benchmark.expected_ev_per_ctr,
                ).where(models.Benchmark.expected_ev_per_ctr.isnot(None))
            ).fetchall()

        assert rows, "No non-null EV rows found — import may have failed"

        out_of_range = [
            (prefix, float(ev))
            for prefix, ev in rows
            if not (-1.0 < float(ev) < 1.0)
        ]
        assert not out_of_range, (
            f"EV out of [-1, 1] range for: {out_of_range[:5]}"
        )

    def test_no_null_prefixes(self, populated_benchmarks):
        """The import filter must discard any rows with a null event_prefix."""
        with engine.connect() as conn:
            null_count = conn.execute(
                select(func.count()).where(
                    models.Benchmark.event_prefix.is_(None)
                )
            ).scalar()
        assert null_count == 0, f"Found {null_count} rows with null event_prefix"

    def test_row_count_consistent(self, populated_benchmarks):
        """Total imported rows should match what import_benchmarks() reported."""
        imported_count = populated_benchmarks  # fixture yields the return value

        with engine.connect() as conn:
            db_count = conn.execute(
                select(func.count(models.Benchmark.event_prefix))
            ).scalar()

        assert db_count == imported_count, (
            f"DB has {db_count} rows but import reported {imported_count}"
        )
        # Sanity bound: we expect at least 700 rows from the seed CSVs
        assert db_count >= 700, f"Unexpectedly low row count: {db_count}"

    def test_categories_populated(self, populated_benchmarks):
        """Multiple distinct categories must be present (not all in one bucket)."""
        with engine.connect() as conn:
            cats = conn.execute(
                select(func.count(models.Benchmark.category.distinct()))
            ).scalar()
        assert cats >= 5, f"Expected at least 5 distinct categories, got {cats}"

    def test_event_prefix_is_uppercase(self, populated_benchmarks):
        """All event_prefix values should be normalised to uppercase."""
        with engine.connect() as conn:
            rows = conn.execute(select(models.Benchmark.event_prefix)).fetchall()

        non_upper = [r[0] for r in rows if r[0] != r[0].upper()]
        assert not non_upper, f"Non-uppercase prefixes found: {non_upper[:5]}"
