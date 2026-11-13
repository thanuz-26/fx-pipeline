"""Shared pytest fixtures: a throwaway PostgreSQL database for integration tests."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from fx_pipeline.config import get_database_url

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """Create an empty temporary database with our tables; drop it afterwards."""
    base_url = get_database_url()
    admin = create_engine(base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    name = f"fx_test_{uuid.uuid4().hex[:8]}"

    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # no Docker / database not reachable: skip, don't fail
        admin.dispose()
        pytest.skip(f"PostgreSQL not reachable: {exc}")

    engine = create_engine(base_url.set(database=name))
    try:
        with engine.begin() as conn:
            for script in sorted(SQL_DIR.glob("*.sql")):
                conn.exec_driver_sql(script.read_text(encoding="utf-8"))
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()