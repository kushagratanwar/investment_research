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
                ↓
            two-portfolio comparison (explicit interval, common dates)

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

### Portfolio comparison

`compare_portfolios` calculates each input portfolio with `portfolio_value_series`, restricts both results to the requested inclusive interval, and aligns them on common dates. It returns both aligned normalized series, actual comparison endpoints, total return and ACT/365 CAGR for each portfolio, and each difference in percentage points. CAGR uses calendar days between the actual aligned endpoints. It does not forward-fill or interpolate, and it does not persist portfolios or derived values.

## Current boundary

The project can calculate and compare historical value series for two portfolios. No portfolio persistence or portfolio-management functionality is provided.
