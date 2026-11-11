"""More unit tests: remaining quality checks and the reject step (fake data only)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from fx_pipeline.quality_checks import (
    check_completeness,
    check_daily_change,
    check_freshness,
    check_row_count,
    reject_invalid_rows,
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


# ---------- day-over-day change ----------


def test_daily_change_passes_for_small_moves() -> None:
    df = pd.DataFrame(
        [
            make_row(rate_date=date(2026, 10, 26), rate=1.10),
            make_row(rate_date=date(2026, 10, 27), rate=1.11),
        ]
    )
    assert check_daily_change(df).status == "pass"


def test_daily_change_flags_a_big_jump() -> None:
    df = pd.DataFrame(
        [
            make_row(rate_date=date(2026, 10, 26), rate=1.10),
            make_row(rate_date=date(2026, 10, 27), rate=1.12),
            make_row(rate_date=date(2026, 10, 28), rate=1.30),  # +16 %
            make_row(rate_date=date(2026, 10, 29), rate=1.30),  # unchanged
        ]
    )
    result = check_daily_change(df)
    assert result.status == "fail"
    assert result.failed_count == 1
    assert "2026-10-28" in (result.details or "")


def test_daily_change_threshold_is_configurable() -> None:
    df = pd.DataFrame(
        [
            make_row(rate_date=date(2026, 10, 27), rate=1.12),
            make_row(rate_date=date(2026, 10, 28), rate=1.30),
        ]
    )
    assert check_daily_change(df, max_change=0.05).status == "fail"
    assert check_daily_change(df, max_change=0.20).status == "pass"


def test_daily_change_compares_each_pair_separately() -> None:
    df = pd.DataFrame(
        [
            make_row(rate_date=date(2026, 10, 26), quote_currency="USD", rate=1.10),
            make_row(rate_date=date(2026, 10, 27), quote_currency="USD", rate=1.11),
            make_row(rate_date=date(2026, 10, 26), quote_currency="GBP", rate=0.80),
            make_row(rate_date=date(2026, 10, 27), quote_currency="GBP", rate=0.95),
        ]
    )
    result = check_daily_change(df)
    assert result.failed_count == 1
    assert "GBP" in (result.details or "")


# ---------- completeness ----------


def test_completeness_passes_when_all_currencies_present() -> None:
    df = pd.DataFrame(
        [make_row(quote_currency="USD"), make_row(quote_currency="GBP")]
    )
    assert check_completeness(df, ["USD", "GBP"]).status == "pass"


def test_completeness_reports_the_missing_currency() -> None:
    df = pd.DataFrame(
        [
            make_row(rate_date=date(2026, 10, 26), quote_currency="USD"),
            make_row(rate_date=date(2026, 10, 26), quote_currency="GBP"),
            make_row(rate_date=date(2026, 10, 27), quote_currency="USD"),  # GBP missing
        ]
    )
    result = check_completeness(df, ["USD", "GBP"])
    assert result.status == "fail"
    assert result.failed_count == 1
    assert "2026-10-27" in (result.details or "")
    assert "GBP" in (result.details or "")


def test_completeness_counts_every_missing_pair() -> None:
    df = pd.DataFrame([make_row(quote_currency="CHF")])  # neither USD nor GBP
    assert check_completeness(df, ["USD", "GBP"]).failed_count == 2


# ---------- freshness ----------

FRESH_DF = pd.DataFrame([make_row(rate_date=date(2026, 10, 30))])  # a Friday


def test_freshness_passes_after_a_normal_weekend() -> None:
    assert check_freshness(FRESH_DF, today=date(2026, 11, 2)).status == "pass"  # 3 days


def test_freshness_accepts_exactly_the_maximum_age() -> None:
    assert check_freshness(FRESH_DF, today=date(2026, 11, 3)).status == "pass"  # 4 days


def test_freshness_fails_when_too_old() -> None:
    result = check_freshness(FRESH_DF, today=date(2026, 11, 4))  # 5 days
    assert result.status == "fail"
    assert "5 days" in (result.details or "")


def test_freshness_fails_for_an_empty_batch() -> None:
    assert check_freshness(pd.DataFrame(), today=date(2026, 11, 2)).status == "fail"


# ---------- row count ----------

THREE_ROWS = pd.DataFrame([make_row(), make_row(), make_row()])


def test_row_count_passes_inside_the_range() -> None:
    assert check_row_count(THREE_ROWS, min_rows=3).status == "pass"
    assert check_row_count(THREE_ROWS, min_rows=1, max_rows=3).status == "pass"


def test_row_count_fails_when_too_few() -> None:
    result = check_row_count(THREE_ROWS, min_rows=4)
    assert result.status == "fail"
    assert "3 rows" in (result.details or "")


def test_row_count_fails_when_too_many() -> None:
    assert check_row_count(THREE_ROWS, min_rows=1, max_rows=2).status == "fail"


def test_row_count_fails_for_an_empty_batch() -> None:
    assert check_row_count(pd.DataFrame(), min_rows=1).status == "fail"


# ---------- reject_invalid_rows ----------


def test_reject_keeps_everything_when_all_rows_are_valid() -> None:
    df = pd.DataFrame([make_row(), make_row(quote_currency="GBP")])
    clean, rejected = reject_invalid_rows(df)
    assert rejected == 0
    assert len(clean) == 2


def test_reject_removes_broken_rows_and_duplicates() -> None:
    df = pd.DataFrame(
        [
            make_row(),                          # 0: good
            make_row(rate=None),                 # 1: missing rate
            make_row(quote_currency="  "),       # 2: blank currency
            make_row(rate=-1.5),                 # 3: negative rate
            make_row(rate=1.15),                 # 4: twin of row 0
            make_row(quote_currency="GBP"),      # 5: good
        ]
    )
    clean, rejected = reject_invalid_rows(df)
    assert rejected == 4
    assert list(clean.index) == [0, 5]


def test_reject_never_lets_a_broken_row_beat_a_good_twin() -> None:
    df = pd.DataFrame([make_row(rate=None), make_row(rate=1.2)])  # same key
    clean, rejected = reject_invalid_rows(df)
    assert rejected == 1
    assert list(clean.index) == [1]
    assert clean.loc[1, "rate"] == 1.2