"""Tests for main.py: the whole pipeline with a fake API and a temporary database."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from fx_pipeline.main import main, run_pipeline

QUOTES = ["USD", "GBP"]


def record(quote: str, rate: float) -> dict[str, Any]:
    """One API record, like the raw JSON the Frankfurter API returns."""
    return {"date": "2026-10-30", "base": "EUR", "quote": quote, "rate": rate}


def scalar(engine: Engine, sql: str) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar_one()


def last_run(engine: Engine) -> dict[str, Any]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM core.pipeline_runs ORDER BY run_id DESC LIMIT 1")
        ).mappings().one()
    return dict(row)


@pytest.fixture
def pipeline_db(db_engine: Engine) -> Iterator[Engine]:
    """Point run_pipeline at the temporary database instead of the real one."""
    with patch("fx_pipeline.main.get_database_url", return_value=db_engine.url):
        yield db_engine


@pytest.mark.integration
def test_successful_run(pipeline_db: Engine) -> None:
    payload = [record("USD", 1.1), record("GBP", 0.83)]
    with patch("fx_pipeline.main.fetch_rates", return_value=payload):
        assert run_pipeline(quotes=QUOTES) is True

    run = last_run(pipeline_db)
    assert run["status"] == "success"
    assert (run["rows_fetched"], run["rows_loaded"], run["rows_rejected"]) == (2, 2, 0)
    assert scalar(pipeline_db, "SELECT count(*) FROM core.fx_rates") == 2
    assert scalar(pipeline_db, "SELECT count(*) FROM raw.fx_rates_raw") == 1
    # all eight checks are recorded (the old date makes the freshness check warn only)
    assert scalar(pipeline_db, "SELECT count(*) FROM core.data_quality_results") == 8


@pytest.mark.integration
def test_invalid_rows_are_rejected_but_the_run_succeeds(pipeline_db: Engine) -> None:
    payload = [record("USD", 1.1), record("GBP", -1.0)]  # a negative rate
    with patch("fx_pipeline.main.fetch_rates", return_value=payload):
        assert run_pipeline(quotes=QUOTES) is True

    run = last_run(pipeline_db)
    assert run["status"] == "success"
    assert (run["rows_fetched"], run["rows_loaded"], run["rows_rejected"]) == (2, 1, 1)
    assert scalar(pipeline_db, "SELECT count(*) FROM core.fx_rates") == 1


@pytest.mark.integration
def test_schema_failure_stops_the_run(pipeline_db: Engine) -> None:
    payload = {"status": 422, "message": "invalid currency: ABC"}  # not a list
    with patch("fx_pipeline.main.fetch_rates", return_value=payload):
        assert run_pipeline(quotes=QUOTES) is False

    run = last_run(pipeline_db)
    assert run["status"] == "failed"
    assert "schema" in run["error_message"]
    assert scalar(pipeline_db, "SELECT count(*) FROM core.fx_rates") == 0
    assert scalar(pipeline_db, "SELECT count(*) FROM raw.fx_rates_raw") == 1  # kept
    assert scalar(pipeline_db, "SELECT count(*) FROM core.data_quality_results") == 1


@pytest.mark.integration
def test_missing_currency_stops_the_run(pipeline_db: Engine) -> None:
    payload = [record("USD", 1.1)]  # GBP is missing
    with patch("fx_pipeline.main.fetch_rates", return_value=payload):
        assert run_pipeline(quotes=QUOTES) is False

    run = last_run(pipeline_db)
    assert run["status"] == "failed"
    assert "completeness" in run["error_message"]
    assert scalar(pipeline_db, "SELECT count(*) FROM core.fx_rates") == 0
    # the verdicts are still saved, so the failure can be investigated
    assert scalar(pipeline_db, "SELECT count(*) FROM core.data_quality_results") == 8


@pytest.mark.integration
def test_api_failure_is_recorded(pipeline_db: Engine) -> None:
    with patch("fx_pipeline.main.fetch_rates", side_effect=RuntimeError("API down")):
        assert run_pipeline(quotes=QUOTES) is False

    run = last_run(pipeline_db)
    assert run["status"] == "failed"
    assert run["error_message"] == "API down"
    assert run["rows_fetched"] == 0
    assert scalar(pipeline_db, "SELECT count(*) FROM core.fx_rates") == 0


def test_main_returns_zero_and_passes_the_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys, "argv", ["fx-pipeline", "--start", "2026-10-26", "--end", "2026-10-30"]
    )
    with patch("fx_pipeline.main.setup_logging"), patch(
        "fx_pipeline.main.run_pipeline", return_value=True
    ) as run:
        assert main() == 0
    run.assert_called_once_with(start_date="2026-10-26", end_date="2026-10-30")


def test_main_returns_one_when_the_run_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["fx-pipeline"])
    with patch("fx_pipeline.main.setup_logging"), patch(
        "fx_pipeline.main.run_pipeline", return_value=False
    ) as run:
        assert main() == 1
    run.assert_called_once_with(start_date=None, end_date=None)