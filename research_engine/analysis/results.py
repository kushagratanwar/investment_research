from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AnalysisResult:
    metric: str
    value: float
    start_date: date
    end_date: date
    actual_start_date: date
    actual_end_date: date
    day_count: str | None = None
