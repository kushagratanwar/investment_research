import sqlite3
from datetime import date

import pytest

from research_engine.db.database import initialize_database
from research_engine.db.repositories import register_instrument
from research_engine.ingestion.pipeline import ingest_observations
from research_engine.portfolio import portfolio_value_series
from research_engine.portfolio.models import PortfolioSpec


def database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    return conn


def add_instrument(conn, key, values):
    instrument_id = register_instrument(conn, key)
    ingest_observations(
        conn,
        [(key, observation_date, value) for observation_date, value in values],
        source_reference=f"synthetic:{key}",
    )
    return instrument_id


def test_single_instrument_portfolio_value_series():
    conn = database()
    instrument_id = add_instrument(
        conn,
        "synthetic_single",
        [("2026-01-01", 100), ("2026-01-02", 110)],
    )

    result = portfolio_value_series(
        conn, PortfolioSpec({instrument_id: 1.0}), date(2026, 1, 1)
    )

    assert result == {
        date(2026, 1, 1): pytest.approx(1.0),
        date(2026, 1, 2): pytest.approx(1.1),
    }


def test_two_instrument_portfolio_uses_fixed_initial_weights():
    conn = database()
    instrument_a = add_instrument(
        conn,
        "synthetic_instrument_a",
        [
            ("2026-01-01", 100),
            ("2026-01-02", 110),
            ("2026-01-03", 120),
            ("2026-01-04", 100),
        ],
    )
    instrument_b = add_instrument(
        conn,
        "synthetic_instrument_b",
        [
            ("2026-01-01", 100),
            ("2026-01-02", 90),
            ("2026-01-03", 80),
            ("2026-01-04", 100),
        ],
    )

    result = portfolio_value_series(
        conn,
        PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4}),
        date(2026, 1, 1),
    )

    assert list(result.values()) == pytest.approx([1.00, 1.02, 1.04, 1.00])


def test_fixed_units_do_not_rebalance_to_initial_weights():
    conn = database()
    instrument_a = add_instrument(
        conn,
        "synthetic_instrument_a",
        [("2026-01-01", 100), ("2026-01-02", 110), ("2026-01-03", 120)],
    )
    instrument_b = add_instrument(
        conn,
        "synthetic_instrument_b",
        [("2026-01-01", 100), ("2026-01-02", 90), ("2026-01-03", 80)],
    )

    result = portfolio_value_series(
        conn,
        PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4}),
        date(2026, 1, 1),
    )

    # Fixed units are 0.006 A and 0.004 B, giving 1.04 on Jan 3.
    assert result[date(2026, 1, 3)] == pytest.approx(1.04)


def test_missing_post_start_observation_excludes_that_date_without_filling():
    conn = database()
    instrument_a = add_instrument(
        conn,
        "synthetic_instrument_a",
        [("2026-01-01", 100), ("2026-01-02", 110), ("2026-01-03", 120)],
    )
    instrument_b = add_instrument(
        conn,
        "synthetic_instrument_b",
        [("2026-01-01", 100), ("2026-01-03", 90)],
    )

    result = portfolio_value_series(
        conn,
        PortfolioSpec({instrument_a: 0.5, instrument_b: 0.5}),
        date(2026, 1, 1),
    )

    assert list(result) == [date(2026, 1, 1), date(2026, 1, 3)]
    assert result[date(2026, 1, 3)] == pytest.approx(1.05)


def test_missing_start_date_observation_is_rejected():
    conn = database()
    instrument_a = add_instrument(
        conn, "synthetic_instrument_a", [("2026-01-01", 100), ("2026-01-02", 110)]
    )
    instrument_b = add_instrument(
        conn, "synthetic_instrument_b", [("2026-01-02", 100), ("2026-01-03", 110)]
    )

    with pytest.raises(ValueError, match="no observation on start date"):
        portfolio_value_series(
            conn,
            PortfolioSpec({instrument_a: 0.5, instrument_b: 0.5}),
            date(2026, 1, 1),
        )


def test_arbitrary_number_of_instruments_is_supported():
    conn = database()
    holdings = {}
    for index, weight in enumerate((0.2, 0.3, 0.5), start=1):
        instrument_id = add_instrument(
            conn,
            f"synthetic_instrument_{index}",
            [("2026-01-01", 100), ("2026-01-02", 100 + index * 10)],
        )
        holdings[instrument_id] = weight

    result = portfolio_value_series(
        conn, PortfolioSpec(holdings), date(2026, 1, 1)
    )

    assert result[date(2026, 1, 2)] == pytest.approx(1.23)


@pytest.mark.parametrize("start_value", [0, -10])
def test_non_positive_start_value_is_rejected(start_value):
    conn = database()
    instrument_id = add_instrument(
        conn,
        "synthetic_instrument",
        [("2026-01-01", start_value), ("2026-01-02", 10)],
    )

    with pytest.raises(ValueError, match="positive value on start date"):
        portfolio_value_series(
            conn, PortfolioSpec({instrument_id: 1.0}), date(2026, 1, 1)
        )


def test_non_finite_historical_value_is_rejected():
    conn = database()
    instrument_id = add_instrument(
        conn,
        "synthetic_instrument",
        [("2026-01-01", 100), ("2026-01-02", 110)],
    )
    conn.execute(
        "UPDATE observations SET value = ? WHERE instrument_id = ? AND observation_date = ?",
        (float("inf"), instrument_id, "2026-01-02"),
    )

    with pytest.raises(ValueError, match="non-finite value"):
        portfolio_value_series(
            conn, PortfolioSpec({instrument_id: 1.0}), date(2026, 1, 1)
        )


def test_only_start_observations_is_insufficient_for_a_series():
    conn = database()
    instrument_id = add_instrument(
        conn, "synthetic_instrument", [("2026-01-01", 100)]
    )

    with pytest.raises(ValueError, match="At least two common observations"):
        portfolio_value_series(
            conn, PortfolioSpec({instrument_id: 1.0}), date(2026, 1, 1)
        )
