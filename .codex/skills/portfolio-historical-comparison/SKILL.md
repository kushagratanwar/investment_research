---
name: portfolio-historical-comparison
description: Compare two arbitrary portfolios using historical daily instrument values and the agreed lump-sum, fixed-units methodology.
---

# Portfolio Historical Comparison

Use this skill when asked to compare the historical performance of two portfolios. It is a repeatable research workflow, not portfolio management. Keep the analysis generic, use only data and capabilities authorized for the current request, and follow the project's “possible ≠ required” principle.

## Required inputs

Obtain or identify:

- Portfolio A and Portfolio B, each as an instrument-to-weight mapping. Either portfolio may contain any number of instruments.
- Historical daily values for each instrument over the requested comparison period, from the available database or user-provided normalized data.
- The comparison start and end dates, or enough context to establish them.

Use stable generic instrument identities. Do not add descriptive metadata. Use stored AMFI NAV data when the user requests analysis of an imported real mutual-fund scheme; do not fetch other real investment data or use real financial data in development fixtures or tests.

Users may provide stable database keys such as `amfi:scheme:<Scheme Code>`. Resolve each key to its internal `instrument_id` before constructing `PortfolioSpec`, which uses integer IDs; do not require users to memorize those IDs. If a key is unknown or maps to no stored observations, report that instead of substituting another instrument.

Validate that each portfolio is nonempty and its weights are finite, positive, and sum to 1. If weights, identities, dates, or required values are missing or invalid, explain what is missing and ask for it; do not guess, silently normalize weights, or substitute instruments.

## Standard methodology

Unless the user explicitly specifies a different method for this analysis:

1. Treat the comparison as a one-time lump-sum investment of initial capital 1.0 at the comparison start date.
2. Allocate the initial capital by the supplied weights. For an instrument with starting value `P_i(start)` and portfolio weight `w_i`, its initial units are `w_i / P_i(start)`.
3. Keep those units fixed throughout the period. There are no subsequent contributions and no rebalancing; portfolio weights may drift as instrument values change.
4. At each valid valuation date `t`, calculate portfolio value as `sum(units_i * P_i(t))`. The initial portfolio value is 1.0; cumulative return is the portfolio value relative to that initial value.

Apply this independently to A and B, then compare their dated values/returns over the agreed period. A clear, explicit methodology in the user’s request overrides this default for that analysis; state the override in the result.

## Standard comparison outputs

Normally report:

- Normalized historical value series for both portfolios.
- Total return for each portfolio and the difference in percentage points.
- CAGR for each portfolio and the CAGR difference in percentage points.

Calculate CAGR from each portfolio's values on the actual first and last common comparison dates, using elapsed calendar days and ACT/365:

`CAGR = (ending_value / starting_value) ** (365 / elapsed_days) - 1`

Do not assume a fixed number of years or substitute 365 days for the actual elapsed calendar days. If the aligned period has no positive elapsed time or the endpoint values do not meet the project's CAGR input requirements, report the issue rather than inventing a result. Add no other metrics unless requested.

## Historical data and dates

Use historical observations as stored or supplied. Preserve their dates and values; do not fabricate, interpolate, forward-fill, or silently drop observations. Retrieve or organize series chronologically and check that values needed for the calculation are valid.

The requested start date is the actual lump-sum investment date. Every constituent of both portfolios must have an observation on that date; if any is missing, fail explicitly and report the affected instruments. Do not advance to a later start date or substitute a value. After the start date, include only dates on which every constituent of each portfolio has an observation, then align both portfolio series on their common dates. Do not forward-fill or interpolate. Report any dates excluded from the direct comparison and the actual last common date used.

Do not infer that a requested period’s endpoints are actual observation dates. Report the actual dates used. Keep raw observations distinct from derived units, portfolio values, and returns; calculate derived values deterministically and do not persist them as source data.

## Reproducibility and reporting

Record in the response the portfolio mappings and weights, requested interval, actual aligned start and end dates, historical data source/reference, actual observations or date treatment used, and the formulas/methodology applied. Show enough intermediate results (initial units and dated portfolio values, as appropriate) to make the comparison traceable. Clearly call out missing data, assumptions explicitly authorized by the user, and limitations.

Report the direct comparison requested. Do not add advanced risk measures, attribution, benchmarks, recommendations, metadata, or other analyses unless the user asks for them. Do not modify application code, database schema, or persist portfolios as part of using this research workflow.
