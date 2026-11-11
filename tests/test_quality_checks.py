"""Unit tests for the data quality checks (small fake data, no API, no database)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from fx_pipeline.quality_checks import (
    check_duplicates,
    check_missing_values,
    check_rate_positive,
    check_schema,
)


def make_row(**overrides: Any) -> dict[str, Any]:
    """One good row in the shape transform_rates() produces; override to break it."""
    row: dict[str, Any] = {
        "rate_date": date(2026, 10, 30),
        "base_currency": "EUR",
        "quote_currency": "USD",
        "rate": 1.1,
        "source": "ECB",
    }
    row.update(overrides)
    return row


# ---------- schema ----------

GOOD_RECORD = {"date": "2026-10-30", "base": "EUR", "quote": "USD", "rate": 1.1}


def test_schema_passes_for_valid_records() -> None:
    result = check_schema([GOOD_RECORD])
    assert result.status == "pass"
    assert result.failed_count == 0


def test_schema_fails_for_missing_field() -> None:
    record = {k: v for k, v in GOOD_RECORD.items() if k != "rate"}
    result = check_schema([GOOD_RECORD, record])
    assert result.status == "fail"
    assert result.failed_count == 1
    assert "rate" in (result.details or "")


def test_schema_fails_for_wrong_type() -> None:
    result = check_schema([{**GOOD_RECORD, "rate": "abc"}])
    assert result.status == "fail"
    assert result.failed_count == 1


def test_schema_does_not_accept_a_boolean_as_rate() -> None:
    result = check_schema([{**GOOD_RECORD, "rate": True}])
    assert result.status == "fail"


def test_schema_fails_when_response_is_not_a_list() -> None:
    result = check_schema({"status": 422, "message": "invalid currency: ABC"})
    assert result.status == "fail"
    assert result.failed_count == 1


# ---------- missing values ----------


def test_missing_values_passes_for_complete_rows() -> None:
    df = pd.DataFrame([make_row(), make_row(quote_currency="GBP")])
    assert check_missing_values(df).status == "pass"


def test_missing_values_counts_null_and_blank() -> None:
    df = pd.DataFrame(
        [make_row(), make_row(rate=None), make_row(quote_currency="  ")]
    )
    result = check_missing_values(df)
    assert result.status == "fail"
    assert result.failed_count == 2  # the null rate and the blank currency


# ---------- duplicates ----------


def test_duplicates_passes_when_keys_are_unique() -> None:
    df = pd.DataFrame([make_row(), make_row(quote_currency="GBP")])
    assert check_duplicates(df).status == "pass"


def test_duplicates_counts_only_the_extra_rows() -> None:
    df = pd.DataFrame(
        [make_row(), make_row(rate=1.2), make_row(quote_currency="GBP")]
    )
    result = check_duplicates(df)
    assert result.status == "fail"
    assert result.failed_count == 1  # row 1 repeats the key of row 0


# ---------- rate must be positive ----------


def test_rate_positive_passes_for_positive_rates() -> None:
    df = pd.DataFrame([make_row(), make_row(rate=0.0001)])
    assert check_rate_positive(df).status == "pass"


def test_rate_positive_fails_for_zero_and_negative() -> None:
    df = pd.DataFrame([make_row(), make_row(rate=0), make_row(rate=-1.5)])
    result = check_rate_positive(df)
    assert result.status == "fail"
    assert result.failed_count == 2


def test_rate_positive_ignores_missing_rates() -> None:
    df = pd.DataFrame([make_row(rate=None)])
    assert check_rate_positive(df).status == "pass"  # check_missing_values owns this

def test_schema_fails_when_a_record_is_not_an_object() -> None:
    result = check_schema([GOOD_RECORD, 42])
    assert result.status == "fail"
    assert result.failed_count == 1
    assert "not an object" in (result.details or "")