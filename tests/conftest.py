"""
conftest.py
pytest fixtures shared across all test modules.
Implemented in Phase 2.5.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure ingestion and api packages are importable
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

# Phase 2.5: add fixtures for:
#   - in-memory SQLite test database (fast, no Docker required for unit tests)
#   - seeded market + trade rows
#   - mock KalshiClient for ingestion tests
