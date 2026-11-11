"""Unit tests for the transform step (small fake data, no API, no database)."""

from datetime import date

from fx_pipeline.transform import OUTPUT_COLUMNS, transform_rates

# Two records like the API returns; the first has a messy currency code on purpose.
RAW = [
    {"date": "2026-10-30", "base": "EUR", "quote": "usd ", "rate": 1.1172},
    {"date": "2026-10-30", "base": "EUR", "quote": "GBP", "rate": 0.8338},
]


def test_columns_match_database_and_source_is_added() -> None:
    df = transform_rates(RAW)
    assert list(df.columns) == OUTPUT_COLUMNS
    assert (df["source"] == "ECB").all()


def test_date_is_converted_and_currency_codes_are_cleaned() -> None:
    df = transform_rates(RAW)
    assert df.loc[0, "rate_date"] == date(2026, 10, 30)
    assert df.loc[0, "quote_currency"] == "USD"  # "usd " -> "USD"


def test_rate_stays_numeric() -> None:
    df = transform_rates(RAW)
    assert df["rate"].tolist() == [1.1172, 0.8338]