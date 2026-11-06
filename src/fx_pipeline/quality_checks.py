"""Data quality checks. Each check is a small function returning a CheckResult."""

from dataclasses import dataclass
from datetime import date
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


def check_completeness(df: pd.DataFrame, expected_currencies: list[str]) -> CheckResult:
    """Check that every expected quote currency is present for each date.

    Only dates that appear in the batch are checked; a date with no rows at
    all is not visible to this check.

    Args:
        df: DataFrame from transform_rates().
        expected_currencies: Quote currency codes that must exist for each date.

    Returns:
        A CheckResult named "completeness"; failed_count is the number of
        missing (date, currency) combinations.
    """
    name = "completeness"

    expected = set(expected_currencies)
    found_per_date = df.groupby("rate_date")["quote_currency"].agg(set)
    missing = found_per_date.apply(lambda found: expected - found)
    missing = missing[missing.map(len) > 0]  # keep only dates with a gap

    failed = int(missing.map(len).sum())
    if failed == 0:
        return CheckResult(name, "pass")

    examples = [
        f"{date}: missing {', '.join(sorted(codes))}"
        for date, codes in missing.head(3).items()
    ]
    return CheckResult(name, "fail", failed, "; ".join(examples))


DEFAULT_MAX_AGE_DAYS = 4  # covers a normal weekend; long holidays may warn


def check_freshness(
    df: pd.DataFrame,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    today: date | None = None,
) -> CheckResult:
    """Check that the latest rate_date is not older than max_age_days.

    Args:
        df: DataFrame from transform_rates().
        max_age_days: Largest accepted age of the newest date, in days.
        today: Reference date; defaults to the real date (set it in tests).

    Returns:
        A CheckResult named "freshness"; failed_count is 1 if the data is too
        old (or empty), otherwise 0.
    """
    name = "freshness"

    if df.empty:
        return CheckResult(name, "fail", 1, "no rows to check")

    today = today or date.today()
    latest = df["rate_date"].max()
    age = (today - latest).days

    if age <= max_age_days:
        return CheckResult(name, "pass")
    return CheckResult(
        name, "fail", 1, f"latest date {latest} is {age} days old (max {max_age_days})"
    )

def check_row_count(
    df: pd.DataFrame, min_rows: int, max_rows: int | None = None
) -> CheckResult:
    """Check that the number of rows is within the expected range.

    Args:
        df: DataFrame from transform_rates().
        min_rows: Smallest acceptable number of rows.
        max_rows: Largest acceptable number of rows (None = no upper limit).

    Returns:
        A CheckResult named "row_count"; failed_count is 1 if the count is
        out of range, otherwise 0.
    """
    name = "row_count"

    count = len(df)
    if count < min_rows:
        return CheckResult(name, "fail", 1, f"{count} rows, expected at least {min_rows}")
    if max_rows is not None and count > max_rows:
        return CheckResult(name, "fail", 1, f"{count} rows, expected at most {max_rows}")
    return CheckResult(name, "pass")