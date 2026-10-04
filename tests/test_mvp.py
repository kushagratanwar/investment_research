import json
import sqlite3
from datetime import date

import pytest

from research_engine.analysis.performance import cagr, period_cagr
from research_engine.analysis.requests import AnalysisRequest
from research_engine.analysis.returns import period_return, simple_return
from research_engine.analysis.series import value_series_to_returns
from research_engine.db.database import initialize_database
from research_engine.db.repositories import (
    get_instrument_id,
    get_observations,
    register_instrument,
)
from research_engine.ingestion.pipeline import ingest_observations
from research_engine.portfolio.models import PortfolioSpec


def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    return conn


def test_database_initializes_only_foundation_tables():
    conn = db()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert tables == {"instruments", "observations", "ingestion_runs", "sqlite_sequence"}
    assert {row[1] for row in conn.execute("PRAGMA table_info(instruments)")} == {
        "instrument_id", "instrument_key", "instrument_name"
    }
    assert {row[1] for row in conn.execute("PRAGMA table_info(observations)")} == {
        "instrument_id", "observation_date", "value", "ingestion_run_id"
    }


def test_register_instrument_uses_stable_key():
    conn = db()
    instrument_id = register_instrument(conn, "synthetic_a")
    assert get_instrument_id(conn, "synthetic_a") == instrument_id
    with pytest.raises(sqlite3.IntegrityError):
        register_instrument(conn, "synthetic_a")


def test_register_instrument_requires_nonempty_key():
    with pytest.raises(ValueError):
        register_instrument(db(), "  ")


def test_observations_enforce_unique_instrument_and_date():
    conn = db()
    instrument_id = register_instrument(conn, "synthetic_a")
    run = ingest_observations(
        conn,
        [("synthetic_a", "2026-01-01", 100)],
        source_reference="synthetic.csv",
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?)",
            (instrument_id, "2026-01-01", 101, run.ingestion_run_id),
        )


def test_initial_ingestion_inserts_normalized_rows_and_tracks_run():
    conn = db()
    instrument_id = register_instrument(conn, "synthetic_a")
    rows = [
        ("synthetic_a", "2026-01-01", 100.0),
        ("synthetic_a", "2026-01-02", 101.0),
    ]
    result = ingest_observations(
        conn,
        rows,
        source_reference="archive/synthetic-a.csv",
        content_hash="sha256:abc123",
    )
    assert (result.received, result.inserted, result.duplicate, result.conflict, result.invalid) == (2, 2, 0, 0, 0)
    run = conn.execute(
        "SELECT * FROM ingestion_runs WHERE ingestion_run_id = ?",
        (result.ingestion_run_id,),
    ).fetchone()
    assert run["instrument_id"] == instrument_id
    assert run["source_reference"] == "archive/synthetic-a.csv"
    assert run["content_hash"] == "sha256:abc123"
    assert run["status"] == "completed"
    assert run["rows_received"] == 2
    assert run["rows_inserted"] == 2


def test_incremental_ingestion_counts_duplicates_and_inserts_new_dates():
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn,
        [("synthetic_a", "2026-01-01", 100), ("synthetic_a", "2026-01-02", 101)],
        source_reference="initial.csv",
    )
    result = ingest_observations(
        conn,
        [("synthetic_a", "2026-01-02", 101), ("synthetic_a", "2026-01-03", 102)],
        source_reference="update.csv",
    )
    assert (result.inserted, result.duplicate, result.conflict) == (1, 1, 0)
    assert [r["observation_date"] for r in get_observations(conn, 1)] == [
        "2026-01-01", "2026-01-02", "2026-01-03"
    ]


def test_conflicting_value_is_logged_and_accepted_value_is_preserved():
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn,
        [("synthetic_a", "2026-01-01", 100)],
        source_reference="initial.csv",
    )
    result = ingest_observations(
        conn,
        [("synthetic_a", "2026-01-01", 105)],
        source_reference="corrected.csv",
        content_hash="corrected-content",
    )
    assert (result.inserted, result.conflict) == (0, 1)
    assert get_observations(conn, 1)[0]["value"] == 100
    run = conn.execute(
        "SELECT status, rows_conflict, error_summary FROM ingestion_runs WHERE ingestion_run_id = ?",
        (result.ingestion_run_id,),
    ).fetchone()
    assert run["status"] == "completed_with_issues"
    assert run["rows_conflict"] == 1
    details = json.loads(run["error_summary"])
    assert details["conflicts"][0] == {
        "date": "2026-01-01", "accepted_value": 100.0, "incoming_value": 105.0
    }


def test_invalid_dates_and_values_are_counted_and_not_inserted():
    conn = db()
    register_instrument(conn, "synthetic_a")
    result = ingest_observations(
        conn,
        [
            ("synthetic_a", "2026-02-30", 1),
            ("synthetic_a", "2026-01-01", None),
            ("synthetic_a", "2026-01-02", float("nan")),
            ("synthetic_a", "2026-01-03", float("inf")),
            ("synthetic_a", "2026-01-04", "not a number"),
        ],
        source_reference="invalid.csv",
    )
    assert (result.received, result.inserted, result.invalid) == (5, 0, 5)
    assert get_observations(conn, 1) == []


def test_invalid_row_shape_is_counted():
    conn = db()
    register_instrument(conn, "synthetic_a")
    result = ingest_observations(
        conn,
        [("synthetic_a", "2026-01-01", 10), ("synthetic_a", "2026-01-02")],
        source_reference="malformed.csv",
    )
    assert (result.inserted, result.invalid) == (1, 1)


def test_ingestion_requires_known_single_instrument():
    conn = db()
    with pytest.raises(ValueError, match="Unknown instrument_key"):
        ingest_observations(
            conn, [("missing", "2026-01-01", 1)], source_reference="input.csv"
        )
    register_instrument(conn, "synthetic_a")
    with pytest.raises(ValueError, match="one instrument_key"):
        ingest_observations(
            conn,
            [("synthetic_a", "2026-01-01", 1), ("synthetic_b", "2026-01-01", 2)],
            source_reference="input.csv",
        )


def test_ingestion_requires_source_reference():
    conn = db()
    register_instrument(conn, "synthetic_a")
    with pytest.raises(ValueError, match="source_reference"):
        ingest_observations(conn, [("synthetic_a", "2026-01-01", 1)], source_reference=" ")


def test_retrieval_filters_and_orders_without_filling_dates():
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn,
        [("synthetic_a", "2026-01-03", 103), ("synthetic_a", "2026-01-01", 101)],
        source_reference="synthetic.csv",
    )
    assert [(r["observation_date"], r["value"]) for r in get_observations(conn, 1)] == [
        ("2026-01-01", 101), ("2026-01-03", 103)
    ]
    bounded = get_observations(conn, 1, date(2026, 1, 2), date(2026, 1, 4))
    assert [(r["observation_date"], r["value"]) for r in bounded] == [
        ("2026-01-03", 103)
    ]


def test_simple_return():
    assert simple_return(100, 110) == pytest.approx(0.10)
    with pytest.raises(ValueError):
        simple_return(0, 110)


def test_value_series_to_returns():
    result = value_series_to_returns([
        {"observation_date": "2026-01-01", "value": 100},
        {"observation_date": "2026-01-02", "value": 110},
        {"observation_date": "2026-01-04", "value": 121},
    ])
    assert result == {
        date(2026, 1, 2): pytest.approx(0.10),
        date(2026, 1, 4): pytest.approx(0.10),
    }


def test_period_return_uses_actual_observations_in_requested_range():
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn,
        [("synthetic_a", "2026-01-02", 100), ("synthetic_a", "2026-01-05", 110)],
        source_reference="synthetic.csv",
    )
    result = period_return(
        conn,
        AnalysisRequest(1, date(2026, 1, 1), date(2026, 1, 10)),
    )
    assert result.value == pytest.approx(0.10)
    assert result.actual_start_date == date(2026, 1, 2)
    assert result.actual_end_date == date(2026, 1, 5)


def test_period_return_requires_two_observations():
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn, [("synthetic_a", "2026-01-02", 100)], source_reference="synthetic.csv"
    )
    with pytest.raises(ValueError, match="two observations"):
        period_return(conn, AnalysisRequest(1, date(2026, 1, 1), date(2026, 1, 10)))


def test_cagr_uses_act_365():
    assert cagr(100, 121, 2) == pytest.approx(0.10)
    conn = db()
    register_instrument(conn, "synthetic_a")
    ingest_observations(
        conn,
        [("synthetic_a", "2024-01-01", 100), ("synthetic_a", "2026-01-01", 121)],
        source_reference="synthetic.csv",
    )
    result = period_cagr(
        conn,
        AnalysisRequest(1, date(2024, 1, 1), date(2026, 1, 1)),
    )
    assert result.value == pytest.approx(0.10, abs=0.0005)
    assert result.day_count == "ACT/365"


def test_analysis_request_rejects_bad_id_and_reversed_dates():
    with pytest.raises(ValueError):
        AnalysisRequest(0, date(2026, 1, 1), date(2026, 1, 2))
    with pytest.raises(ValueError):
        AnalysisRequest(1, date(2026, 1, 2), date(2026, 1, 1))


def test_portfolio_spec_supports_arbitrary_number_of_instruments():
    weights = {index: 1 / 12 for index in range(1, 13)}
    portfolio = PortfolioSpec(weights)
    assert len(portfolio.holdings) == 12


@pytest.mark.parametrize(
    "weights",
    [
        {},
        {1: 0.6, 2: 0.3},
        {1: 1.1, 2: -0.1},
        {1: float("nan")},
    ],
)
def test_portfolio_spec_rejects_invalid_weights(weights):
    with pytest.raises(ValueError):
        PortfolioSpec(weights)
