"""
tests/test_position.py
Verifies position aggregation logic.

Test cases (spec Phase 2.5):
  - Multiple fills on same market aggregate correctly
  - Partial close reduces net_contracts and updates avg_price
  - Full close moves position to position_history

Implemented in Phase 2.5.
"""
import pytest


class TestPositionAggregation:
    def test_multiple_fills_same_market(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_partial_close(self):
        pytest.skip("Implemented in Phase 2.5")

    def test_full_close(self):
        pytest.skip("Implemented in Phase 2.5")
