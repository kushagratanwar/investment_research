# Investment Research Foundation

This project is a generic foundation for working with historical daily NAV/value data. The current implementation provides a small SQLite data store, conflict-safe ingestion of normalized observations, historical retrieval, basic single-series return calculations, and an in-memory portfolio specification. It does not yet calculate portfolio-level historical values or returns.

## Current components

- **SQLite** is the source of truth for accepted historical values. The schema contains `instruments`, `observations`, and `ingestion_runs`.
- **Ingestion** accepts normalized `(instrument_key, observation_date, value)` rows for one registered instrument. It records provenance and counts; new observations are inserted, repeats are counted, conflicts are recorded without overwriting, and invalid rows are not inserted.
- **Retrieval** returns stored observations in date order, optionally bounded by dates. It does not fill gaps or transform values.
- **Python analysis** provides simple returns, period returns, and ACT/365 CAGR for one series.
- **`PortfolioSpec`** represents `instrument_id -> weight` in memory and validates non-empty positive weights summing to 1. It does not construct a portfolio value or return series.

Use synthetic data during development. No provider-specific acquisition implementation is part of the current system; source acquisition and parsing are outside the SQLite loader.

## Scope principle

**Possible ≠ required.** Do not implement a capability merely because it is technically possible, reasonable, or potentially useful. Add functionality only when a concrete research need requires it.

Portfolio construction methodology, missing-date policy for portfolio calculations, advanced risk metrics, rolling analysis, attribution, benchmarks, saved portfolios, extensive instrument metadata, and provider-specific ingestion are not current capabilities or commitments. Their requirements remain open until explicitly defined.

See [architecture](docs/architecture.md), [data model](docs/data-model.md), and [design decisions](docs/design-decisions.md) for details.
