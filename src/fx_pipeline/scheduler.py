"""Scheduler: runs the pipeline once a day (default 17:00, Europe/Berlin)."""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from fx_pipeline.logging_config import setup_logging
from fx_pipeline.main import get_window_days, run_pipeline, window_dates

logger = logging.getLogger("fx_pipeline.scheduler")

# The ECB publishes its reference rates around 16:00 CET, so we run an hour later.
DEFAULT_HOUR = 17
DEFAULT_MINUTE = 0
DEFAULT_TIMEZONE = "Europe/Berlin"  # follows the ECB's clock, including summer time

JOB_ID = "daily_fx_run"


def build_trigger() -> CronTrigger:
    """Build the daily trigger from SCHEDULE_HOUR / _MINUTE / _TIMEZONE (or defaults)."""
    hour = int(os.getenv("SCHEDULE_HOUR", DEFAULT_HOUR))
    minute = int(os.getenv("SCHEDULE_MINUTE", DEFAULT_MINUTE))
    timezone = os.getenv("SCHEDULE_TIMEZONE", DEFAULT_TIMEZONE)
    return CronTrigger(hour=hour, minute=minute, timezone=timezone)


def run_scheduled_job() -> bool:
    """Run the pipeline once over the rolling window. Returns True on success."""
    start_date, end_date = window_dates(get_window_days(None))
    logger.info("scheduled run: fetching %s to %s", start_date, end_date)
    ok = run_pipeline(start_date=start_date, end_date=end_date)
    if not ok:
        logger.error("scheduled run failed; see core.pipeline_runs for the reason")
    return ok


def build_scheduler() -> BlockingScheduler:
    """Create a scheduler with the one daily job (not started yet)."""
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scheduled_job,
        build_trigger(),
        id=JOB_ID,
        coalesce=True,           # several missed runs -> run once
        max_instances=1,         # two runs never overlap
        misfire_grace_time=3600, # still run if we wake up within an hour of the time
    )
    return scheduler


def main() -> None:
    """Start the scheduler and keep running until the container stops."""
    setup_logging()
    scheduler = build_scheduler()
    logger.info("scheduler started, trigger: %s", build_trigger())
    try:
        scheduler.start()  # blocks
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler stopped")


if __name__ == "__main__":
    main()