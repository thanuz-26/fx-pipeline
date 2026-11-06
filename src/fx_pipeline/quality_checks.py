"""Data quality checks. Each check is a small function returning a CheckResult."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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