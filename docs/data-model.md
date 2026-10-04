# Data model and ingestion behavior

SQLite currently contains exactly three application tables.

## `instruments`

| Field | Purpose |
|---|---|
| `instrument_id` | Internal primary key used by observations and in-memory portfolio specifications. |
| `instrument_key` | Stable, generic, unique identity used to associate normalized input rows with a registered instrument. |
| `instrument_name` | Optional human-readable label. AMFI imports include the scheme name, plan, and option so the instrument is identifiable in database queries. It is descriptive, not an identity key. |

No additional descriptive investment metadata is stored.

## `observations`

| Field | Purpose |
|---|---|
| `instrument_id` | Foreign key to `instruments`. |
| `observation_date` | Date of the stored daily value. |
| `value` | Stored numeric NAV/value. |
| `ingestion_run_id` | Foreign key to the run that first inserted this accepted observation. |

The primary key is `(instrument_id, observation_date)`, preventing two accepted rows for the same instrument and date. There is no separate observation ID.

## `ingestion_runs`

| Field | Purpose |
|---|---|
| `ingestion_run_id` | Run primary key. |
| `instrument_id` | Foreign key to the instrument whose input is being loaded. |
| `ingested_at` | Timestamp recorded by SQLite when the run row is created. |
| `source_reference` | Required source/artifact description or reference. |
| `content_hash` | Required content identity. A normal ingestion run uses a supplied hash or calculates SHA-256 over normalized rows when none is supplied. The checked-in database also contains three legacy migrated runs with sentinel values such as `legacy-artifact-unavailable:1`, not actual content hashes; these indicate that the original hash and artifact were unavailable during migration. |
| `status` | `running`, `completed`, or `completed_with_issues` as set by the current pipeline. |
| `rows_received` | Number of supplied rows. |
| `rows_inserted` | Number of new observations inserted. |
| `rows_duplicate` | Number of identical existing observations encountered. |
| `rows_conflict` | Number of existing dates with a different incoming value. |
| `rows_invalid` | Number of rows rejected as invalid. |
| `error_summary` | Normal ingestion stores JSON text containing invalid-row details and/or accepted versus incoming values for conflicts, or null. Legacy migration may store a plain-text explanation; the three checked-in migrated runs use this form. |

## Relationships

```text
instruments 1 ─── many ingestion_runs
instruments 1 ─── many observations
ingestion_runs 1 ─── many observations
```

The schema also has an index on `observations.observation_date`.

## Normalized input and ingestion

Input rows have the form:

```text
instrument_key, observation_date, value
```

One ingestion call accepts rows for one registered instrument. The loader does not fetch or parse provider data and does not create unknown instruments; an unknown key raises an error before a run is created.

The AMFI adapter is separate from the loader. It resolves scheme candidates from AMFI's NAV report and uses `amfi:scheme:<Scheme Code>` as the stable instrument key when populating a selected scheme. It also records a human-readable instrument name containing the scheme name, plan, and option. The operational AMFI NAV Import skill requires the user to confirm the displayed Scheme Code, exact scheme identity, and requested date range before each import—even when the catalogue returns one match. Historical AMFI rows are normalized and submitted through the loader, which records provenance and applies the existing duplicate, conflict, and invalid-row behavior.

The AMFI NAV Import skill uses the official AMFI HTTPS history endpoint with `curl`, after confirming the exact scheme and the current AMFI mutual-fund selector. It requests inclusive chunks no longer than 90 calendar days and records each chunk's source URL through the existing ingestion pipeline. The `instrument_key` is the stable external-facing identity; it is looked up to an internal `instrument_id` for observations and in-memory portfolios. The local SQLite database is Git-ignored, so its current data coverage is not guaranteed in a fresh checkout.

- New instrument/date: insert and link the observation to the current run.
- Same date and same numeric value: count as duplicate; preserve the existing observation.
- Same date and different numeric value: count and detail as conflict; preserve the accepted value.
- Invalid row shape, non-ISO date, or non-finite/nonnumeric value: count and detail as invalid; do not insert.

`value_series_to_returns` converts an ordered sequence of observations into returns keyed by their dates. It requires the input sequence to be ordered and every value to be positive.

The same operation supports initial history and subsequent updates. The schema does not store the original input file. Keep that artifact externally if it must be available for later reproduction: a hash identifies content but cannot recreate it. The automatically generated hash identifies the normalized rows, not necessarily the original file bytes.

## Retrieval

`get_observations` selects one instrument’s stored date/value pairs, optionally bounded by inclusive start and end dates, ordered by date. Retrieval does not fill missing dates or transform values.
