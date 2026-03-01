"""
conftest.py
Shared pytest fixtures for the Kalshi Trading System test suite.

Sets DATABASE_URL to a local SQLite file BEFORE any api/ingestion modules
are imported, so the global SQLAlchemy engine points at SQLite throughout
the test session.

Fixtures:
  create_tables  — session-scoped, autouse: creates all ORM tables once and
                   drops + deletes the DB file on teardown.
  db_session     — function-scoped: yields a rolled-back-on-teardown session
                   for tests that need DB access without persisting changes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Must set DATABASE_URL before any api/ or ingestion/ imports ───────────────
_TEST_DB = Path(__file__).parent / "test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB}")

# Make api/, ingestion/, and scripts/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

from database import Base, engine, SessionLocal
import models  # noqa: F401 — side-effect: registers all ORM models with Base


# ── Session-scoped schema fixture ─────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once for the test session; drop and delete on exit."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()          # release the file lock before deleting (Windows)
    _TEST_DB.unlink(missing_ok=True)


# ── Per-test database session ─────────────────────────────────────────────────

@pytest.fixture
def db_session(create_tables):
    """
    Yield a SQLAlchemy session that is rolled back after each test.

    Uses flush() (not commit()) to make inserted rows visible within the
    session for assertions, while keeping the transaction open so rollback
    on teardown fully restores the database state.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
