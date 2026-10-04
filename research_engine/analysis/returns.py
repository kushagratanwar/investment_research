from datetime import date

from research_engine.analysis.requests import AnalysisRequest
from research_engine.analysis.results import AnalysisResult
from research_engine.db.repositories import get_observations


def simple_return(start_value, end_value):
    if start_value <= 0:
        raise ValueError("start_value must be greater than 0")
    return (end_value / start_value) - 1


def _period_observations(conn, request):
    observations = get_observations(
        conn,
        request.instrument_id,
        request.start_date,
        request.end_date,
    )
    if len(observations) < 2:
        raise ValueError("At least two observations are required")
    first, last = observations[0], observations[-1]
    return (
        first,
        last,
        date.fromisoformat(first["observation_date"]),
        date.fromisoformat(last["observation_date"]),
    )


def period_return(conn, request: AnalysisRequest) -> AnalysisResult:
    first, last, actual_start, actual_end = _period_observations(conn, request)
    return AnalysisResult(
        metric="period_return",
        value=simple_return(first["value"], last["value"]),
        start_date=request.start_date,
        end_date=request.end_date,
        actual_start_date=actual_start,
        actual_end_date=actual_end,
    )
