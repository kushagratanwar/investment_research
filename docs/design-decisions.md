# Design decisions

## Current decisions

- **Minimal persistence:** SQLite contains only `instruments`, `observations`, and `ingestion_runs`.
- **Instrument labels:** instruments use an internal ID and stable generic key, with an optional human-readable `instrument_name`. AMFI fund labels include the scheme name, plan, and option so stored instruments can be identified. Other static fund metadata remains out of scope.
- **Normalized ingestion:** the database loader accepts `(instrument_key, observation_date, value)` rows for one registered instrument. Acquisition and provider-specific parsing are separate.
- **Conflict-safe history:** instrument/date is unique. Identical repeats are duplicates; a differing value is recorded as a conflict and never silently overwrites the accepted observation.
- **Input validation:** malformed rows, invalid ISO dates, and nonnumeric or non-finite values are not inserted and are counted in the run.
- **Provenance:** ingestion runs hold a source reference, content identity, status, and outcome counts/details. The default SHA-256 is over normalized rows. The database does not preserve the original artifact; retain it externally if reproducibility requires it.
- **Numerical source of truth:** SQLite holds accepted raw values. Python performs deterministic single-series calculations; derived metrics are not persisted.
- **Basic calculations:** simple value-to-value return, period return from the first and last stored observations within an inclusive requested range, and CAGR using ACT/365 elapsed time.
- **AMFI acquisition:** AMFI is the one explicitly supported provider-specific source. Mutual-fund requests default to Direct Plan — Growth unless the user explicitly asks for another variant. Before each import, the user must explicitly confirm the displayed AMFI Scheme Code, exact identity, and date range, including when the match is unique. The reusable AMFI NAV Import skill uses official HTTPS `curl` requests in chunks of at most 90 days, validates scheme identity, and submits normalized rows through the existing conflict-safe ingestion API. It does not add schema or provider-specific fields.
- **Portfolio value methodology:** `PortfolioSpec` remains an in-memory `instrument_id -> weight` mapping. For a single portfolio, `portfolio_value_series` models an initial lump-sum investment normalized to 1.0 on an explicit start date. Weights set the initial allocation; component units remain fixed, with no subsequent contributions or rebalancing, so weights drift naturally. Every constituent must have a positive start-date observation. Later output dates are limited to dates with observations for every constituent; no forward filling or interpolation occurs.
- **Portfolio comparison:** `compare_portfolios` accepts two `PortfolioSpec` values and an explicit inclusive start/end interval. Every constituent must have an observation on the requested start date or comparison fails; it does not advance the start. It restricts the normalized portfolio value series to the interval, aligns on dates common to both, and returns each total return and ACT/365 CAGR, plus each difference in percentage points. CAGR uses the actual aligned endpoints and elapsed calendar days. It does not fill or interpolate missing dates.
- **Data-use boundary:** synthetic data is used in development fixtures and tests. Real AMFI NAV data may be imported only on an explicit user request for a confirmed scheme and date range. Personal portfolio data is outside scope.

## Explicitly unresolved or out of scope

Portfolio persistence, lifecycle, rebalancing, subsequent contributions or withdrawals, advanced risk metrics, rolling analysis, attribution, benchmark analysis, extensive instrument metadata, additional provider-specific adapters beyond AMFI, and real personal portfolio data are not current capabilities or commitments. They remain outside scope unless a concrete research need is explicitly identified.

## Scope principle

**Possible ≠ required.** Do not implement a capability merely because it is technically possible, reasonable, or potentially useful in the future. A capability should be added only when there is a concrete research need.
