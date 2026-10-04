from pathlib import Path
import sqlite3

DEFAULT_DB = Path("investment_research.db")


def connect(db_path=DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(conn):
    schema_path = Path(__file__).with_name("schema.sql")
    _migrate_legacy_schema(conn)
    _migrate_instrument_name(conn)
    conn.executescript(schema_path.read_text())
    conn.commit()


def _migrate_instrument_name(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "instruments" not in tables:
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(instruments)")
    }
    if "instrument_key" in columns and "instrument_name" not in columns:
        conn.execute("ALTER TABLE instruments ADD COLUMN instrument_name TEXT")
        conn.commit()


def _migrate_legacy_schema(conn):
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "instruments" not in tables:
        return
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(instruments)")
    }
    if "instrument_key" in columns:
        return

    # Preserve accepted observations and ingestion counts while removing the
    # superseded series/source/portfolio schema. Legacy input artifacts were
    # not retained, so their hashes are explicitly marked unavailable.
    instruments = conn.execute(
        "SELECT instrument_id, name FROM instruments ORDER BY instrument_id"
    ).fetchall()
    series_rows = conn.execute(
        "SELECT series_id, instrument_id, source_id, source_identifier FROM time_series"
    ).fetchall()
    series_by_id = {row["series_id"]: row for row in series_rows}
    source_names = {}
    if "data_sources" in tables:
        source_names = {
            row["source_id"]: row["name"]
            for row in conn.execute("SELECT source_id, name FROM data_sources")
        }
    old_runs = []
    if "ingestion_runs" in tables:
        old_runs = conn.execute("SELECT * FROM ingestion_runs ORDER BY ingestion_run_id").fetchall()
    observations = conn.execute(
        """SELECT series_id, observation_date, value, ingestion_run_id
           FROM observations ORDER BY series_id, observation_date"""
    ).fetchall()

    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        for table in (
            "portfolio_holdings", "portfolio_versions", "portfolios",
            "validation_results", "observations", "ingestion_runs",
            "time_series", "instruments", "data_sources",
        ):
            if table in tables:
                conn.execute(f'DROP TABLE "{table}"')

        schema = Path(__file__).with_name("schema.sql").read_text()
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement and not statement.upper().startswith("PRAGMA"):
                conn.execute(statement)

        for row in instruments:
            conn.execute(
                "INSERT INTO instruments(instrument_id, instrument_key) VALUES (?, ?)",
                (row["instrument_id"], row["name"]),
            )

        run_ids = set()
        for run in old_runs:
            series = series_by_id.get(run["series_id"])
            if series is None:
                continue
            source = source_names.get(series["source_id"], "legacy source unavailable")
            source_ref = source
            if series["source_identifier"]:
                source_ref += f":{series['source_identifier']}"
            conn.execute(
                """INSERT INTO ingestion_runs
                   (ingestion_run_id, instrument_id, ingested_at, source_reference,
                    content_hash, status, rows_received, rows_inserted,
                    rows_duplicate, rows_conflict, rows_invalid, error_summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run["ingestion_run_id"], series["instrument_id"],
                    run["started_at"], source_ref,
                    f"legacy-artifact-unavailable:{run['ingestion_run_id']}",
                    run["status"], run["rows_received"], run["rows_inserted"],
                    run["rows_duplicate"], run["rows_conflict"], run["rows_invalid"],
                    "Legacy database did not retain the original input artifact or content hash.",
                ),
            )
            run_ids.add(run["ingestion_run_id"])

        for obs in observations:
            series = series_by_id.get(obs["series_id"])
            if series is None:
                continue
            run_id = obs["ingestion_run_id"]
            if run_id not in run_ids:
                run_id = conn.execute(
                    """INSERT INTO ingestion_runs
                       (instrument_id, source_reference, content_hash, status,
                        rows_received, rows_inserted, error_summary)
                       VALUES (?, 'legacy database migration',
                               'legacy-artifact-unavailable', 'migrated', 1, 1,
                               'Original ingestion run was not linked to this observation.')""",
                    (series["instrument_id"],),
                ).lastrowid
                run_ids.add(run_id)
            conn.execute(
                """INSERT INTO observations
                   (instrument_id, observation_date, value, ingestion_run_id)
                   VALUES (?, ?, ?, ?)""",
                (series["instrument_id"], obs["observation_date"], obs["value"], run_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
