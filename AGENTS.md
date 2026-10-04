# Guidance for contributors and coding agents

Read the current implementation and this documentation before changing the project. Treat the implementation as the source of truth for current behavior; update documentation only when a deliberate code change changes that behavior.

## Project boundary

- Preserve the minimal data foundation: SQLite `instruments`, `observations`, and `ingestion_runs`; normalized ingestion; historical retrieval; deterministic single-series calculations; and an in-memory `PortfolioSpec` validator.
- Keep generic instrument concepts generic. Do not add provider-specific assumptions or instrument-specific calculations.
- Use synthetic data during development. Do not introduce real funds, indices, ETFs, ISINs, or personal financial data.
- Store data because an analysis needs it, not because the data exists. Avoid static investment metadata unless a concrete current analysis requires it.
- **Possible ≠ required.** Technical feasibility or potential future usefulness is not a requirement. Add a capability only for a concrete research need.
- Do not choose portfolio construction or missing-date behavior without an explicit requirement. `PortfolioSpec` is validation-only; it does not imply a portfolio calculation method.
- Do not add portfolio lifecycle, rebalancing, advanced risk, rolling analysis, attribution, benchmark analysis, or provider-specific acquisition without an explicit requirement.

## Data and calculation boundaries

- SQLite is the source of truth for accepted historical numerical observations.
- Ingestion accepts normalized `(instrument_key, observation_date, value)` rows for one registered instrument. Keep acquisition, source-specific parsing, and database loading separate.
- Ordinary ingestion inserts new observations, counts identical repeats, and records conflicts without overwriting accepted values. It rejects nonnumeric and non-finite values, but accepts finite zero and negative values. Calculation functions have separate input requirements; do not conflate them with ingestion validation: `value_series_to_returns` rejects values at or below zero, `simple_return` requires a positive starting value, and CAGR requires positive endpoint values.
- Preserve source reference and input identity in ingestion records. A hash does not recreate the original artifact; retain the artifact externally when reproducibility requires it.
- Keep derived calculations deterministic and in Python. Do not persist derived metrics as source data.

When making an authorized change, keep it within the requested scope and update the relevant tests and documentation as requested.
