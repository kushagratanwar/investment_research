# Investment Research Foundation

This project is a generic foundation for working with historical daily NAV/value data. The current implementation provides a small SQLite data store, conflict-safe ingestion of normalized observations, historical retrieval, basic single-series return calculations, an in-memory portfolio specification, and deterministic portfolio value and comparison calculations.

## Current components

- **SQLite** is the source of truth for accepted historical values. The schema contains `instruments`, `observations`, and `ingestion_runs`.
- **Ingestion** accepts normalized `(instrument_key, observation_date, value)` rows for one registered instrument. It records provenance and counts; new observations are inserted, repeats are counted, conflicts are recorded without overwriting, and invalid rows are not inserted.
- **AMFI acquisition** parses AMFI scheme catalog/history reports, resolves scheme candidates, chunks history requests to AMFI's 90-day limit, and delegates database loading to the generic ingestion API. For mutual-fund requests without a specified variant, resolve **Direct Plan — Growth** by default. The reusable [AMFI NAV Import skill](.codex/skills/amfi-nav-import/SKILL.md) describes the tested operational path: display the AMFI Scheme Code and exact identity/date range, wait for the user's explicit confirmation even for a unique match, then fetch with verified official AMFI HTTPS `curl` requests, validate and normalize each response, ingest, and verify stored values.
- **Retrieval** returns stored observations in date order, optionally bounded by dates. It does not fill gaps or transform values.
- **Python analysis** provides simple returns, period returns, and ACT/365 CAGR for one series.
- **`PortfolioSpec`** represents `instrument_id -> weight` in memory and validates non-empty positive weights summing to 1. Users can identify stored instruments by stable `instrument_key`; callers resolve those keys to internal IDs before constructing a `PortfolioSpec`. `portfolio_value_series` calculates normalized historical values for one portfolio using an initial lump-sum allocation and fixed component units. `compare_portfolios` compares two such series over an explicit interval, aligns them on common dates, and returns total return and ACT/365 CAGR for both portfolios, plus each difference in percentage points. CAGR uses the actual aligned start and end dates. It does not persist portfolios or derived values.

Use synthetic data in development and tests. Real AMFI NAV data may be imported only when explicitly requested for a confirmed scheme and date range. AMFI acquisition and parsing are separate from the SQLite loader. Tests use synthetic/local mocked responses and do not make network requests.

## Scope principle

**Possible ≠ required.** Do not implement a capability merely because it is technically possible, reasonable, or potentially useful. Add functionality only when a concrete research need requires it.

The portfolio value calculation uses a one-time lump-sum investment at an explicit start date, with no subsequent contributions or rebalancing. Component units stay fixed and weights drift naturally. Every constituent must have a positive observation on the start date; later dates are included only when all constituents have observations. Values are not forward-filled or interpolated. Portfolio comparison uses an explicit start/end interval and dates common to both portfolio series. Advanced risk metrics, rolling analysis, attribution, benchmarks, saved portfolios, and extensive instrument metadata are not current capabilities or commitments.

See [architecture](docs/architecture.md), [data model](docs/data-model.md), and [design decisions](docs/design-decisions.md) for details.

## Reusable research workflows

- [AMFI NAV Import](.codex/skills/amfi-nav-import/SKILL.md): fetch and populate a confirmed mutual-fund scheme's historical NAV for a requested date range.
- [Portfolio Historical Comparison](.codex/skills/portfolio-historical-comparison/SKILL.md): compare two arbitrary weighted portfolios using stored historical values, total returns, and ACT/365 CAGR.

For an import, ask to “Use the AMFI NAV Import skill to add [fund] from [start date] through [end date].” Unless you specify another variant, the skill resolves Direct Plan — Growth and asks you to confirm the displayed AMFI Scheme Code and exact identity before fetching or importing. For a comparison, provide both instrument-to-weight mappings and the inclusive date interval. The comparison uses the fixed-unit lump-sum methodology documented in the skill.
