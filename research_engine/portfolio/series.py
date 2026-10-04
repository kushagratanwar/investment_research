from datetime import date, datetime
import math

from research_engine.db.repositories import get_observations
from research_engine.portfolio.models import PortfolioSpec


def portfolio_value_series(
    conn,
    portfolio: PortfolioSpec,
    start_date: date,
) -> dict[date, float]:
    """Calculate normalized historical values using fixed initial units.

    The portfolio starts with value 1.0 on ``start_date``. Its weights define
    the initial allocation, after which component units remain fixed. Values
    are returned only for dates observed for every portfolio instrument.
    """
    if not isinstance(portfolio, PortfolioSpec):
        raise TypeError("portfolio must be a PortfolioSpec")
    if isinstance(start_date, datetime) or not isinstance(start_date, date):
        raise ValueError("start_date must be a date")
    if not portfolio.holdings:
        raise ValueError("Portfolio must contain at least one holding")

    weights = {}
    for instrument_id, weight in portfolio.holdings.items():
        if (
            not isinstance(instrument_id, int)
            or isinstance(instrument_id, bool)
            or instrument_id <= 0
        ):
            raise ValueError("Portfolio instrument IDs must be positive integers")
        try:
            numeric_weight = float(weight)
        except (TypeError, ValueError):
            raise ValueError("Portfolio weights must be positive finite numbers") from None
        if not math.isfinite(numeric_weight) or numeric_weight <= 0:
            raise ValueError("Portfolio weights must be positive finite numbers")
        weights[instrument_id] = numeric_weight

    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > 1e-9:
        raise ValueError(f"Portfolio weights must sum to 1.0; got {total_weight}")

    # PortfolioSpec permits tiny floating-point sum error. Correct only that
    # tolerance so the returned initial value is exactly normalized to 1.0.
    weights = {
        instrument_id: weight / total_weight
        for instrument_id, weight in weights.items()
    }

    histories = {}
    units = {}
    for instrument_id, weight in weights.items():
        rows = get_observations(conn, instrument_id, start_date=start_date)
        observations = {}
        for row in rows:
            observation_date = date.fromisoformat(row["observation_date"])
            try:
                value = float(row["value"])
            except (TypeError, ValueError):
                raise ValueError(
                    f"Instrument {instrument_id} has a nonnumeric value on "
                    f"{observation_date}"
                ) from None
            if not math.isfinite(value):
                raise ValueError(
                    f"Instrument {instrument_id} has a non-finite value on "
                    f"{observation_date}"
                )
            observations[observation_date] = value

        if start_date not in observations:
            raise ValueError(
                f"Instrument {instrument_id} has no observation on start date "
                f"{start_date}"
            )
        start_value = observations[start_date]
        if start_value <= 0:
            raise ValueError(
                f"Instrument {instrument_id} must have a positive value on "
                f"start date {start_date}"
            )

        histories[instrument_id] = observations
        initial_units = weight / start_value
        if not math.isfinite(initial_units):
            raise ValueError(
                f"Instrument {instrument_id} produces non-finite units on "
                f"start date {start_date}"
            )
        units[instrument_id] = initial_units

    common_dates = set.intersection(
        *(set(observations) for observations in histories.values())
    )
    eligible_dates = sorted(common_dates)
    if len(eligible_dates) < 2:
        raise ValueError(
            "At least two common observations, including the start date, "
            "are required to construct a portfolio value series"
        )

    result = {}
    for observation_date in eligible_dates:
        portfolio_value = sum(
            units[instrument_id] * histories[instrument_id][observation_date]
            for instrument_id in histories
        )
        if not math.isfinite(portfolio_value):
            raise ValueError(
                f"Portfolio value is non-finite on {observation_date}"
            )
        result[observation_date] = (
            1.0 if observation_date == start_date else portfolio_value
        )
    return result
