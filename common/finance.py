"""Readers for the Federal Reserve, New York Fed and Treasury files behind the household-finance
and Treasury-debt measures. Keyless; every download goes through `econdata.get`, so it is cached
and identifies itself.

    dfa_by_wealth_group("Net worth")   Distributional Financial Accounts, one column per group
    hhdc_sheet("Page 6 Data")          a data sheet from the NY Fed Household Debt and Credit Report
    treasury_securities(month_end, soma_date)
                                       every marketable Treasury security outstanding at a month
                                       end, with the par amount the Federal Reserve holds
    soma_asof_dates(), soma_asof_for() the dates the Fed's security-level holdings are published for
    soma_agency(soma_date)             the Fed's agency MBS, agency debt and agency CMBS holdings
    treasury_curve("par", year)        Treasury's daily par (or "real") yield curve for one year
"""
from __future__ import annotations

import datetime as dt
import functools
import io
import json
import zipfile

import pandas as pd

from common.econdata import get

# ------------------------------------------------------------------ Distributional Financial Accounts
DFA_ZIP = "https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip"
# The Board splits the top percentile into the top 0.1% and the next 0.9%; the top 1% is their sum.
DFA_GROUPS = {"Bottom50": "bottom50", "Next40": "next40", "Next9": "next9",
              "RemainingTop1": "top1", "TopPt1": "top1"}


def dfa_by_wealth_group(column: str) -> pd.DataFrame:
    """One column of the DFA's net-worth-percentile table (millions of dollars, nominal), with one
    column per wealth group: bottom50, next40, next9, top1. Quarters are dated to their first month."""
    z = zipfile.ZipFile(io.BytesIO(get(DFA_ZIP, binary=True, timeout=120)))
    df = pd.read_csv(z.open("dfa-networth-levels.csv"))
    df["date"] = pd.PeriodIndex(df["Date"].str.replace(":", "-"), freq="Q").to_timestamp()
    df["group"] = df["Category"].map(DFA_GROUPS)
    wide = df.dropna(subset=["group"]).groupby(["date", "group"])[column].sum().unstack()
    wide.columns.name = None
    return wide[["bottom50", "next40", "next9", "top1"]]


# ------------------------------------------------------------------ NY Fed Household Debt and Credit
HHDC_URL = ("https://www.newyorkfed.org/medialibrary/interactives/householdcredit/data/xls/"
            "HHD_C_Report_{q}.xlsx")


@functools.lru_cache(maxsize=1)
def hhdc_workbook() -> tuple[str, bytes]:
    """The newest published Household Debt and Credit Report workbook: (quarter, file bytes).

    One workbook per quarter. A quarter not yet published answers with a web page rather than a
    404, so the file is recognized by the zip signature every .xlsx starts with."""
    q = pd.Period(dt.date.today(), freq="Q")
    for _ in range(6):
        try:
            body = get(HHDC_URL.format(q=f"{q.year}Q{q.quarter}"), binary=True, timeout=120)
            if body[:2] == b"PK":
                return f"{q.year}Q{q.quarter}", body
        except RuntimeError:
            pass
        q -= 1
    raise RuntimeError("no Household Debt and Credit workbook found in the last six quarters")


def hhdc_sheet(sheet: str) -> pd.DataFrame:
    """A time-series data sheet of the report, one row per quarter (dated to its first month),
    columns named as the sheet heads them (e.g. "<620", "620-659", "TOTAL")."""
    _, body = hhdc_workbook()
    raw = pd.read_excel(io.BytesIO(body), sheet_name=sheet, header=None)
    labels = raw.iloc[:, 0].astype(str).str.strip()
    is_quarter = labels.str.match(r"^\d\d:Q[1-4]$")            # the sheet writes 2003Q1 as "03:Q1"
    header_row = raw.index[is_quarter.values.argmax()] - 1
    table = raw[is_quarter.values].copy()
    table.columns = [str(c).strip() for c in raw.loc[header_row]]
    table.index = pd.PeriodIndex(["20" + s.replace(":", "-") for s in labels[is_quarter]],
                                 freq="Q").to_timestamp()
    table.index.name = "date"
    return table.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")


# ------------------------------------------------------------------ Treasury and the Fed's holdings
MSPD = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/mspd/"
        "mspd_table_3_market")
SOMA_DATES = "https://markets.newyorkfed.org/api/soma/asofdates/list.json"
SOMA_TSY = "https://markets.newyorkfed.org/api/soma/tsy/get/asof/{d}.json"
SOMA_AGENCY = "https://markets.newyorkfed.org/api/soma/agency/get/asof/{d}.json"
CURVE = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
         "daily-treasury-rates.csv/{y}/all?type={kind}&field_tdr_date_value={y}&page&_format=csv")

# Table 3's security classes. Before June 2004 Treasury filed TIPS as "Inflation-Indexed Notes"
# and "Inflation-Indexed Bonds"; missing those drops about $200 billion of long debt.
CLASSES = {"Bills Maturity Value": "bill", "Notes": "note", "Bonds": "bond",
           "Inflation-Protected Securities": "tips", "Floating Rate Notes": "frn",
           "Inflation-Indexed Notes": "tips", "Inflation-Indexed Bonds": "tips"}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def mspd_rows(month_end: dt.date) -> list[dict]:
    """Every row of the Monthly Statement of the Public Debt, Table 3 (marketable), at a month end."""
    fields = ("record_date,security_class1_desc,security_class2_desc,interest_rate_pct,"
              "maturity_date,outstanding_amt")
    rows, page = [], 1
    while True:
        got = json.loads(get(MSPD, {"filter": f"record_date:eq:{month_end.isoformat()}",
                                    "fields": fields, "page[size]": 10000,
                                    "page[number]": page}, timeout=180))
        rows += got["data"]
        if page >= got["meta"]["total-pages"]:
            return rows
        page += 1


def soma_asof_dates() -> list[str]:
    """Every date the New York Fed has published security-level SOMA holdings for (Wednesdays)."""
    return sorted(json.loads(get(SOMA_DATES))["soma"]["asOfDates"])


def soma_asof_for(month_end: dt.date, dates: list[str]) -> str | None:
    """The latest holdings date at or before a month end."""
    before = [d for d in dates if d <= month_end.isoformat()]
    return before[-1] if before else None


def treasury_securities(month_end: dt.date, soma_date: str) -> pd.DataFrame:
    """Every marketable Treasury security outstanding at `month_end`, one row per security:
    cusip, kind (bill/note/bond/tips/frn), maturity, coupon (percent), par and fed_par ($ millions),
    where fed_par is the par the Federal Reserve held on `soma_date`.

    Three traps in Table 3 are handled here. Each security is listed once per auction and reopening,
    and only the first row carries the amount outstanding (the rest are blank), so blank rows are
    dropped rather than summed. Matured-but-unredeemed securities stay listed and are kept here (the
    caller drops anything with no remaining term). And a few pre-2010 bills carry a different CUSIP
    prefix in Table 3 than in the Fed's file, so a Fed holding that does not match on CUSIP is
    matched again on maturity date and coupon, which identify a Treasury security uniquely.

    A guard refuses to go on unless the securities add up, class by class, to Treasury's own
    published subtotals for that month within 0.05 percent.
    """
    rows = mspd_rows(month_end)
    if not rows:                                   # not published yet
        return pd.DataFrame()
    secs, subtotals = [], {}
    for r in rows:
        cls1, par, mat = r["security_class1_desc"], _num(r["outstanding_amt"]), r["maturity_date"]
        if cls1 in CLASSES and mat in (None, "null", ""):          # a subtotal line
            name = (r["security_class2_desc"] or "").lower()
            slot = "unmatured" if "unmatured" in name else "matured" if "matured" in name else "total"
            subtotals.setdefault(cls1, {})[slot] = par
            continue
        if cls1 not in CLASSES or par is None or par <= 0 or not mat or mat == "null":
            continue
        secs.append(dict(cusip=r["security_class2_desc"], kind=CLASSES[cls1], class1=cls1,
                         maturity=dt.date.fromisoformat(mat), coupon=_num(r["interest_rate_pct"]),
                         par=par))

    # The guard. Treasury's unmatured subtotal is best taken as its total less its matured line;
    # the printed "unmatured" line is the fallback (it is occasionally wrong, and spelled
    # inconsistently).
    for cls1, v in subtotals.items():
        mine = sum(x["par"] for x in secs if x["class1"] == cls1)
        targets = ([v["total"] - (v.get("matured") or 0.0)] if v.get("total") is not None else []) + \
                  ([v["unmatured"]] if v.get("unmatured") is not None else [])
        if targets and not any(w and abs(mine - w) / w <= 0.0005 for w in targets):
            raise RuntimeError(f"{month_end} {cls1}: securities sum to ${mine / 1e3:,.1f}bn, Treasury's "
                               f"subtotal is ${targets[0] / 1e3:,.1f}bn; refusing to go on")

    known = {x["cusip"] for x in secs}
    by_terms: dict = {}
    for x in secs:
        by_terms.setdefault((x["maturity"], round(x["coupon"] or 0.0, 3)), []).append(x["cusip"])
    fed: dict = {}
    for h in json.loads(get(SOMA_TSY.format(d=soma_date), timeout=120))["soma"]["holdings"]:
        p = _num(h.get("parValue"))
        if not p:
            continue
        c = h["cusip"]
        if c not in known:
            hit = by_terms.get((dt.date.fromisoformat(h["maturityDate"][:10]),
                                round(_num(h.get("coupon")) or 0.0, 3)))
            if hit and len(hit) == 1:
                c = hit[0]
        fed[c] = fed.get(c, 0.0) + p / 1e6
    for x in secs:
        x["fed_par"] = min(fed.get(x["cusip"], 0.0), x["par"])
    return pd.DataFrame(secs)


def soma_agency(soma_date: str) -> list[dict]:
    """The Fed's agency holdings (agency MBS, agency debt, agency CMBS) on one date, as published."""
    return json.loads(get(SOMA_AGENCY.format(d=soma_date), timeout=300))["soma"]["holdings"]


def treasury_curve(kind: str, year: int) -> pd.DataFrame:
    """Treasury's daily par ("par") or real ("real") yield curve for one year, percent; one row per
    business day, columns headed in years to maturity (1/12, 0.25, ..., 30)."""
    t = {"par": "daily_treasury_yield_curve", "real": "daily_treasury_real_yield_curve"}[kind]
    df = pd.read_csv(io.StringIO(get(CURVE.format(y=year, kind=t))))
    df.index = pd.to_datetime(df.pop("Date"), format="%m/%d/%Y").dt.date
    tenors = {}
    for col in df.columns:
        n, unit = col.split()[0], col.split()[1].lower()
        tenors[col] = float(n) / 12 if unit.startswith("mo") else float(n)
    return df.rename(columns=tenors).sort_index()
