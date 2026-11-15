"""Pipeline entry point: fetch, validate, transform, load and log one run."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

from sqlalchemy import create_engine

from fx_pipeline.config import get_database_url
from fx_pipeline.extract import fetch_rates
from fx_pipeline.load import load_rates, load_raw
from fx_pipeline.logging_config import setup_logging
from fx_pipeline.quality_checks import (
    CheckResult,
    check_completeness,
    check_daily_change,
    check_duplicates,
    check_freshness,
    check_missing_values,
    check_rate_positive,
    check_row_count,
    check_schema,
    reject_invalid_rows,
)
from fx_pipeline.run_tracking import finish_run, save_check_results, start_run
from fx_pipeline.transform import transform_rates

logger = logging.getLogger("fx_pipeline.main")

DEFAULT_QUOTES = ["USD", "GBP", "CHF", "JPY", "INR"]


DEFAULT_WINDOW_DAYS = 14
MAX_WINDOW_DAYS = 730  # two years: the longest range we tested in one API request


def window_dates(days: int, today: date | None = None) -> tuple[str, str]:
    """Return (start, end) as "YYYY-MM-DD" for the last `days` days up to today."""
    today = today or date.today()
    return (today - timedelta(days=days)).isoformat(), today.isoformat()

def get_window_days(cli_days: int | None) -> int:
    """Window length: --days if given, else FX_WINDOW_DAYS, else the default.

    Raises:
        ValueError: if the number is not between 1 and MAX_WINDOW_DAYS.
    """
    if cli_days is not None:
        days = cli_days
    else:
        days = int(os.getenv("FX_WINDOW_DAYS", DEFAULT_WINDOW_DAYS))
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise ValueError(f"window must be between 1 and {MAX_WINDOW_DAYS} days, got {days}")
    return days

class PipelineStopped(Exception):
    """Raised when a stop-level quality check fails."""


def run_pipeline(
    start_date: str | None = None,
    end_date: str | None = None,
    quotes: list[str] | None = None,
) -> bool:
    """Run the whole pipeline once and record it in core.pipeline_runs.

    Args:
        start_date: First date of a range "YYYY-MM-DD" (None = latest rates).
        end_date: Last date of a range "YYYY-MM-DD".
        quotes: Currencies to fetch (default: DEFAULT_QUOTES).

    Returns:
        True if the run succeeded, False if it failed or was stopped.
    """
    quotes = quotes or DEFAULT_QUOTES
    engine = create_engine(get_database_url())
    run_id = start_run(engine)
    logger.info("run %s started", run_id)

    results: list[CheckResult] = []
    rows_fetched = rows_loaded = rows_rejected = 0
    try:
        # 1. Extract, and keep the untouched response first.
        raw = fetch_rates(quotes=quotes, start_date=start_date, end_date=end_date)
        load_raw(raw, engine)

        # 2. Schema check alone: if the structure is wrong, stop before the rest.
        schema = check_schema(raw)
        results.append(schema)
        if schema.status == "fail":
            raise PipelineStopped(f"schema check failed: {schema.details}")

        # 3. Transform, then run the remaining checks.
        df = transform_rates(raw)
        rows_fetched = len(df)
        logger.info("fetched %s rows", rows_fetched)

        stop_level = [
            check_completeness(df, quotes),
            check_row_count(df, min_rows=len(quotes)),
        ]
        row_level = [
            check_missing_values(df),
            check_duplicates(df),
            check_rate_positive(df),
        ]
        warn_level = [check_daily_change(df), check_freshness(df)]
        results.extend(stop_level + row_level + warn_level)

        # 4. Policy: stop the run.
        stopped = [r for r in stop_level if r.status == "fail"]
        if stopped:
            reasons = "; ".join(f"{r.check_name}: {r.details}" for r in stopped)
            raise PipelineStopped(reasons)

        # 5. Policy: warn and continue.
        for r in warn_level:
            if r.status == "fail":
                logger.warning("check %s failed: %s", r.check_name, r.details)

        # 6. Policy: reject rows, then load the rest.
        clean, rows_rejected = reject_invalid_rows(df)
        if rows_rejected:
            logger.warning("rejected %s invalid rows", rows_rejected)
        rows_loaded = load_rates(clean, engine)

        save_check_results(engine, run_id, results)
        finish_run(engine, run_id, "success", rows_fetched, rows_loaded, rows_rejected)
        logger.info(
            "run %s finished: fetched=%s loaded=%s rejected=%s",
            run_id, rows_fetched, rows_loaded, rows_rejected,
        )
        return True

    except Exception as exc:  # log every failure, then report it in the logbook
        logger.exception("run %s failed", run_id)
        save_check_results(engine, run_id, results)
        finish_run(
            engine, run_id, "failed", rows_fetched, rows_loaded, rows_rejected,
            error_message=str(exc)[:1000],
        )
        return False


def main() -> int:
    """Command-line entry point. Returns the process exit code (0 = success)."""
    parser = argparse.ArgumentParser(description="Run the FX rates pipeline.")
    parser.add_argument("--start", help="first date YYYY-MM-DD (use with --end)")
    parser.add_argument("--end", help="last date YYYY-MM-DD")
    parser.add_argument("--days", type=int, help="fetch the last N days")
    args = parser.parse_args()

    start_date, end_date = args.start, args.end
    if start_date is None and end_date is None:
        try:
            days = get_window_days(args.days)
        except ValueError as exc:
            parser.error(str(exc))
        start_date, end_date = window_dates(days)

    setup_logging()
    if args.start is None and args.end is None:
        logger.info("fetching the last %s days: %s to %s", days, start_date, end_date)

    ok = run_pipeline(start_date=start_date, end_date=end_date)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())