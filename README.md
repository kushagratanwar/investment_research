# Investment Research Foundation

This project is a generic foundation for working with historical daily NAV/value data. The current implementation provides a small SQLite data store, conflict-safe ingestion of normalized observations, historical retrieval, basic single-series return calculations, an in-memory portfolio specification, and a deterministic historical portfolio value calculation.

## Current components

- **SQLite** is the source of truth for accepted historical values. The schema contains `instruments`, `observations`, and `ingestion_runs`.
- **Ingestion** accepts normalized `(instrument_key, observation_date, value)` rows for one registered instrument. It records provenance and counts; new observations are inserted, repeats are counted, conflicts are recorded without overwriting, and invalid rows are not inserted.
- **Retrieval** returns stored observations in date order, optionally bounded by dates. It does not fill gaps or transform values.
- **Python analysis** provides simple returns, period returns, and ACT/365 CAGR for one series.
- **`PortfolioSpec`** represents `instrument_id -> weight` in memory and validates non-empty positive weights summing to 1. `portfolio_value_series` calculates normalized historical values for one portfolio using an initial lump-sum allocation, fixed component units, and dates observed for all constituents. It does not persist portfolios or derived values.

Use synthetic data during development. No provider-specific acquisition implementation is part of the current system; source acquisition and parsing are outside the SQLite loader.

## Scope principle

**Possible ≠ required.** Do not implement a capability merely because it is technically possible, reasonable, or potentially useful. Add functionality only when a concrete research need requires it.

The portfolio value calculation uses a one-time lump-sum investment at an explicit start date, with no subsequent contributions or rebalancing. Component units stay fixed and weights drift naturally. Every constituent must have a positive observation on the start date; later dates are included only when all constituents have observations. Values are not forward-filled or interpolated. Portfolio comparison, advanced risk metrics, rolling analysis, attribution, benchmarks, saved portfolios, extensive instrument metadata, and provider-specific ingestion are not current capabilities or commitments.

See [architecture](docs/architecture.md), [data model](docs/data-model.md), and [design decisions](docs/design-decisions.md) for details.
