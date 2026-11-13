"""Integration tests for load.py against a real (temporary) PostgreSQL database."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from fx_pipeline.load import load_rates, load_raw

pytestmark = pytest.mark.integration


def make_df(usd_rate: float = 1.1) -> pd.DataFrame:
    """Two tidy rows in the shape transform_rates() produces."""
    rows = [
        ("USD", usd_rate),
        ("GBP", 0.83),
    ]
    return pd.DataFrame(
        [
            {
                "rate_date": date(2026, 10, 30),
                "base_currency": "EUR",
                "quote_currency": quote,
                "rate": rate,
                "source": "ECB",
            }
            for quote, rate in rows
        ]
    )


def count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_load_inserts_rows(db_engine: Engine) -> None:
    assert load_rates(make_df(), db_engine) == 2
    assert count(db_engine, "core.fx_rates") == 2


def test_loading_twice_creates_no_duplicates(db_engine: Engine) -> None:
    load_rates(make_df(), db_engine)
    load_rates(make_df(), db_engine)
    assert count(db_engine, "core.fx_rates") == 2  # idempotent


def test_upsert_updates_an_existing_rate(db_engine: Engine) -> None:
    load_rates(make_df(usd_rate=1.1), db_engine)
    load_rates(make_df(usd_rate=1.2), db_engine)  # same key, new rate
    with db_engine.connect() as conn:
        rate = conn.execute(
            text("SELECT rate FROM core.fx_rates WHERE quote_currency = 'USD'")
        ).scalar_one()
    assert count(db_engine, "core.fx_rates") == 2
    assert float(rate) == pytest.approx(1.2)


def test_database_refuses_a_non_positive_rate(db_engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        load_rates(make_df(usd_rate=-1.0), db_engine)
    assert count(db_engine, "core.fx_rates") == 0  # the whole load was rolled back


def test_raw_table_is_append_only(db_engine: Engine) -> None:
    payload = [{"date": "2026-10-30", "base": "EUR", "quote": "USD", "rate": 1.1}]
    load_raw(payload, db_engine)
    load_raw(payload, db_engine)
    assert count(db_engine, "raw.fx_rates_raw") == 2