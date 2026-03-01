"""
scripts/migrate.py
Creates all database tables defined in api/models.py.
Run this once after standing up a fresh PostgreSQL instance.

Usage:
    python scripts/migrate.py
    docker-compose exec api python scripts/migrate.py

Implemented in Phase 2.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow importing from api/
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))

from database import Base, engine  # noqa: E402  (after sys.path insert)


def main() -> None:
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    main()
