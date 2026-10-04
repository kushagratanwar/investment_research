# Guidance for contributors and coding agents

Read the current implementation and this documentation before changing the project. Treat the implementation as the source of truth for current behavior; update documentation only when a deliberate code change changes that behavior.

## Project boundary

- Preserve the minimal data foundation: SQLite `instruments`, `observations`, and `ingestion_runs`; normalized ingestion; historical retrieval; deterministic single-series calculations; in-memory `PortfolioSpec`; and the implemented portfolio value-series and two-portfolio comparison calculations.
- Keep instrument identity generic. AMFI NAV acquisition is the one explicitly supported provider workflow; do not hard-code provider-specific logic into the generic loader or add other providers without a concrete request.
- Use synthetic data for development fixtures and tests. Real AMFI NAV data may be imported only when the user explicitly requests a fund and date range and the exact scheme identity is resolved. Do not use personal portfolio data.
- Store data because an analysis needs it, not because the data exists. Avoid static investment metadata unless a concrete current analysis requires it.
- **Possible ≠ required.** Technical feasibility or potential future usefulness is not a requirement. Add a capability only for a concrete research need.
- Preserve the implemented portfolio methodology: one-time lump-sum allocation, normalized initial value 1.0, fixed units, and no contributions or rebalancing. Do not add another construction method without an explicit requirement.
- For the current calculations, every constituent must have a value on the requested start date; later dates require observations for all constituents, and comparisons use dates common to both portfolio series. Do not fill or interpolate missing values.
- Do not add portfolio persistence/lifecycle, rebalancing, advanced risk, rolling analysis, attribution, benchmark analysis, or providers beyond AMFI without an explicit requirement.

## Data and calculation boundaries

- SQLite is the source of truth for accepted historical numerical observations.
- Ingestion accepts normalized `(instrument_key, observation_date, value)` rows for one registered instrument. Keep acquisition, source-specific parsing, and database loading separate.
- Ordinary ingestion inserts new observations, counts identical repeats, and records conflicts without overwriting accepted values. It rejects nonnumeric and non-finite values, but accepts finite zero and negative values. Calculation functions have separate input requirements; do not conflate them with ingestion validation: `value_series_to_returns` rejects values at or below zero, `simple_return` requires a positive starting value, and CAGR requires positive endpoint values.
- Preserve source reference and input identity in ingestion records. A hash does not recreate the original artifact; retain the artifact externally when reproducibility requires it.
- Keep derived calculations deterministic and in Python. Do not persist derived metrics as source data.
- For user-requested AMFI imports, assume Direct Plan — Growth unless the user explicitly names another mutual-fund variant. Follow `.codex/skills/amfi-nav-import/SKILL.md`: resolve and display the AMFI Scheme Code and exact identity/date range, then wait for explicit user confirmation before fetching history, registering an instrument, or ingesting—even for a unique match. Use the verified official AMFI HTTPS history request with `curl`, chunk ranges to at most 90 calendar days, and pass normalized rows through the existing ingestion API. Never write observations directly.

When making an authorized change, keep it within the requested scope and update the relevant tests and documentation as requested.
