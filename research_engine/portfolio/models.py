from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class PortfolioSpec:
    holdings: Mapping[int, float]

    def __post_init__(self):
        if not self.holdings:
            raise ValueError("Portfolio must contain at least one holding")

        try:
            weights = [float(weight) for weight in self.holdings.values()]
        except (TypeError, ValueError):
            raise ValueError("Portfolio weights must be finite numbers") from None
        if any(not math.isfinite(weight) or weight <= 0 for weight in weights):
            raise ValueError("Each portfolio weight must be positive and finite")

        total = sum(weights)

        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Portfolio weights must sum to 1.0; got {total}"
            )
