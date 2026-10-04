"""AMFI-to-SQLite population workflow using the canonical ingestion API."""

from datetime import date, datetime

from research_engine.acquisition.amfi import AMFIClient, ConfirmedScheme
from research_engine.db.repositories import get_instrument_id, register_instrument
from research_engine.ingestion.pipeline import ingest_observations


def populate_amfi_scheme(
    conn,
    scheme,
    start_date,
    end_date,
    *,
    client=None,
):
    """Fetch confirmed-scheme NAVs and submit normalized rows for ingestion.

    The stable instrument key is derived from the confirmed AMFI Scheme Code.
    SQLite writes and duplicate/conflict handling remain owned by
    ``ingest_observations``.
    """
    if not isinstance(scheme, ConfirmedScheme):
        raise TypeError("scheme must be uniquely resolved or explicitly confirmed from AMFI")
    client = client or AMFIClient()
    nav_rows = client.history(scheme, start_date, end_date)
    if not nav_rows:
        raise ValueError("AMFI returned no NAV observations for the confirmed scheme and range")

    instrument_key = scheme.instrument_key
    if get_instrument_id(conn, instrument_key) is None:
        register_instrument(conn, instrument_key)

    normalized = [
        (
            instrument_key,
            row.observation_date.isoformat()
            if isinstance(row.observation_date, date)
            else row.observation_date,
            row.value,
        )
        for row in nav_rows
    ]
    source_reference = (
        "AMFI NAV history;"
        f"scheme_code={scheme.scheme_code};"
        f"start={_date_text(start_date)};end={_date_text(end_date)};"
        "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
    )
    return ingest_observations(
        conn,
        normalized,
        source_reference=source_reference,
    )


def _date_text(value):
    if isinstance(value, datetime):
        raise ValueError("date must not include a time")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
