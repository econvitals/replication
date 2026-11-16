"""Where this copy of the engine gets its data: free public sources, nothing else.

Econvitals' own copy of the engine reads each agency through its in-house data library. The engine's
code names those readers `bea`, `fred`, `bls_client` and `atlfed`; in this copy each name is one of
the small readers below, which fetch the same numbers from the same public sources:

    bea          BEA's API (NIPA tables), the same DataValue BEA serves; needs BEA_API_KEY
    fred         FRED; needs FRED_API_KEY
    bls_client   the BLS series the engine reads, from FRED, which republishes BLS's numbers unchanged
                 (BLS_ON_FRED gives each twin); needs FRED_API_KEY
    atlfed       the Atlanta Fed's GDPNow workbook: BEA's advance estimates and their release dates

The Census Bureau's APIs (EITS, international trade) and FRED's release calendars and archive
(ALFRED) are read by the engine's own code, unchanged. `census_direct`, `census_ftd` and
`providers` serve sources that Econvitals' tracking of BEA's later estimates of a quarter reads,
not this estimate; they say so if called.

Downloads go through the repository's common/econdata.py: a contact User-Agent, polite retries,
BEA's download pacing, and a cache of a few hours.
"""
from __future__ import annotations

import datetime as dt
import io
import sys
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))     # the repository root, for common/
from common import econdata  # noqa: E402

Obs = namedtuple("Obs", "d v")
Series = namedtuple("Series", "id obs")

#: BLS series id -> the FRED series that republishes it (checked against FRED 2026-11-15)
BLS_ON_FRED = {
    "CUSR0000SA0": "CPIAUCSL", "CUSR0000SACL1E": "CUSR0000SACL1E", "CUSR0000SAF11": "CUSR0000SAF11",
    "CUSR0000SETB01": "CUSR0000SETB01",
    "CES9092000001": "CES9092000001", "CES9093000001": "CES9093000001", "CES0800000016": "CES0800000016",
    "CES0500000001": "USPRIV", "CES0500000007": "AWHNONAG", "CES6500000006": "CES6500000006",
    "CES6500000007": "CES6500000007", "CES8000000006": "CES8000000006", "CES8000000007": "CES8000000007",
    "WPSFD41312": "WPSFD41312", "WPUIP2300001": "WPUIP2300001", "WPSFD49207": "WPSFD49207",
    "WPSFD4131": "WPSFD4131", "EIUIR": "IR", "EIUIQ": "IQ", "EIUIR2": "IR2",
}
GDPNOW = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/"
          "data/gdpnow/GDPTrackingModelDataAndForecasts.xlsx")


def _bea_series(addr: str, start: str | None = None) -> Series:
    """'TABLE/CODE' (monthly) or 'TABLE/CODE@Q' (quarterly), as BEA's API serves it."""
    table, code = addr.split("/")
    freq = "Q" if code.endswith("@Q") else "M"
    code = code.removesuffix("@Q")
    rows = econdata.bea_nipa(table, freq)
    rows = rows[rows["code"] == code].drop_duplicates("date").sort_values("date")
    if not len(rows):
        raise RuntimeError(f"BEA table {table} has no series {code} at frequency {freq}")
    if start:
        rows = rows[rows["date"] >= pd.Timestamp(start)]
    return Series(addr, [Obs(d, float(v)) for d, v in zip(rows["date"], rows["value"])])


def _fred_series(sid: str, start: str | None = None) -> Series:
    s = econdata.fred(sid, start)
    return Series(sid, [Obs(d, float(v)) for d, v in s.items()])


def _bls_fetch(ids, start_year: int, end_year: int) -> dict:
    """{BLS id: [Obs]} from each id's FRED twin, start_year through end_year."""
    out = {}
    for sid in ids:
        if sid not in BLS_ON_FRED:
            raise RuntimeError(f"BLS series {sid} has no FRED twin listed in public_doors.BLS_ON_FRED")
        s = econdata.fred(BLS_ON_FRED[sid], f"{start_year}-01-01")
        s = s[s.index.year <= end_year]
        out[sid] = [Obs(d, float(v)) for d, v in s.items()]
    return out


def _not_here(what: str):
    def fail(*_args, **_kwargs):
        raise NotImplementedError(f"{what} is read only by Econvitals' tracking of BEA's later "
                                  "estimates of a quarter, which this folder does not include")
    return fail


# ---- the Atlanta Fed's GDPNow workbook ------------------------------------------------------------
_SHEETS: dict = {}


def _sheet(name: str) -> list:
    """Rows of one sheet of the GDPNow workbook (header first), dates as dates."""
    if name not in _SHEETS:
        book = openpyxl.load_workbook(io.BytesIO(econdata.get(GDPNOW, binary=True, timeout=180)),
                                      read_only=True, data_only=True)

        def cell(v):
            if isinstance(v, dt.datetime):
                return v.date()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and 30000 < v < 80000:
                return dt.date(1899, 12, 30) + dt.timedelta(days=int(v))     # an Excel date serial
            return v
        for ws in book.worksheets:
            if ws.title in ("TrackRecord", "TrackingArchives"):
                _SHEETS[ws.title] = [[cell(v) for v in row] for row in ws.iter_rows(values_only=True)]
        book.close()
    return _SHEETS.get(name, [])


def _qkey(d) -> str | None:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}" if isinstance(d, dt.date) else None


def gdpnow_advance_dates() -> dict:
    """{'2026Q3': '2026-10-29'}: the day BEA published each quarter's advance estimate, from the
    TrackingArchives sheet's "Publication Date of Advance Estimate" column (2014Q2 on)."""
    rows = _sheet("TrackingArchives")
    if not rows:
        return {}
    head = [str(h or "").strip() for h in rows[0]]
    if "Publication Date of Advance Estimate" not in head:
        return {}
    ci = head.index("Publication Date of Advance Estimate")
    out: dict = {}
    for r in rows[1:]:
        if len(r) > ci and isinstance(r[1], dt.date) and isinstance(r[ci], dt.date):
            out.setdefault(_qkey(r[1]), r[ci].isoformat())
    return out


def gdpnow_track_record() -> dict:
    """{'2026Q2': {'final', 'advance', 'release_date', 'error'}} from the TrackRecord sheet: GDPNow's
    last reading and BEA's advance estimate (unrounded), one row per quarter since 2011Q3. The release
    date comes from TrackingArchives wherever it has the quarter, because TrackRecord's own Release
    Date column misdates three quarters (2024Q3 and 2026Q3 carry September 30; 2020Q3 is a day late).
    A row neither sheet dates after the quarter's end, or dated in the future, is left out: an
    advance estimate cannot print inside the quarter it measures."""
    rows = _sheet("TrackRecord")
    dated = gdpnow_advance_dates()
    today = dt.date.today().isoformat()
    out: dict = {}
    for r in rows[1:]:
        if len(r) < 4 or not isinstance(r[0], dt.date):
            continue
        qk = _qkey(r[0])
        rel = dated.get(qk) or (r[3].isoformat() if isinstance(r[3], dt.date) else None)
        if not rel or rel <= r[0].isoformat() or rel > today:
            continue
        try:
            out[qk] = {"final": round(float(r[1]), 4), "advance": round(float(r[2]), 4),
                       "release_date": rel, "error": round(float(r[1]) - float(r[2]), 4)}
        except (TypeError, ValueError):
            continue
    return out


def current_quarter() -> str:
    """The quarter in progress: the one after the last quarter BEA has published."""
    from . import sources
    return str(sources.quarterly("gdp_growth").index[-1] + 1)


# ---- the names the engine's code uses ------------------------------------------------------------
bea = SimpleNamespace(series=_bea_series)
fred = SimpleNamespace(series=_fred_series)
bls_client = SimpleNamespace(fetch=_bls_fetch)
atlfed = SimpleNamespace(gdpnow_track_record=gdpnow_track_record, gdpnow_advance_dates=gdpnow_advance_dates)
providers = SimpleNamespace(series=_not_here("a provider series"))
census_direct = SimpleNamespace(series=_not_here("the trade report's Exhibit 1"))
census_ftd = SimpleNamespace(fetch_exh1=_not_here("the trade report's Exhibit 1"))
