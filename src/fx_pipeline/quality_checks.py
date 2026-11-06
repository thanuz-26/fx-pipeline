"""Data quality checks. Each check is a small function returning a CheckResult."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

# Field name -> allowed Python types, for every record in the API response.
REQUIRED_FIELDS: dict[str, tuple[type, ...]] = {
    "date": (str,),
    "base": (str,),
    "quote": (str,),
    "rate": (int, float),
}


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one check; mirrors the columns of core.data_quality_results."""

    check_name: str
    status: str  # "pass" or "fail"
    failed_count: int = 0
    details: str | None = None


def _record_problem(record: Any) -> str | None:
    """Return a short description of the first problem in a record, or None."""
    if not isinstance(record, dict):
        return "not an object"
    for field, allowed_types in REQUIRED_FIELDS.items():
        if field not in record:
            return f"missing field '{field}'"
        value = record[field]
        # bool is a subclass of int in Python, so exclude it explicitly.
        if isinstance(value, bool) or not isinstance(value, allowed_types):
            return f"field '{field}' has wrong type {type(value).__name__}"
    return None


def check_schema(raw: Any) -> CheckResult:
    """Check that the raw API response is a list of well-formed records.

    Args:
        raw: The parsed JSON returned by extract.fetch_rates().

    Returns:
        A CheckResult named "schema"; failed_count is the number of bad records.
    """
    name = "schema"
    if not isinstance(raw, list):
        return CheckResult(name, "fail", 1, f"expected a list, got {type(raw).__name__}")

    failed = 0
    examples: list[str] = []
    for index, record in enumerate(raw):
        problem = _record_problem(record)
        if problem:
            failed += 1
            if len(examples) < 3:  # keep details short
                examples.append(f"record {index}: {problem}")

    if failed == 0:
        return CheckResult(name, "pass")
    return CheckResult(name, "fail", failed, "; ".join(examples))


REQUIRED_COLUMNS = ["rate_date", "base_currency", "quote_currency", "rate", "source"]
TEXT_COLUMNS = ["base_currency", "quote_currency", "source"]


def check_missing_values(df: pd.DataFrame) -> CheckResult:
    """Check for null values or blank text in the required columns.

    Args:
        df: DataFrame from transform_rates().

    Returns:
        A CheckResult named "missing_values"; failed_count is the number of
        rows with at least one null or blank value.
    """
    name = "missing_values"

    bad = df[REQUIRED_COLUMNS].isna().any(axis=1)  # None / NaN anywhere in the row
    for column in TEXT_COLUMNS:
        bad = bad | df[column].str.strip().eq("")  # "" or "   "

    failed = int(bad.sum())
    if failed == 0:
        return CheckResult(name, "pass")

    first_rows = ", ".join(str(i) for i in df.index[bad][:3])
    return CheckResult(name, "fail", failed, f"first bad row positions: {first_rows}")

KEY_COLUMNS = ["rate_date", "base_currency", "quote_currency"]


def check_duplicates(df: pd.DataFrame) -> CheckResult:
    """Check for repeated (rate_date, base_currency, quote_currency) keys.

    Args:
        df: DataFrame from transform_rates().

    Returns:
        A CheckResult named "duplicates"; failed_count is the number of extra
        rows (every occurrence of a key after the first one).
    """
    name = "duplicates"

    extra = df.duplicated(subset=KEY_COLUMNS, keep="first")

    failed = int(extra.sum())
    if failed == 0:
        return CheckResult(name, "pass")

    first_rows = ", ".join(str(i) for i in df.index[extra][:3])
    return CheckResult(name, "fail", failed, f"first duplicate row positions: {first_rows}")

def check_rate_positive(df: pd.DataFrame) -> CheckResult:
    """Check that every rate is greater than zero.

    Missing rates (NaN) are not counted here; check_missing_values covers them.

    Args:
        df: DataFrame from transform_rates().

    Returns:
        A CheckResult named "rate_positive"; failed_count is the number of
        rows with rate <= 0.
    """
    name = "rate_positive"

    bad = df["rate"] <= 0

    failed = int(bad.sum())
    if failed == 0:
        return CheckResult(name, "pass")

    first_rows = ", ".join(str(i) for i in df.index[bad][:3])
    return CheckResult(name, "fail", failed, f"first bad row positions: {first_rows}")

DEFAULT_MAX_DAILY_CHANGE = 0.05  # 5 %: starting point, tune it once we see real data


def check_daily_change(
    df: pd.DataFrame, max_change: float = DEFAULT_MAX_DAILY_CHANGE
) -> CheckResult:
    """Flag day-over-day rate changes larger than max_change (e.g. 0.05 = 5 %).

    Compares each row with the previous date of the same currency pair inside
    the batch. Rows with a missing or non-positive rate are ignored here.

    Args:
        df: DataFrame from transform_rates().
        max_change: Largest accepted absolute change as a fraction.

    Returns:
        A CheckResult named "daily_change"; failed_count is the number of
        rows whose change exceeds the threshold.
    """
    name = "daily_change"

    pair = ["base_currency", "quote_currency"]
    valid = df[df["rate"] > 0].sort_values(pair + ["rate_date"])
    previous = valid.groupby(pair)["rate"].shift(1)
    change = valid["rate"] / previous - 1  # first row of each pair is NaN

    flagged = change.abs() > max_change  # NaN compares as False

    failed = int(flagged.sum())
    if failed == 0:
        return CheckResult(name, "pass")

    examples = []
    for idx in valid.index[flagged][:3]:
        row = valid.loc[idx]
        examples.append(
            f"{row['rate_date']} {row['base_currency']}/{row['quote_currency']}: "
            f"{change[idx]:+.1%}"
        )
    return CheckResult(name, "fail", failed, "; ".join(examples))