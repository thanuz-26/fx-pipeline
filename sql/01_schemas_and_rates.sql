-- Two schemas: raw = untouched API data, core = cleaned data for users
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;

-- RAW: store the full API response as-is
CREATE TABLE IF NOT EXISTS raw.fx_rates_raw (
    raw_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     TEXT        NOT NULL,
    payload    JSONB       NOT NULL,
    loaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- CORE: one clean row per date + base currency + quote currency
CREATE TABLE IF NOT EXISTS core.fx_rates (
    rate_date       DATE           NOT NULL,
    base_currency   CHAR(3)        NOT NULL,
    quote_currency  CHAR(3)        NOT NULL,
    rate            NUMERIC(18, 8) NOT NULL CHECK (rate > 0),
    source          TEXT           NOT NULL,
    loaded_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (rate_date, base_currency, quote_currency)
);