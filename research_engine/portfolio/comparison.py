from dataclasses import dataclass
from datetime import date, datetime

from research_engine.analysis.performance import cagr
from research_engine.portfolio.models import PortfolioSpec
from research_engine.portfolio.series import portfolio_value_series


@dataclass(frozen=True)
class PortfolioComparisonResult:
    portfolio_a_series: dict[date, float]
    portfolio_b_series: dict[date, float]
    actual_start_date: date
    actual_end_date: date
    total_return_a: float
    total_return_b: float
    return_difference_percentage_points: float
    cagr_a: float
    cagr_b: float
    cagr_difference_percentage_points: float


def compare_portfolios(
    conn,
    portfolio_a: PortfolioSpec,
    portfolio_b: PortfolioSpec,
    start_date: date,
    end_date: date,
) -> PortfolioComparisonResult:
    """Compare two fixed-unit portfolio value series over a date interval.

    Returns are decimal fractions (for example, 0.05 means 5%). The return
    difference is expressed in percentage points.
    """
    if (
        isinstance(start_date, datetime)
        or not isinstance(start_date, date)
        or isinstance(end_date, datetime)
        or not isinstance(end_date, date)
    ):
        raise ValueError("start_date and end_date must be dates")
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    try:
        series_a = portfolio_value_series(conn, portfolio_a, start_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Portfolio A cannot be valued: {exc}") from exc
    try:
        series_b = portfolio_value_series(conn, portfolio_b, start_date)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Portfolio B cannot be valued: {exc}") from exc

    series_a = {
        observation_date: value
        for observation_date, value in series_a.items()
        if start_date <= observation_date <= end_date
    }
    series_b = {
        observation_date: value
        for observation_date, value in series_b.items()
        if start_date <= observation_date <= end_date
    }
    common_dates = sorted(set(series_a).intersection(series_b))
    if len(common_dates) < 2:
        raise ValueError(
            "At least two common observation dates within the requested "
            "comparison interval are required"
        )

    actual_start_date = common_dates[0]
    actual_end_date = common_dates[-1]
    start_value_a = series_a[actual_start_date]
    start_value_b = series_b[actual_start_date]
    aligned_a = {
        observation_date: series_a[observation_date] / start_value_a
        for observation_date in common_dates
    }
    aligned_b = {
        observation_date: series_b[observation_date] / start_value_b
        for observation_date in common_dates
    }
    # Keep the normalized base exact despite floating-point division.
    aligned_a[actual_start_date] = 1.0
    aligned_b[actual_start_date] = 1.0

    total_return_a = aligned_a[actual_end_date] - 1.0
    total_return_b = aligned_b[actual_end_date] - 1.0
    elapsed_days = (actual_end_date - actual_start_date).days
    years = elapsed_days / 365
    cagr_a = cagr(
        aligned_a[actual_start_date], aligned_a[actual_end_date], years
    )
    cagr_b = cagr(
        aligned_b[actual_start_date], aligned_b[actual_end_date], years
    )

    return PortfolioComparisonResult(
        portfolio_a_series=aligned_a,
        portfolio_b_series=aligned_b,
        actual_start_date=actual_start_date,
        actual_end_date=actual_end_date,
        total_return_a=total_return_a,
        total_return_b=total_return_b,
        return_difference_percentage_points=(
            total_return_a - total_return_b
        )
        * 100.0,
        cagr_a=cagr_a,
        cagr_b=cagr_b,
        cagr_difference_percentage_points=(cagr_a - cagr_b) * 100.0,
    )
