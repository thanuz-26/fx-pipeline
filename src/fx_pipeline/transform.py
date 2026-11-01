"""Transform step: turn the raw API JSON into a tidy table for the database."""

from __future__ import annotations

from typing import Any

import pandas as pd

# The exact columns (and order) that core.fx_rates expects.
OUTPUT_COLUMNS = ["rate_date", "base_currency", "quote_currency", "rate", "source"]


def transform_rates(raw: list[dict[str, Any]], source: str = "ECB") -> pd.DataFrame:
    """Convert the API's JSON list into a clean DataFrame for core.fx_rates.

    Args:
        raw: The list of dicts returned by extract.fetch_rates().
        source: Label stored in the "source" column.

    Returns:
        A DataFrame with exactly the columns in OUTPUT_COLUMNS.
    """
    df = pd.DataFrame(raw)

    # 1. Rename API field names to our database column names.
    df = df.rename(
        columns={
            "date": "rate_date",
            "base": "base_currency",
            "quote": "quote_currency",
        }
    )

    # 2. Convert types: text -> real calendar date, and make sure rate is a number.
    df["rate_date"] = pd.to_datetime(df["rate_date"]).dt.date
    df["rate"] = pd.to_numeric(df["rate"])

    # 3. Standardise currency codes: no spaces, always upper case ("usd " -> "USD").
    df["base_currency"] = df["base_currency"].str.strip().str.upper()
    df["quote_currency"] = df["quote_currency"].str.strip().str.upper()

    # 4. Add the column the API doesn't provide.
    df["source"] = source

    # 5. Keep only our columns, in the order the table expects.
    return df[OUTPUT_COLUMNS]