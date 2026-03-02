"""
tests/test_migrate.py
Tests for scripts/migrate.py — the schema-creation script Railway runs on deploy.

Two areas:
  1. Fresh-DB creation: Base.metadata.create_all() against a temp SQLite file
     produces exactly the tables and indexes that migrate.py declares.
  2. Idempotency: running create_all() twice, and create_schema() against an
     already-migrated DB, must not raise.
  3. Maintenance-list accuracy: TABLES_EXPECTED and INDEXES_EXPECTED match
     the actual ORM model definitions so the deploy check never false-positives.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect

# conftest.py has already added api/ and scripts/ to sys.path and set DATABASE_URL.
from database import Base
import models  # noqa: F401 — registers all ORM models with Base


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fresh_engine(tmp_path_factory):
    """A brand-new SQLite DB with no tables — used to test from-scratch creation."""
    db_path = tmp_path_factory.mktemp("migrate") / "fresh.db"
    eng = create_engine(f"sqlite:///{db_path}")
    yield eng
    eng.dispose()


@pytest.fixture(scope="module")
def migrated_engine(fresh_engine):
    """The fresh engine after Base.metadata.create_all() has been run once."""
    Base.metadata.create_all(bind=fresh_engine)
    yield fresh_engine


# ── Tests: fresh-DB schema creation ───────────────────────────────────────────

class TestFreshDBCreation:

    def test_all_expected_tables_present(self, migrated_engine):
        """create_all() creates every table declared in TABLES_EXPECTED."""
        from migrate import TABLES_EXPECTED

        inspector = sa_inspect(migrated_engine)
        existing = set(inspector.get_table_names())
        for table in TABLES_EXPECTED:
            assert table in existing, f"Table {table!r} was not created"

    def test_no_extra_unexpected_tables(self, migrated_engine):
        """create_all() creates exactly the 6 expected tables, nothing more."""
        from migrate import TABLES_EXPECTED

        inspector = sa_inspect(migrated_engine)
        existing = set(inspector.get_table_names())
        assert existing == set(TABLES_EXPECTED), (
            f"Unexpected tables: {existing - set(TABLES_EXPECTED)}"
        )

    def test_all_expected_indexes_present(self, migrated_engine):
        """create_all() creates every index listed in INDEXES_EXPECTED."""
        from migrate import INDEXES_EXPECTED

        inspector = sa_inspect(migrated_engine)
        for table_name, index_name in INDEXES_EXPECTED:
            existing_idx = {idx["name"] for idx in inspector.get_indexes(table_name)}
            assert index_name in existing_idx, (
                f"Index {index_name!r} missing from table {table_name!r}"
            )

    def test_create_all_is_idempotent(self, migrated_engine):
        """Calling create_all() a second time must not raise (checkfirst=True)."""
        Base.metadata.create_all(bind=migrated_engine, checkfirst=True)   # no-op second call


# ── Tests: maintenance-list accuracy ──────────────────────────────────────────

class TestMaintenanceLists:

    def test_tables_expected_matches_orm_models(self):
        """
        TABLES_EXPECTED must equal the set of tables registered in Base.metadata.
        If a model is added or removed, this test catches any drift in the list.
        """
        from migrate import TABLES_EXPECTED

        orm_tables = set(Base.metadata.tables.keys())
        assert set(TABLES_EXPECTED) == orm_tables, (
            f"TABLES_EXPECTED drift — "
            f"extra: {set(TABLES_EXPECTED) - orm_tables}, "
            f"missing: {orm_tables - set(TABLES_EXPECTED)}"
        )

    def test_indexes_expected_all_defined_in_models(self):
        """
        Every (table, index) pair in INDEXES_EXPECTED must exist in the ORM
        model metadata. Catches index renames or removals before deploy.
        """
        from migrate import INDEXES_EXPECTED

        for table_name, index_name in INDEXES_EXPECTED:
            table = Base.metadata.tables.get(table_name)
            assert table is not None, f"Table {table_name!r} not in Base.metadata"
            idx_names = {idx.name for idx in table.indexes}
            assert index_name in idx_names, (
                f"Index {index_name!r} not defined on model table {table_name!r}"
            )


# ── Tests: create_schema() end-to-end ─────────────────────────────────────────

class TestCreateSchema:

    def test_runs_without_error_on_existing_db(self, create_tables, capsys):
        """
        create_schema() called against an already-migrated DB must complete
        without raising, since Base.metadata.create_all(..., checkfirst=True)
        is a no-op when tables exist.
        """
        from migrate import create_schema
        create_schema()   # tables already exist from conftest create_tables fixture

    def test_does_not_call_sys_exit_when_tables_present(self, create_tables, monkeypatch):
        """
        The script calls sys.exit(1) only when tables are missing.
        With a fully migrated DB it must not exit.
        """
        import sys
        exit_calls = []
        monkeypatch.setattr(sys, "exit", lambda code: exit_calls.append(code))

        from migrate import create_schema
        create_schema()

        assert exit_calls == [], f"sys.exit called unexpectedly with: {exit_calls}"
