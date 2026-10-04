PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    ingestion_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_reference TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    rows_received INTEGER NOT NULL DEFAULT 0,
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    rows_duplicate INTEGER NOT NULL DEFAULT 0,
    rows_conflict INTEGER NOT NULL DEFAULT 0,
    rows_invalid INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    instrument_id INTEGER NOT NULL REFERENCES instruments(instrument_id),
    observation_date TEXT NOT NULL,
    value REAL NOT NULL,
    ingestion_run_id INTEGER NOT NULL REFERENCES ingestion_runs(ingestion_run_id),
    PRIMARY KEY (instrument_id, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_observations_date
    ON observations(observation_date);
