from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AnalysisRequest:
    instrument_id: int
    start_date: date
    end_date: date

    def __post_init__(self):
        if self.instrument_id <= 0:
            raise ValueError("instrument_id must be greater than 0")
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
