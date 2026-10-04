---
name: amfi-nav-import
description: Resolve an exact Indian mutual-fund scheme against AMFI and import its historical daily NAV into this project's SQLite database.
---

# AMFI NAV Import

Use this skill when the user asks to fetch, backfill, or update historical NAV data for an Indian mutual fund in this project. The workflow resolves the exact AMFI scheme, retrieves official AMFI history with `curl`, validates it, and loads normalized rows through the existing ingestion pipeline. It does not add application functionality or change the schema.

## Required request details

Obtain a fund description or an exact AMFI identity, plus an inclusive start and end date. Ask for missing dates. Interpret relative periods only when the intended dates are clear; state the exact dates before import.

## Resolve and confirm the scheme before loading

1. Resolve the request against AMFI's current scheme catalogue, using its official HTTPS text report (`https://portal.amfiindia.com/spages/NAVAll.txt`) and the project's AMFI parser when available.
2. Match the exact scheme identity, including Scheme Code, NAV Name, Plan, Option, and the available ISIN fields. Distinguish Direct from Regular and Growth from IDCW or reinvestment variants.
3. If the request supplies Scheme Code and ISIN, verify both against AMFI. Do not treat a scheme name alone as proof if multiple variants match.
4. Before writing to SQLite, state the resolved fund identity and requested dates. If the user supplied only a description/search string, ask them to confirm the exact candidate and wait. If multiple candidates remain, identity fields conflict, or the requested variant cannot be distinguished, show the candidates and wait for the user to select one. Never guess. A user-provided Scheme Code, ISIN, Plan, and Option that all match one AMFI catalogue entry are an explicit selection and do not need a second confirmation. A reference such as “the same fund” may reuse an exact scheme confirmed earlier in the conversation; restate its identity before loading.

## Fetch historical reports with curl

Use only AMFI's official history endpoint over HTTPS. The current endpoint returns semicolon-delimited text and accepts an inclusive date range of at most 90 calendar days per request. Split longer periods into consecutive inclusive chunks of at most 90 days, with the next chunk starting the day after the previous chunk ends.

The endpoint's `mf` parameter is AMFI's mutual-fund/AMC selector value, not the scheme code. Obtain that value from the current official AMFI NAV History selector and verify it corresponds to the resolved scheme's AMC. Do not hard-code a selector value or substitute the Scheme Code for it. If the selector cannot be verified, stop and ask for help rather than guessing.

For each chunk, make a read-only request like this, substituting the verified selector and dates:

```sh
curl --fail --silent --show-error --location --max-time 60 \
  --output '<unique-temp-response-file>' \
  'https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=<verified-selector>&frmdt=<DD-Mon-YYYY>&todt=<DD-Mon-YYYY>'
```

Quote the complete URL so shell-special `&` characters are not interpreted. Keep TLS certificate verification enabled; never use `curl -k`/`--insecure`. If the response is an HTTP error, empty, an error page, or not parseable as the expected AMFI report, stop and report the failed chunk. Do not estimate or substitute data.

Save each response artifact outside tracked source files when practical. A normalized-row hash identifies the ingested rows but cannot recreate the original AMFI response; retain the raw artifact externally when later reproduction requires it.

## Parse and validate each chunk

Parse AMFI's current history format:

```text
Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date
```

Use `research_engine.acquisition.amfi.parse_amfi_report` when available. Ignore non-data grouping lines, but require the report header and valid data rows. Check that the response corresponds to the requested chunk. Keep only rows whose Scheme Code exactly matches the confirmed scheme; verify every available ISIN, Plan, Option, and name field against that scheme. Stop on contradictory identity or out-of-chunk dates; do not silently accept another scheme or another period.

Normalize accepted data to `(instrument_key, observation_date, value)`, using `amfi:scheme:<Scheme Code>`, ISO `YYYY-MM-DD` dates, and the reported NAV. Do not fill weekends or holidays, interpolate, or invent observations. Let the existing ingestion validator classify invalid date/value rows; do not silently discard them.

## Load through the existing database pipeline

- Use the existing `ingest_observations` API, one instrument per run; never insert directly into `observations`.
- Register `amfi:scheme:<Scheme Code>` with the existing instrument-registration API only if it is not already registered. Do not add descriptive/static fund metadata.
- Use a distinct ingestion run per fetched chunk when practical. Put the official AMFI URL and requested chunk dates in `source_reference`; let the ingestion pipeline calculate the normalized-row SHA-256 when one is not supplied.
- Preserve the existing behavior: new date/value pairs are inserted, identical observations count as duplicates, conflicting values are recorded without overwriting accepted values, and invalid rows are rejected and audited.

## Verify and report

After ingestion, retrieve the requested interval through the historical observation repository API. Compare fetched and stored dates and values exactly, accounting for reported conflicts (the previously accepted database value must remain unchanged). Confirm there are no observations outside the requested interval. Report:

- the confirmed Scheme Code, NAV Name, Plan, Option, and available ISINs;
- the inclusive requested interval and each AMFI request chunk;
- per-chunk rows received, inserted, duplicate, conflict, and invalid counts, plus ingestion run IDs;
- exact date/value verification results, first and last available observation dates, and any dates for which AMFI returned no NAV;
- source references and whether raw response artifacts were retained.

If a run reports conflicts or invalid rows, describe them explicitly. Never claim that a chunk fully imported when its stored values have not been verified. Do not add portfolio calculations, recommendations, metadata, or other analysis to an import request.
