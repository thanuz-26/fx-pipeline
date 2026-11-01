"""Load step: write tidy exchange rates into PostgreSQL (idempotent upsert)."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# If a row with the same (rate_date, base_currency, quote_currency) already exists,
# update it instead of failing or creating a duplicate.
UPSERT_SQL = text(
    """
    INSERT INTO core.fx_rates
        (rate_date, base_currency, quote_currency, rate, source)
    VALUES
        (:rate_date, :base_currency, :quote_currency, :rate, :source)
    ON CONFLICT (rate_date, base_currency, quote_currency)
    DO UPDATE SET
        rate      = EXCLUDED.rate,
        source    = EXCLUDED.source,
        loaded_at = now()
    """
)


def load_rates(df: pd.DataFrame, engine: Engine) -> int:
    """Upsert the rows of df into core.fx_rates.

    Args:
        df: DataFrame from transform_rates() (columns match core.fx_rates).
        engine: SQLAlchemy engine connected to the database.

    Returns:
        The number of rows sent to the database.
    """
    records = df.to_dict(orient="records")
    if not records:
        return 0

    # engine.begin() = one transaction: everything is saved, or nothing is.
    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, records)
    return len(records)