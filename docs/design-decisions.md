# Design decisions

## Current decisions

- **Minimal persistence:** SQLite contains only `instruments`, `observations`, and `ingestion_runs`.
- **Generic identity:** instruments use an internal ID and stable generic key; no static fund metadata is required by current analyses.
- **Normalized ingestion:** the database loader accepts `(instrument_key, observation_date, value)` rows for one registered instrument. Acquisition and provider-specific parsing are separate.
- **Conflict-safe history:** instrument/date is unique. Identical repeats are duplicates; a differing value is recorded as a conflict and never silently overwrites the accepted observation.
- **Input validation:** malformed rows, invalid ISO dates, and nonnumeric or non-finite values are not inserted and are counted in the run.
- **Provenance:** ingestion runs hold a source reference, content identity, status, and outcome counts/details. The default SHA-256 is over normalized rows. The database does not preserve the original artifact; retain it externally if reproducibility requires it.
- **Numerical source of truth:** SQLite holds accepted raw values. Python performs deterministic single-series calculations; derived metrics are not persisted.
- **Basic calculations:** simple value-to-value return, period return from the first and last stored observations within an inclusive requested range, and CAGR using ACT/365 elapsed time.
- **Portfolio input only:** `PortfolioSpec` is an in-memory `instrument_id -> weight` mapping. It validates nonempty, positive weights summing to 1; it does not calculate portfolio performance.
- **Synthetic development data:** no real instrument or personal portfolio data is part of the current scope.

## Explicitly unresolved or out of scope

No portfolio construction method has been selected. Buy-and-hold, daily or periodic rebalancing, and any other method are not implemented. Portfolio historical values and returns are not calculated. A portfolio missing-date policy is not defined.

Advanced risk metrics, rolling analysis, attribution, benchmark analysis, saved portfolio/version management, portfolio persistence, extensive instrument metadata, provider-specific ingestion, and real personal portfolio data are not current capabilities or commitments. They remain outside scope unless a concrete research need is explicitly identified.

## Scope principle

**Possible ≠ required.** Do not implement a capability merely because it is technically possible, reasonable, or potentially useful in the future. A capability should be added only when there is a concrete research need.
