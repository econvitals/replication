"""Helpers shared by the measures built on CBO's budget projections.

The fiscal measures need three things the general readers in econdata.py do not cover:

    fred_as_of(series, date)   a FRED series exactly as it stood on a past date (FRED's
                               archive of past vintages, ALFRED), so a script can reproduce a
                               page that was built on that date even after the data are revised
    fiscal_year_gdp(as_of)     BEA's nominal GDP put on the federal fiscal year (October-September)
    treasury_year_end(fy)      Treasury's totals for a fiscal year it has closed, from the final
                               September Monthly Treasury Statement (no key needed)

and one small convenience, read_input(), for the CSVs each measure ships in its inputs/ folder
(CBO's website refuses scripted downloads, so its workbooks travel with this repository).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from common.econdata import get, key

FISCAL_DATA = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"


def read_input(folder: str | Path, name: str) -> pd.DataFrame:
    """A CSV from <folder>/inputs/, indexed by its first column (usually the fiscal year)."""
    return pd.read_csv(Path(folder) / "inputs" / name, index_col=0)


def fred_as_of(series_id: str, as_of: str, start: str | None = None) -> pd.Series:
    """One FRED series as it was published on `as_of` (YYYY-MM-DD), floats on a DatetimeIndex.

    FRED keeps every past vintage of the series it carries; asking for a single real-time date
    returns the numbers a reader would have downloaded that day, before any later revision.
    """
    params = {"series_id": series_id, "api_key": key("FRED_API_KEY"), "file_type": "json",
              "realtime_start": as_of, "realtime_end": as_of}
    if start:
        params["observation_start"] = start
    obs = json.loads(get("https://api.stlouisfed.org/fred/series/observations", params))
    if "observations" not in obs:
        raise RuntimeError(f"FRED {series_id} as of {as_of}: {obs.get('error_message', obs)}")
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs["observations"]},
                  name=series_id)
    return pd.to_numeric(s, errors="coerce").dropna()


def fiscal_year_gdp(as_of: str, first_fy: int = 1991) -> pd.Series:
    """Nominal GDP ($ billions) for every completed federal fiscal year from `first_fy`.

    Fiscal year t runs October of t-1 through September of t, so it is the average of four
    seasonally adjusted annual rates: (t-1) Q4, t Q1, t Q2 and t Q3 (FRED series GDP).
    This calendar is right only from FY1977; before that the fiscal year ran July-June.
    """
    q = fred_as_of("GDP", as_of, start=f"{first_fy - 1}-10-01")
    out = {}
    for t in range(first_fy, q.index.max().year + 1):
        quarters = [pd.Timestamp(f"{t - 1}-10-01"), pd.Timestamp(f"{t}-01-01"),
                    pd.Timestamp(f"{t}-04-01"), pd.Timestamp(f"{t}-07-01")]
        if all(d in q.index for d in quarters):
            out[t] = sum(q[d] for d in quarters) / 4
    return pd.Series(out, name="gdp")


def _mts(table: str, flt: str) -> list:
    raw = get(FISCAL_DATA + f"v1/accounting/mts/{table}", {"filter": flt, "page[size]": "1000"})
    return json.loads(raw).get("data") or []


def treasury_year_end(fy: int, as_of: str | None = None) -> dict | None:
    """Treasury's totals for fiscal year `fy`, in $ billions, or None if the year is not closed.

    `as_of` (YYYY-MM-DD) asks whether the year was closed on that date rather than today; the
    final September statement comes out in the second week of October.

    From the final (September) Monthly Treasury Statement, on the same definitions CBO uses:
      revenues, outlays, deficit   Table 1, fiscal-year-to-date line for FY `fy`
      net_interest                 Table 9 (outlays by function), "Net Interest", year to date
      debt_held_public             Table 6, "Total Borrowing from the Public" at the close of
                                   September (CBO's measure; the Monthly Statement of the Public
                                   Debt's face-value figure runs about $100 billion higher)
    """
    today = dt.date.fromisoformat(as_of) if as_of else dt.date.today()
    if today < dt.date(fy, 10, 8):                  # the September statement is not out yet
        return None
    close = f"{fy}-09-30"
    t1 = _mts("mts_table_1", f"record_date:eq:{close}")
    # A September statement restates the prior year too, so it carries two year-to-date
    # lines; the one wanted hangs off the line labeled "FY <fy>".
    parent = next((r["classification_id"] for r in t1
                   if r.get("classification_desc") == f"FY {fy}"), None)
    ytd = next((r for r in t1 if r.get("classification_desc") == "Year-to-Date"
                and parent and r.get("parent_id") == parent), None)
    if ytd is None:
        return None
    t9 = _mts("mts_table_9", f"record_date:eq:{close},classification_desc:eq:Net Interest")
    t6 = _mts("mts_table_6", f"record_date:eq:{close},"
                             "classification_desc:eq:Total Borrowing from the Public")
    return {
        "revenues": float(ytd["current_month_gross_rcpt_amt"]) / 1e9,
        "outlays": float(ytd["current_month_gross_outly_amt"]) / 1e9,
        "deficit": float(ytd["current_month_dfct_sur_amt"]) / 1e9,
        "net_interest": float(t9[0]["current_fytd_rcpt_outly_amt"]) / 1e9,
        "debt_held_public": float(t6[0]["close_month_acct_bal_amt"]) / 1e9,
    }
