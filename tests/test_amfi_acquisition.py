from datetime import date
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

from research_engine.acquisition.amfi import (
    AMFIClient,
    AMFIFormatError,
    AMFINavRow,
    AMFIScheme,
    ConfirmedScheme,
    SchemeIdentityError,
    chunk_date_range,
    confirm_scheme,
    parse_amfi_report,
    parse_nav_value,
    parse_scheme_catalog,
    resolve_scheme,
    validate_scheme_rows,
)
from research_engine.db.database import initialize_database
from research_engine.db.repositories import get_instrument_id, get_observations
from research_engine.ingestion import amfi as amfi_ingestion
from research_engine.ingestion.amfi import populate_amfi_scheme


CURRENT_HEADER = (
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;"
    "ISIN Div Reinvestment;Net Asset Value;Date"
)


def current_report(*rows):
    return "\n".join([CURRENT_HEADER, *rows])


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_database(conn)
    return conn


@pytest.fixture
def scheme_report():
    return current_report(
        "1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA000001;;12.50;01-Jan-2026",
        "1002;Synthetic Blue Fund;Regular Plan;Growth Option;INFA000002;;11.50;01-Jan-2026",
        "1003;Synthetic Blue Fund;Direct Plan;IDCW Reinvestment;INFA000003;INFA000004;10.50;01-Jan-2026",
    )


def test_scheme_catalog_resolves_candidates_and_keeps_plan_option_isins(scheme_report):
    schemes = parse_scheme_catalog(scheme_report)
    result = resolve_scheme("synthetic blue fund growth", schemes)

    assert len(result.candidates) == 2
    assert result.selected is None
    assert {(s.scheme_code, s.plan, s.option, s.isin_growth_or_payout) for s in result.candidates} == {
        ("1001", "Direct Plan", "Growth Option", "INFA000001"),
        ("1002", "Regular Plan", "Growth Option", "INFA000002"),
    }
    assert confirm_scheme(result, "1001") == ConfirmedScheme(result.candidates[0])


def test_ambiguous_candidate_cannot_be_used_for_history_without_confirmation(scheme_report):
    client = AMFIClient(lambda _url: scheme_report)
    resolution = client.resolve("synthetic blue fund growth")
    with pytest.raises(TypeError, match="confirmed"):
        client.history(resolution.candidates[0], "2026-01-01", "2026-01-02")


def test_unique_scheme_match_can_be_selected(scheme_report):
    result = resolve_scheme("1003", parse_scheme_catalog(scheme_report))
    assert len(result.candidates) == 1
    assert result.selected.scheme_code == "1003"
    assert result.selected.scheme.isin_reinvestment == "INFA000004"


def test_amfi_catalog_format_is_parsed_for_scheme_resolution():
    report = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

1001;INFA000001;-;Synthetic Blue Fund;Direct Plan;Growth Option;12.50;01-Jan-2026
"""
    schemes = parse_scheme_catalog(report)
    assert schemes == (
        AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", ""),
    )


def test_current_history_format_converts_dates_and_numeric_nav():
    rows = parse_amfi_report(current_report(
        "1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA000001;;12.50;01-Jan-2026"
    ))
    assert rows[0].observation_date == date(2026, 1, 1)
    assert rows[0].value == 12.5


@pytest.mark.parametrize("raw_value", ["bad", "NaN", "Infinity"])
def test_invalid_nav_values_are_preserved_for_ingestion_rejection(raw_value):
    parsed = parse_amfi_report(current_report(
        f"1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA000001;;{raw_value};01-Jan-2026"
    ))
    assert parsed[0].value == raw_value
    with pytest.raises(AMFIFormatError, match="NAV"):
        parse_nav_value(raw_value)


def test_finite_zero_and_negative_nav_follow_existing_ingestion_validation():
    assert parse_nav_value("0") == 0
    assert parse_nav_value("-1") == -1


def test_invalid_amfi_date_is_preserved_for_ingestion_rejection():
    parsed = parse_amfi_report(current_report(
        "1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA000001;;12.5;31-Feb-2026"
    ))
    assert parsed[0].observation_date == "31-Feb-2026"


def test_date_range_chunking_uses_amfi_maximum_inclusive_days():
    assert chunk_date_range("2026-01-01", "2026-03-31") == (
        (date(2026, 1, 1), date(2026, 3, 31)),
    )
    assert chunk_date_range("2026-01-01", "2026-04-01") == (
        (date(2026, 1, 1), date(2026, 3, 31)),
        (date(2026, 4, 1), date(2026, 4, 1)),
    )


def test_history_requests_are_chunked_and_rows_are_filtered_to_confirmed_scheme():
    calls = []
    report = current_report(
        "1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA000001;;12.5;01-Jan-2026",
        "2000;Another Synthetic Fund;Direct Plan;Growth Option;INFA000099;;9.0;01-Jan-2026",
    )

    def fetch(url):
        calls.append(url)
        return report

    client = AMFIClient(fetch)
    confirmed = ConfirmedScheme(AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", ""))
    rows = client.history(confirmed, "2026-01-01", "2026-04-01")

    assert len(calls) == 2
    assert parse_qs(urlparse(calls[0]).query) == {"frmdt": ["01-Jan-2026"], "todt": ["31-Mar-2026"]}
    assert parse_qs(urlparse(calls[1]).query) == {"frmdt": ["01-Apr-2026"], "todt": ["01-Apr-2026"]}
    assert all(row.scheme.scheme_code == confirmed.scheme_code for row in rows)


def test_same_scheme_code_with_conflicting_isin_is_rejected():
    confirmed = AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", "")
    different_identity = parse_amfi_report(current_report(
        "1001;Synthetic Blue Fund;Direct Plan;Growth Option;INFA999999;;12.5;01-Jan-2026"
    ))
    with pytest.raises(SchemeIdentityError, match="ISIN"):
        validate_scheme_rows(different_identity, confirmed)


def test_population_normalizes_rows_and_calls_existing_ingestion_api(monkeypatch):
    conn = make_db()
    scheme = ConfirmedScheme(AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", ""))
    nav_rows = (
        AMFINavRow(scheme.scheme, date(2026, 1, 1), 12.5),
        AMFINavRow(scheme.scheme, date(2026, 1, 2), 12.75),
    )

    class StubClient:
        def history(self, selected, start, end):
            assert selected == scheme
            assert (start, end) == ("2026-01-01", "2026-01-02")
            return nav_rows

    captured = {}

    def ingest(conn_arg, rows, *, source_reference, content_hash=None):
        captured.update(conn=conn_arg, rows=list(rows), source_reference=source_reference)
        return "ingestion delegated"

    monkeypatch.setattr(amfi_ingestion, "ingest_observations", ingest)
    result = populate_amfi_scheme(conn, scheme, "2026-01-01", "2026-01-02", client=StubClient())

    assert result == "ingestion delegated"
    assert captured["conn"] is conn
    assert captured["rows"] == [
        ("amfi:scheme:1001", "2026-01-01", 12.5),
        ("amfi:scheme:1001", "2026-01-02", 12.75),
    ]
    assert "scheme_code=1001" in captured["source_reference"]
    assert get_instrument_id(conn, "amfi:scheme:1001") is not None


def test_population_requires_selected_or_confirmed_scheme():
    conn = make_db()
    candidate = AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", "")
    with pytest.raises(TypeError, match="confirmed"):
        populate_amfi_scheme(conn, candidate, "2026-01-01", "2026-01-02", client=object())


def test_repeat_and_conflict_semantics_remain_owned_by_existing_ingestion():
    conn = make_db()
    scheme = ConfirmedScheme(AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", ""))

    class StubClient:
        values = [12.5, 12.5, 13.0]

        def history(self, selected, start, end):
            return (AMFINavRow(selected.scheme, date(2026, 1, 1), self.values.pop(0)),)

    client = StubClient()
    first = populate_amfi_scheme(conn, scheme, "2026-01-01", "2026-01-01", client=client)
    duplicate = populate_amfi_scheme(conn, scheme, "2026-01-01", "2026-01-01", client=client)
    conflict = populate_amfi_scheme(conn, scheme, "2026-01-01", "2026-01-01", client=client)

    assert (first.inserted, first.duplicate, first.conflict) == (1, 0, 0)
    assert (duplicate.inserted, duplicate.duplicate, duplicate.conflict) == (0, 1, 0)
    assert (conflict.inserted, conflict.duplicate, conflict.conflict) == (0, 0, 1)
    instrument_id = get_instrument_id(conn, scheme.instrument_key)
    assert [row["value"] for row in get_observations(conn, instrument_id)] == [12.5]
    assert conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0] == 3


def test_invalid_amfi_values_reach_ingestion_and_are_audited_as_rejected():
    conn = make_db()
    scheme = ConfirmedScheme(AMFIScheme("1001", "Synthetic Blue Fund", "Direct Plan", "Growth Option", "INFA000001", ""))

    class StubClient:
        def history(self, selected, start, end):
            return (
                AMFINavRow(selected.scheme, "2026-01-01", "NaN"),
                AMFINavRow(selected.scheme, "31-Feb-2026", 12.5),
            )

    result = populate_amfi_scheme(conn, scheme, "2026-01-01", "2026-02-01", client=StubClient())
    assert (result.inserted, result.invalid) == (0, 2)
    assert get_observations(conn, get_instrument_id(conn, scheme.instrument_key)) == []
    run = conn.execute(
        "SELECT rows_invalid, status, error_summary FROM ingestion_runs"
    ).fetchone()
    assert run["rows_invalid"] == 2
    assert run["status"] == "completed_with_issues"
    assert "invalid_rows" in run["error_summary"]
