"""Run tracking: the pipeline's logbook in core.pipeline_runs."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# started_at and status have defaults, so only the ticket number comes back.
START_SQL = text("INSERT INTO core.pipeline_runs DEFAULT VALUES RETURNING run_id")

FINISH_SQL = text(
    """
    UPDATE core.pipeline_runs
    SET finished_at   = now(),
        status        = :status,
        rows_fetched  = :rows_fetched,
        rows_loaded   = :rows_loaded,
        rows_rejected = :rows_rejected,
        error_message = :error_message
    WHERE run_id = :run_id
    """
)


def start_run(engine: Engine) -> int:
    """Insert a new run with status 'running' and return its run_id."""
    with engine.begin() as conn:
        return conn.execute(START_SQL).scalar_one()


def finish_run(
    engine: Engine,
    run_id: int,
    status: str,
    rows_fetched: int = 0,
    rows_loaded: int = 0,
    rows_rejected: int = 0,
    error_message: str | None = None,
) -> None:
    """Complete a run's logbook line.

    Args:
        engine: SQLAlchemy engine connected to the database.
        run_id: The ticket number returned by start_run().
        status: "success" or "failed" (the database refuses anything else).
        rows_fetched: Rows received from the API.
        rows_loaded: Rows written to core.fx_rates.
        rows_rejected: Rows removed by the quality checks.
        error_message: What went wrong, if the run failed.
    """
    with engine.begin() as conn:
        conn.execute(
            FINISH_SQL,
            {
                "run_id": run_id,
                "status": status,
                "rows_fetched": rows_fetched,
                "rows_loaded": rows_loaded,
                "rows_rejected": rows_rejected,
                "error_message": error_message,
            },
        )