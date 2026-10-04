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

The AMFI acquisition module parses the official scheme catalogue, resolves unique candidates, supports explicit candidate selection, splits history ranges into inclusive chunks of at most 90 days, parses AMFI dates and values, filters to the selected Scheme Code, and checks available ISIN identity. Its injectable client uses Python's standard-library HTTP transport by default. The [AMFI NAV Import skill](../.codex/skills/amfi-nav-import/SKILL.md) documents the tested operational route using `curl` over HTTPS and the verified AMFI mutual-fund selector; this workflow requires explicit user confirmation of the displayed Scheme Code, identity, and date range before fetching history or writing to SQLite, including when the match is unique. It validates each requested chunk before sending normalized rows to the existing ingestion API. Both paths delegate observation writes and conflict handling to the generic loader; the AMFI adapter may register an instrument through the existing registration API.

The acquisition/parser code is in `research_engine/acquisition/amfi.py`; `research_engine/ingestion/amfi.py` provides an adapter that registers the stable `amfi:scheme:<Scheme Code>` key when needed and delegates normalized rows to `ingest_observations`. The generic loader itself remains provider-agnostic. Automated AMFI tests use mocked/local report text and do not contact AMFI.

### Retrieval and analysis

Repository retrieval selects stored values by instrument and optional date bounds, in chronological order. It does not fill missing dates or transform values. Python functions calculate simple value-to-value returns, period returns, and ACT/365 CAGR from retrieved observations.

### Portfolio representation

`PortfolioSpec` is an in-memory mapping from instrument IDs to weights. It validates that the mapping is nonempty, weights are positive, and their sum is 1 within tolerance. `portfolio_value_series` uses SQLite observations to calculate one portfolio's historical value series: initial capital is normalized to 1.0, allocated by the weights at an explicit start date, and converted to fixed component units. No later contributions or rebalancing occur, so weights drift naturally. The start date must be observed for every constituent; subsequent output dates include only dates observed for every constituent. No values are forward-filled or interpolated. Derived values remain in Python and are not persisted.

### Portfolio comparison

`compare_portfolios` calculates each input portfolio with `portfolio_value_series`, restricts both results to the requested inclusive interval, and aligns them on common dates. Each constituent of both portfolios must have a value on the requested start date; otherwise comparison fails rather than advancing the start. It returns both aligned normalized series, actual comparison endpoints, total return and ACT/365 CAGR for each portfolio, and each difference in percentage points. CAGR uses calendar days between the actual aligned endpoints. It does not forward-fill or interpolate, and it does not persist portfolios or derived values.

## Current boundary

The reusable [Portfolio Historical Comparison skill](../.codex/skills/portfolio-historical-comparison/SKILL.md) describes the same implemented methodology and outputs. The local SQLite file is ignored by Git; its currently loaded instruments and date coverage vary by environment and must be checked before an analysis. No portfolio persistence or portfolio-management functionality is provided.
