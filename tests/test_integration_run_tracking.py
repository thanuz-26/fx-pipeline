"""Integration tests for run_tracking.py against a temporary PostgreSQL database."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from fx_pipeline.quality_checks import CheckResult
from fx_pipeline.run_tracking import finish_run, save_check_results, start_run

pytestmark = pytest.mark.integration


def get_run(engine: Engine, run_id: int) -> dict[str, Any]:
    """Read one logbook row as a dictionary."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM core.pipeline_runs WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).mappings().one()
    return dict(row)


def test_start_run_creates_a_running_row(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    row = get_run(db_engine, run_id)
    assert isinstance(run_id, int)
    assert row["status"] == "running"
    assert row["finished_at"] is None
    assert row["rows_fetched"] == row["rows_loaded"] == row["rows_rejected"] == 0


def test_finish_run_records_success(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    finish_run(db_engine, run_id, "success", rows_fetched=10, rows_loaded=8, rows_rejected=2)
    row = get_run(db_engine, run_id)
    assert row["status"] == "success"
    assert (row["rows_fetched"], row["rows_loaded"], row["rows_rejected"]) == (10, 8, 2)
    assert row["finished_at"] is not None
    assert row["error_message"] is None


def test_finish_run_records_failure_with_message(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    finish_run(db_engine, run_id, "failed", error_message="API timeout")
    row = get_run(db_engine, run_id)
    assert row["status"] == "failed"
    assert row["error_message"] == "API timeout"
    assert row["finished_at"] is not None


def test_finish_run_refuses_an_unknown_status(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    with pytest.raises(IntegrityError):
        finish_run(db_engine, run_id, "sucess")  # misspelled on purpose


def test_save_check_results_stores_one_row_per_check(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    results = [
        CheckResult("schema", "pass"),
        CheckResult("row_count", "fail", 1, "2 rows, expected at least 3"),
    ]
    save_check_results(db_engine, run_id, results)
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT check_name, status, failed_count, details "
                "FROM core.data_quality_results WHERE run_id = :run_id ORDER BY result_id"
            ),
            {"run_id": run_id},
        ).all()
    assert [tuple(r) for r in rows] == [
        ("schema", "pass", 0, None),
        ("row_count", "fail", 1, "2 rows, expected at least 3"),
    ]


def test_save_check_results_needs_an_existing_run(db_engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        save_check_results(db_engine, 999, [CheckResult("schema", "pass")])


def test_save_check_results_with_no_results_does_nothing(db_engine: Engine) -> None:
    run_id = start_run(db_engine)
    save_check_results(db_engine, run_id, [])
    with db_engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM core.data_quality_results")).scalar_one()
    assert count == 0