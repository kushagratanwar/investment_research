from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import math

from research_engine.db.repositories import get_instrument_id


@dataclass(frozen=True)
class IngestionSummary:
    ingestion_run_id: int
    received: int
    inserted: int
    duplicate: int
    conflict: int
    invalid: int


def normalized_rows_hash(rows):
    """Return a stable SHA-256 identity for normalized rows."""
    encoded = json.dumps(
        list(rows), separators=(",", ":"), ensure_ascii=False, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ingest_observations(
    conn,
    rows,
    *,
    source_reference,
    content_hash=None,
):
    """Load normalized (instrument_key, date, value) rows for one instrument."""
    rows = list(rows)
    if not rows:
        raise ValueError("At least one normalized row is required")
    if not isinstance(source_reference, str) or not source_reference.strip():
        raise ValueError("source_reference must be a non-empty string")

    keys = {row[0] for row in rows if isinstance(row, (tuple, list)) and row}
    if len(keys) != 1:
        raise ValueError("An ingestion run must contain one instrument_key")
    instrument_key = next(iter(keys))
    if not isinstance(instrument_key, str) or not instrument_key.strip():
        raise ValueError("instrument_key must be a non-empty string")
    instrument_id = get_instrument_id(conn, instrument_key)
    if instrument_id is None:
        raise ValueError(f"Unknown instrument_key: {instrument_key}")

    if content_hash is None:
        content_hash = normalized_rows_hash(rows)
    if not isinstance(content_hash, str) or not content_hash.strip():
        raise ValueError("content_hash must be a non-empty string")

    cur = conn.execute(
        """INSERT INTO ingestion_runs
           (instrument_id, source_reference, content_hash, status, rows_received)
           VALUES (?, ?, ?, 'running', ?)""",
        (instrument_id, source_reference.strip(), content_hash, len(rows)),
    )
    run_id = cur.lastrowid
    inserted = duplicate = conflict = invalid = 0
    conflict_details = []
    invalid_details = []

    try:
        for index, row in enumerate(rows):
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                invalid += 1
                invalid_details.append({"row": index, "reason": "expected three fields"})
                continue
            row_key, raw_date, raw_value = row
            if row_key != instrument_key:
                invalid += 1
                invalid_details.append({"row": index, "reason": "instrument_key mismatch"})
                continue

            try:
                observation_date = _parse_date(raw_date)
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError("value must be finite")
            except (TypeError, ValueError, OverflowError) as error:
                invalid += 1
                invalid_details.append({"row": index, "reason": str(error)})
                continue

            date_text = observation_date.isoformat()
            existing = conn.execute(
                """SELECT value FROM observations
                   WHERE instrument_id = ? AND observation_date = ?""",
                (instrument_id, date_text),
            ).fetchone()
            if existing is not None:
                if float(existing["value"]) == value:
                    duplicate += 1
                else:
                    conflict += 1
                    conflict_details.append({
                        "date": date_text,
                        "accepted_value": float(existing["value"]),
                        "incoming_value": value,
                    })
                continue

            conn.execute(
                """INSERT INTO observations
                   (instrument_id, observation_date, value, ingestion_run_id)
                   VALUES (?, ?, ?, ?)""",
                (instrument_id, date_text, value, run_id),
            )
            inserted += 1

        status = "completed" if conflict == 0 and invalid == 0 else "completed_with_issues"
        details = {}
        if conflict_details:
            details["conflicts"] = conflict_details
        if invalid_details:
            details["invalid_rows"] = invalid_details
        conn.execute(
            """UPDATE ingestion_runs
               SET status = ?, rows_inserted = ?, rows_duplicate = ?,
                   rows_conflict = ?, rows_invalid = ?, error_summary = ?
               WHERE ingestion_run_id = ?""",
            (
                status, inserted, duplicate, conflict, invalid,
                json.dumps(details, separators=(",", ":")) if details else None,
                run_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return IngestionSummary(run_id, len(rows), inserted, duplicate, conflict, invalid)


def _parse_date(value):
    if isinstance(value, datetime):
        raise ValueError("date must not include a time")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("date must be an ISO YYYY-MM-DD string")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use ISO YYYY-MM-DD format")
    return parsed
