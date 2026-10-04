import sqlite3
from datetime import date

import pytest

from research_engine.db.database import initialize_database
from research_engine.db.repositories import register_instrument
from research_engine.ingestion.pipeline import ingest_observations
from research_engine.portfolio import (
    PortfolioComparisonResult,
    compare_portfolios,
    portfolio_value_series,
)
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


def comparison_fixture():
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
    return conn, instrument_a, instrument_b


def test_identical_portfolios_have_identical_series_and_zero_difference():
    conn, instrument_a, instrument_b = comparison_fixture()
    portfolio = PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4})

    result = compare_portfolios(
        conn,
        portfolio,
        portfolio,
        date(2026, 1, 1),
        date(2026, 1, 4),
    )

    assert isinstance(result, PortfolioComparisonResult)
    assert result.portfolio_a_series == pytest.approx(result.portfolio_b_series)
    assert result.total_return_a == pytest.approx(0.0)
    assert result.total_return_b == pytest.approx(0.0)
    assert result.return_difference_percentage_points == pytest.approx(0.0)


def test_different_portfolios_return_expected_values_and_percentage_point_difference():
    conn, instrument_a, instrument_b = comparison_fixture()

    result = compare_portfolios(
        conn,
        PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4}),
        PortfolioSpec({instrument_a: 0.4, instrument_b: 0.6}),
        date(2026, 1, 1),
        date(2026, 1, 3),
    )

    assert list(result.portfolio_a_series.values()) == pytest.approx(
        [1.00, 1.02, 1.04]
    )
    assert list(result.portfolio_b_series.values()) == pytest.approx(
        [1.00, 0.98, 0.96]
    )
    assert result.total_return_a == pytest.approx(0.04)
    assert result.total_return_b == pytest.approx(-0.04)
    assert result.return_difference_percentage_points == pytest.approx(8.0)


def test_comparison_reuses_fixed_unit_portfolio_series():
    conn, instrument_a, instrument_b = comparison_fixture()
    portfolio = PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4})
    expected = portfolio_value_series(conn, portfolio, date(2026, 1, 1))

    result = compare_portfolios(
        conn,
        portfolio,
        PortfolioSpec({instrument_a: 0.4, instrument_b: 0.6}),
        date(2026, 1, 1),
        date(2026, 1, 4),
    )

    assert result.portfolio_a_series == pytest.approx(expected)


def test_explicit_interval_restricts_dates_and_normalizes_at_interval_start():
    conn, instrument_a, instrument_b = comparison_fixture()

    result = compare_portfolios(
        conn,
        PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4}),
        PortfolioSpec({instrument_a: 0.4, instrument_b: 0.6}),
        date(2026, 1, 2),
        date(2026, 1, 3),
    )

    assert list(result.portfolio_a_series) == [date(2026, 1, 2), date(2026, 1, 3)]
    assert result.portfolio_a_series[date(2026, 1, 2)] == 1.0
    assert result.portfolio_b_series[date(2026, 1, 2)] == 1.0
    assert result.actual_start_date == date(2026, 1, 2)
    assert result.actual_end_date == date(2026, 1, 3)
    assert result.total_return_a == pytest.approx(
        0.6 * (120 / 110) + 0.4 * (80 / 90) - 1
    )
    assert result.total_return_b == pytest.approx(
        0.4 * (120 / 110) + 0.6 * (80 / 90) - 1
    )


def test_portfolio_series_align_only_on_common_dates_without_filling():
    conn = database()
    instrument_a1 = add_instrument(
        conn,
        "synthetic_a1",
        [("2026-01-01", 100), ("2026-01-02", 110), ("2026-01-03", 120)],
    )
    instrument_a2 = add_instrument(
        conn,
        "synthetic_a2",
        [("2026-01-01", 100), ("2026-01-03", 100)],
    )
    instrument_b = add_instrument(
        conn,
        "synthetic_b",
        [("2026-01-01", 100), ("2026-01-02", 90), ("2026-01-03", 80)],
    )

    result = compare_portfolios(
        conn,
        PortfolioSpec({instrument_a1: 0.5, instrument_a2: 0.5}),
        PortfolioSpec({instrument_b: 1.0}),
        date(2026, 1, 1),
        date(2026, 1, 3),
    )

    assert list(result.portfolio_a_series) == [date(2026, 1, 1), date(2026, 1, 3)]
    assert list(result.portfolio_a_series) == list(result.portfolio_b_series)
    assert result.portfolio_a_series[date(2026, 1, 3)] == pytest.approx(1.1)
    assert result.portfolio_b_series[date(2026, 1, 3)] == pytest.approx(0.8)


def test_missing_start_observation_is_reported_with_portfolio_identity():
    conn = database()
    instrument_a = add_instrument(
        conn,
        "synthetic_a",
        [("2026-01-01", 100), ("2026-01-02", 110), ("2026-01-03", 120)],
    )
    instrument_b = add_instrument(
        conn,
        "synthetic_b",
        [("2026-01-02", 100), ("2026-01-03", 110)],
    )

    with pytest.raises(ValueError, match="Portfolio B cannot be valued.*start date"):
        compare_portfolios(
            conn,
            PortfolioSpec({instrument_a: 1.0}),
            PortfolioSpec({instrument_b: 1.0}),
            date(2026, 1, 1),
            date(2026, 1, 3),
        )


def test_insufficient_common_dates_in_interval_fail_explicitly():
    conn, instrument_a, instrument_b = comparison_fixture()

    with pytest.raises(ValueError, match="At least two common observation dates"):
        compare_portfolios(
            conn,
            PortfolioSpec({instrument_a: 0.6, instrument_b: 0.4}),
            PortfolioSpec({instrument_a: 0.4, instrument_b: 0.6}),
            date(2026, 1, 1),
            date(2026, 1, 1),
        )


def test_arbitrary_instrument_counts_work_for_both_portfolios():
    conn = database()
    portfolio_a = {}
    portfolio_b = {}
    for index, weight in enumerate((0.2, 0.3, 0.5), start=1):
        instrument_id = add_instrument(
            conn,
            f"synthetic_a{index}",
            [("2026-01-01", 100), ("2026-01-02", 100 + 10 * index)],
        )
        portfolio_a[instrument_id] = weight
    for index, weight in enumerate((0.25, 0.25, 0.25, 0.25), start=1):
        instrument_id = add_instrument(
            conn,
            f"synthetic_b{index}",
            [("2026-01-01", 100), ("2026-01-02", 100 - 5 * index)],
        )
        portfolio_b[instrument_id] = weight

    result = compare_portfolios(
        conn,
        PortfolioSpec(portfolio_a),
        PortfolioSpec(portfolio_b),
        date(2026, 1, 1),
        date(2026, 1, 2),
    )

    assert result.portfolio_a_series[date(2026, 1, 2)] == pytest.approx(1.23)
    assert result.portfolio_b_series[date(2026, 1, 2)] == pytest.approx(0.875)
