-- One row per pipeline execution: our "logbook"
CREATE TABLE IF NOT EXISTS core.pipeline_runs (
    run_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,                       -- empty until the run ends
    status         TEXT        NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'success', 'failed')),
    rows_fetched   INTEGER     NOT NULL DEFAULT 0,
    rows_loaded    INTEGER     NOT NULL DEFAULT 0,
    rows_rejected  INTEGER     NOT NULL DEFAULT 0,
    error_message  TEXT                                -- empty unless the run failed
);

-- One row per quality check per run
CREATE TABLE IF NOT EXISTS core.data_quality_results (
    result_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id        BIGINT      NOT NULL REFERENCES core.pipeline_runs (run_id),
    check_name    TEXT        NOT NULL,
    status        TEXT        NOT NULL CHECK (status IN ('pass', 'fail')),
    failed_count  INTEGER     NOT NULL DEFAULT 0,
    details       TEXT,
    checked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);