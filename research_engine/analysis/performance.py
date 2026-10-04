from research_engine.analysis.requests import AnalysisRequest
from research_engine.analysis.results import AnalysisResult
from research_engine.analysis.returns import _period_observations


def cagr(start_value, end_value, years):
    if start_value <= 0 or end_value <= 0 or years <= 0:
        raise ValueError("CAGR inputs must be positive and years must be > 0")
    return (end_value / start_value) ** (1 / years) - 1


def period_cagr(conn, request: AnalysisRequest) -> AnalysisResult:
    first, last, actual_start, actual_end = _period_observations(conn, request)
    years = (actual_end - actual_start).days / 365
    return AnalysisResult(
        metric="CAGR",
        value=cagr(first["value"], last["value"], years),
        start_date=request.start_date,
        end_date=request.end_date,
        actual_start_date=actual_start,
        actual_end_date=actual_end,
        day_count="ACT/365",
    )
