"""
tests/test_benchmarks.py
Verifies benchmark import from Becker CSV files.

Test cases (spec Phase 2.5):
  - Known categories present after import (e.g. KXGOVSHUT, KXATPMATCH)
  - EV values within expected ranges (0 < EV < 0.10 for longshot-fade)
  - No null event_prefix rows
  - Row count matches source CSV

Implemented in Phase 2.5.
"""
import pytest


class TestBenchmarkImport:
    def test_known_prefixes_present(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_ev_values_in_range(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_no_null_prefixes(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_row_count_matches_csv(self):
        pytest.skip("Implemented in Phase 2.5")
