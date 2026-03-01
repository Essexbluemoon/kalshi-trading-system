"""
scripts/migrate.py
Creates all database tables and indexes.
Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS via SQLAlchemy's
checkfirst=True, so existing data is never dropped.

Usage:
    # Against local PostgreSQL (docker-compose running):
    python scripts/migrate.py

    # Inside the API container:
    docker-compose exec api python scripts/migrate.py

    # Override the database URL:
    DATABASE_URL=sqlite:///./test.db python scripts/migrate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow importing from api/
_API_DIR = Path(__file__).parent.parent / "api"
sys.path.insert(0, str(_API_DIR))

from sqlalchemy import inspect, text   # noqa: E402
from database import Base, engine      # noqa: E402
import models  # noqa: F401, E402  — side-effect: registers all ORM models


TABLES_EXPECTED = [
    "markets",
    "trades",
    "positions",
    "position_history",
    "benchmarks",
    "daily_performance",
]

INDEXES_EXPECTED = [
    ("trades",           "ix_trades_filled_at"),
    ("trades",           "ix_trades_market_ticker"),
    ("position_history", "ix_position_history_settled_at"),
]


def create_schema() -> None:
    print(f"Target database: {engine.url!r}")
    print()

    # ── Create tables ──────────────────────────────────────────────────────────
    print("Creating tables (skipping existing)...")
    Base.metadata.create_all(bind=engine, checkfirst=True)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    for table in TABLES_EXPECTED:
        status = "OK" if table in existing_tables else "MISSING"
        print(f"  [{status}] {table}")

    missing = [t for t in TABLES_EXPECTED if t not in existing_tables]
    if missing:
        print(f"\nERROR: Tables not created: {missing}", file=sys.stderr)
        sys.exit(1)

    # ── Verify indexes ──────────────────────────────────────────────────────────
    print("\nVerifying indexes...")
    for table_name, index_name in INDEXES_EXPECTED:
        if table_name not in existing_tables:
            print(f"  [SKIP]    {index_name} (table {table_name!r} missing)")
            continue
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
        status = "OK" if index_name in existing_indexes else "MISSING"
        print(f"  [{status}] {index_name} on {table_name}")

    # ── Row counts (useful after benchmark import) ─────────────────────────────
    print("\nRow counts:")
    with engine.connect() as conn:
        for table in TABLES_EXPECTED:
            if table in existing_tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table:<25} {count:>8,} rows")

    print("\nMigration complete.")


if __name__ == "__main__":
    create_schema()
