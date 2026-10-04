from collections.abc import Sequence
from datetime import date


def value_series_to_returns(
    observations: Sequence,
) -> dict[date, float]:
    """
    Convert an ordered value series into simple period returns.

    The first observation has no return because there is no
    preceding observation.

    Each subsequent return is:

        current_value / previous_value - 1
    """

    if len(observations) < 2:
        raise ValueError("At least two observations are required")

    returns = {}

    previous_date = None
    previous_value = None

    for observation in observations:
        observation_date = date.fromisoformat(
            observation["observation_date"]
        )
        value = observation["value"]

        if value <= 0:
            raise ValueError("Observation values must be greater than 0")

        if previous_value is not None:
            returns[observation_date] = (
                value / previous_value
            ) - 1

        previous_date = observation_date
        previous_value = value

    return returns