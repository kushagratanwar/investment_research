"""Acquisition and parsing for AMFI mutual-fund NAV text reports.

This module does not write to SQLite. Use the AMFI ingestion adapter after a
scheme has been resolved and explicitly confirmed.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from urllib.parse import urlencode
from urllib.request import Request, urlopen


AMFI_NAV_CATALOG_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
AMFI_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
# AMFI's NAV Download page documents a maximum historical period of 90 days.
AMFI_MAX_HISTORY_DAYS = 90


class AMFIFormatError(ValueError):
    """AMFI returned a row or report format this adapter cannot interpret."""


class SchemeIdentityError(ValueError):
    """A history report contains rows inconsistent with the confirmed scheme."""


@dataclass(frozen=True)
class AMFIScheme:
    scheme_code: str
    nav_name: str
    plan: str
    option: str
    isin_growth_or_payout: str
    isin_reinvestment: str

    @property
    def instrument_key(self):
        return f"amfi:scheme:{self.scheme_code}"


@dataclass(frozen=True)
class SchemeResolution:
    query: str
    candidates: tuple[AMFIScheme, ...]
    selected: "ConfirmedScheme | None"


@dataclass(frozen=True)
class ConfirmedScheme:
    """A scheme identity explicitly confirmed or uniquely resolved."""

    scheme: AMFIScheme

    @property
    def scheme_code(self):
        return self.scheme.scheme_code

    @property
    def instrument_key(self):
        return self.scheme.instrument_key


@dataclass(frozen=True)
class AMFINavRow:
    scheme: AMFIScheme
    observation_date: date | str
    value: float | str


def fetch_text(url):
    """Fetch an AMFI text report using the standard library HTTP client."""
    request = Request(url, headers={"User-Agent": "investment-research-engine/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig")


def parse_amfi_report(text):
    """Parse either the requested current header or AMFI's NAVAll header.

    The current history format is:
    Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;
    ISIN Div Reinvestment;Net Asset Value;Date

    AMFI's published complete NAV text report currently places its two ISIN
    fields before Scheme Name. Both formats carry the same eight data fields.
    Non-data grouping lines in the complete report are ignored.
    """
    if not isinstance(text, str):
        raise TypeError("AMFI report must be text")

    layout = None
    parsed = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        fields = [field.strip() for field in line.split(";")]
        lowered = [field.casefold() for field in fields]
        if len(fields) == 8 and lowered[0] == "scheme code":
            second = lowered[1]
            if "nav name" in second or "scheme name" in second:
                layout = "history"
            elif "isin" in second:
                layout = "catalog"
            else:
                raise AMFIFormatError("Unrecognized AMFI report header")
            continue

        if layout is None or len(fields) != 8:
            continue
        if not fields[0].isdigit():
            continue

        if layout == "history":
            code, name, plan, option, isin_a, isin_b, raw_value, raw_date = fields
        else:
            code, isin_a, isin_b, name, plan, option, raw_value, raw_date = fields
        try:
            observation_date = _parse_amfi_date(raw_date)
        except ValueError:
            # Keep malformed dates in normalized rows so ingest_observations
            # rejects and audits the row using the existing validation path.
            observation_date = raw_date
        try:
            value = parse_nav_value(raw_value)
        except AMFIFormatError:
            # As with dates, pass malformed/non-finite values to the existing
            # ingestion validator so they are counted in ingestion_runs.
            value = raw_value
        parsed.append(
            AMFINavRow(
                AMFIScheme(code, name, plan, option, _optional_isin(isin_a), _optional_isin(isin_b)),
                observation_date,
                value,
            )
        )
    if layout is None:
        raise AMFIFormatError("AMFI report header was not found")
    return parsed


def parse_nav_value(raw_value):
    """Parse a finite numeric NAV; zero/negative values follow ingestion rules."""
    try:
        value = float(raw_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise AMFIFormatError(f"Invalid AMFI NAV {raw_value!r}") from error
    if not math.isfinite(value):
        raise AMFIFormatError("AMFI NAV must be finite")
    return value


def parse_scheme_catalog(text):
    """Return scheme identities from an AMFI complete/latest NAV report."""
    return tuple(dict.fromkeys(row.scheme for row in parse_amfi_report(text)))


def resolve_scheme(query, schemes):
    """Find candidate identities; select only when the query yields one row."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    terms = query.casefold().split()
    candidates = tuple(
        scheme for scheme in schemes
        if all(term in _search_text(scheme) for term in terms)
    )
    selected = ConfirmedScheme(candidates[0]) if len(candidates) == 1 else None
    return SchemeResolution(query, candidates, selected)


def confirm_scheme(resolution, scheme_code):
    """Explicitly select one candidate by its AMFI Scheme Code."""
    if not isinstance(resolution, SchemeResolution):
        raise TypeError("resolution must be a SchemeResolution")
    matches = [s for s in resolution.candidates if s.scheme_code == str(scheme_code)]
    if len(matches) != 1:
        raise ValueError("scheme_code must identify exactly one displayed candidate")
    return ConfirmedScheme(matches[0])


def chunk_date_range(start_date, end_date, *, max_days=AMFI_MAX_HISTORY_DAYS):
    """Split an inclusive date interval into bounded inclusive chunks."""
    start_date, end_date = _as_date(start_date), _as_date(end_date)
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if not isinstance(max_days, int) or isinstance(max_days, bool) or max_days < 1:
        raise ValueError("max_days must be a positive integer")
    chunks = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=max_days - 1), end_date)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return tuple(chunks)


class AMFIClient:
    """Small injectable HTTP client for AMFI catalogue and history reports."""

    def __init__(self, text_fetcher=fetch_text):
        self._text_fetcher = text_fetcher

    def list_schemes(self):
        return parse_scheme_catalog(self._text_fetcher(AMFI_NAV_CATALOG_URL))

    def resolve(self, query):
        return resolve_scheme(query, self.list_schemes())

    def history(self, scheme, start_date, end_date):
        if not isinstance(scheme, ConfirmedScheme):
            raise TypeError("scheme must be uniquely resolved or explicitly confirmed")
        scheme = scheme.scheme
        result = []
        for chunk_start, chunk_end in chunk_date_range(start_date, end_date):
            query = urlencode({
                "frmdt": chunk_start.strftime("%d-%b-%Y"),
                "todt": chunk_end.strftime("%d-%b-%Y"),
            })
            report = parse_amfi_report(self._text_fetcher(f"{AMFI_HISTORY_URL}?{query}"))
            in_chunk = (
                row for row in report
                if not isinstance(row.observation_date, date)
                or chunk_start <= row.observation_date <= chunk_end
            )
            result.extend(validate_scheme_rows(in_chunk, scheme))
        return tuple(result)


def validate_scheme_rows(rows, confirmed_scheme):
    """Keep exact scheme-code rows and reject contradictory identity metadata."""
    accepted = []
    for row in rows:
        if row.scheme.scheme_code != confirmed_scheme.scheme_code:
            # Full AMFI history reports can include other schemes. They are
            # deliberately filtered and can never reach the ingestion API.
            continue
        _check_optional_identity(
            "ISIN Div Payout/ISIN Growth",
            confirmed_scheme.isin_growth_or_payout,
            row.scheme.isin_growth_or_payout,
            confirmed_scheme.scheme_code,
        )
        _check_optional_identity(
            "ISIN Div Reinvestment",
            confirmed_scheme.isin_reinvestment,
            row.scheme.isin_reinvestment,
            confirmed_scheme.scheme_code,
        )
        accepted.append(row)
    return tuple(accepted)


def _check_optional_identity(label, expected, actual, scheme_code):
    if expected and actual and expected != actual:
        raise SchemeIdentityError(
            f"AMFI history {label} does not match confirmed Scheme Code {scheme_code}"
        )


def _optional_isin(value):
    return "" if value.strip() in {"", "-"} else value.strip()


def _parse_amfi_date(value):
    day, month_text, year = value.split("-")
    month_names = (
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    )
    try:
        month = month_names.index(month_text.casefold()) + 1
        return date(int(year), month, int(day))
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid AMFI date {value!r}") from error


def _search_text(scheme):
    return " ".join((
        scheme.scheme_code, scheme.nav_name, scheme.plan, scheme.option,
        scheme.isin_growth_or_payout, scheme.isin_reinvestment,
    )).casefold()


def _as_date(value):
    if isinstance(value, datetime):
        raise ValueError("date must not include a time")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("date must use ISO YYYY-MM-DD format") from error
        if parsed.isoformat() == value:
            return parsed
    raise ValueError("date must use ISO YYYY-MM-DD format")
