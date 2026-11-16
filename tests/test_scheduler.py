"""Tests for scheduler.py: the schedule is checked with fixed times, never by waiting."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from fx_pipeline.scheduler import (
    JOB_ID,
    build_scheduler,
    build_trigger,
    run_scheduled_job,
)

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture(autouse=True)
def default_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SCHEDULE_HOUR", "SCHEDULE_MINUTE", "SCHEDULE_TIMEZONE"):
        monkeypatch.delenv(name, raising=False)


def test_next_run_is_today_at_17_when_asked_at_noon() -> None:
    now = datetime(2026, 11, 16, 12, 0, tzinfo=BERLIN)
    nxt = build_trigger().get_next_fire_time(None, now)
    assert (nxt.year, nxt.month, nxt.day, nxt.hour, nxt.minute) == (2026, 11, 16, 17, 0)


def test_next_run_is_tomorrow_when_asked_after_17() -> None:
    now = datetime(2026, 11, 16, 18, 0, tzinfo=BERLIN)
    nxt = build_trigger().get_next_fire_time(None, now)
    assert (nxt.month, nxt.day, nxt.hour) == (11, 17, 17)


def test_run_time_follows_summer_and_winter_time() -> None:
    winter = build_trigger().get_next_fire_time(
        None, datetime(2026, 11, 16, 12, 0, tzinfo=BERLIN)
    )
    summer = build_trigger().get_next_fire_time(
        None, datetime(2026, 7, 16, 12, 0, tzinfo=BERLIN)
    )
    assert winter.astimezone(UTC).hour == 16  # 17:00 CET = 16:00 UTC
    assert summer.astimezone(UTC).hour == 15  # 17:00 CEST = 15:00 UTC


def test_schedule_can_be_changed_by_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCHEDULE_HOUR", "6")
    monkeypatch.setenv("SCHEDULE_MINUTE", "30")
    now = datetime(2026, 11, 16, 5, 0, tzinfo=BERLIN)
    nxt = build_trigger().get_next_fire_time(None, now)
    assert (nxt.hour, nxt.minute) == (6, 30)


def test_scheduled_job_runs_the_pipeline_over_the_window() -> None:
    with (
        patch(
            "fx_pipeline.scheduler.window_dates",
            return_value=("2026-11-02", "2026-11-16"),
        ),
        patch("fx_pipeline.scheduler.run_pipeline", return_value=True) as run,
    ):
        assert run_scheduled_job() is True
    run.assert_called_once_with(start_date="2026-11-02", end_date="2026-11-16")


def test_scheduler_has_exactly_one_daily_job() -> None:
    jobs = build_scheduler().get_jobs()
    assert [job.id for job in jobs] == [JOB_ID]
