# Architecture

## Current component boundaries

```text
normalized input rows
        ↓
ingestion validation, provenance, and conflict-safe loading
        ↓
SQLite: instruments, observations, ingestion_runs
        ↓
historical observation retrieval
        ├── deterministic single-series calculations
        └── PortfolioSpec + portfolio value series
            (one-time allocation, fixed component units)

PortfolioSpec (in-memory weights and validation)
```

### Database

SQLite stores the accepted historical values and ingestion records. The database schema is intentionally limited to three tables. Observations are keyed by instrument and date, and each accepted observation references the ingestion run that inserted it.

### Ingestion

The ingestion pipeline accepts normalized `(instrument_key, observation_date, value)` rows for one already registered instrument. It validates row shape, ISO dates, and finite numeric values; looks up the instrument rather than creating it implicitly; tracks inserts, duplicates, conflicts, and invalid rows; and records source reference and content identity with the run.

Source acquisition and provider-specific parsing are separate from this loader. The loader does not fetch data from an external provider.

### Retrieval and analysis

Repository retrieval selects stored values by instrument and optional date bounds, in chronological order. It does not fill missing dates or transform values. Python functions calculate simple value-to-value returns, period returns, and ACT/365 CAGR from retrieved observations.

### Portfolio representation

`PortfolioSpec` is an in-memory mapping from instrument IDs to weights. It validates that the mapping is nonempty, weights are positive, and their sum is 1 within tolerance. `portfolio_value_series` uses SQLite observations to calculate one portfolio's historical value series: initial capital is normalized to 1.0, allocated by the weights at an explicit start date, and converted to fixed component units. No later contributions or rebalancing occur, so weights drift naturally. The start date must be observed for every constituent; subsequent output dates include only dates observed for every constituent. No values are forward-filled or interpolated. Derived values remain in Python and are not persisted.

## Current boundary

The project can store and analyse individual historical value series and calculate a historical value series for one portfolio. It does not yet compare two portfolio series. No portfolio persistence or portfolio-management functionality is provided.
