"""Risk Monitor — rebuilds the numbers of econvitals.org's Risk Monitor from its scored readings and,
as far as public data allows, the readings themselves.

    python replicate.py            # needs FRED_API_KEY and BEA_API_KEY
    python replicate.py --stage1   # only the arithmetic on the published readings (no keys, one download)

The page scores 32 indicators against their own record since January 1990, averages them into a heat map
of six areas, and keeps a record of eight recession signals. It reads them all from one data file (its
address is `published` in check.json, the one place it is written). This script works in two stages.

STAGE 1, THE ARITHMETIC (exact; a fresh implementation of the definitions on the page and in its method
note, sharing no code with Econvitals' builder). From each scored indicator's stored readings:

1. THE PERCENTILE of every period's reading and of the latest reading. A reading x is ranked against the
   indicator's own stored readings from January 1990 (the first quarter of 1990; 1990 for a yearly
   series), or from its first reading if it began later, through the latest:

       p(x) = 100 x (readings below x + half the readings equal to x) / all those readings

   and where LOWER is riskier the percentile is 100 minus that, so 100 is always the riskiest reading
   since 1990. The latest reading is the latest NATIVE one (for a daily series, the last close, ranked
   among the monthly means).

2. THE HEAT MAP, six areas by quarter from 1990 Q1 through the quarter in progress. An indicator's value
   in a quarter is the mean of its monthly percentiles in the quarter (a monthly series), its percentile
   that quarter (quarterly), or the percentile of the year containing the quarter's last month (yearly;
   for the four federal budget series the FISCAL year, so October to December count in the next one).
   A quarter with no reading takes the indicator's latest earlier value for at most four quarters, then
   the indicator drops out until it reads again; `held` counts the quarters so carried at the end of the
   row. A cell is the plain mean of the indicators with a value that quarter; a year is the plain mean of
   its quarterly cells. Every stored number is rounded to six significant digits, and each step works from
   the numbers the step before it stored: quarterly values are means of the rounded percentiles, cells
   means of the rounded quarterly values, years means of the rounded cells.

3. THE RECESSION SIGNALS. Each signal is on or off at each of its readings. An ALARM is a run of readings
   with it on; once off it must stay off for a year (12 months; 4 quarters for the forecasters' survey)
   before a new alarm is counted, so an on-reading more than 12 periods after the last one starts a new
   alarm and any nearer one extends the current alarm. With s an alarm's first
   period, e its last, and the NBER's peaks P and troughs T (quarterly dates for the survey):

       late    a recession was under way when it began (P < s <= T)
       hit     else a peak fell in [s, e + N], N = 12 months (4 quarters); its lead is P - s
       late    else it began within K = 3 months (1 quarter) after a trough (T < s <= T + K)
       open    else e + N is after the last reading (too soon to say)
       false   otherwise

   A recession (judged only if its peak is at least N periods after the first reading) is WARNED if an
   alarm that was not late was on at a reading in [P - N, P] more than K periods after the previous
   trough; its lead is then measured from that alarm's first on-reading after the previous trough plus
   K. It is LATE if the signal was on only in (P, T + K], measured from the first such reading, and
   MISSED otherwise. The two derived signal series are rebuilt too: jobless claims as the percent by
   which the three-month average of the monthly mean of weekly claims (the month in progress left out)
   exceeds its lowest three-month average of the previous 12 months, and the loan officer survey re-dated
   to the month it was published (the survey quarter's first month plus one).

STAGE 2, THE INPUTS. Each scored series, and each series behind a recession signal, that can reasonably
be rebuilt from its publisher's public file is rebuilt and compared with the page's stored readings since
1990 (or the series' start). For a daily or weekly series the stored reading is the month's mean of the
publisher's readings, so the page's last month - the month in progress - is not compared. The other ten
scored series are RECORDED: read from the page's data file at run time and never copied here. The
README lists which is which, and why.

Writes to output/ (keys are the positions the page's data file uses, so check.json can compare them):
    percentiles.csv      indicator x period: the percentile         pct.csv           latest reading's percentile
    heat_rows.csv        area x quarter: the cell                   heat_parts.csv    area x indicator x quarter
    heat_held.csv        area x indicator: quarters carried         heat_years.csv    area x year: the cell
    signal_alarms.csv    each alarm: first, last, n, kind, peak, lead
    signal_recessions.csv  each judged recession: kind, first_on, lead
    signal_counts.csv    the counts the page tabulates              signal_last_on.csv  last period on
    signal_tested.csv    claims and loan officer series rebuilt from the stored readings
    checks.csv           the page's own sample of percentiles and heat cells, from the above
    inputs.csv           every rebuilt reading, beside the page's   inputs_summary.csv  one line a series
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import operator
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_nipa, fred, get, published  # noqa: E402
from common.finance import hhdc_sheet  # noqa: E402

PUBLISHED = json.loads((HERE / "check.json").read_text())["published"]
BUDGET = {"fed_debt_gdp", "fed_deficit_gdp", "fed_netint_gdp", "fed_netint_receipts"}
CMP = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}

# The NBER's peaks and troughs, by month and by quarter.
# https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions
NBER = [("1948-11", "1949-10", "1948-Q4", "1949-Q4"), ("1953-07", "1954-05", "1953-Q2", "1954-Q2"),
        ("1957-08", "1958-04", "1957-Q3", "1958-Q2"), ("1960-04", "1961-02", "1960-Q2", "1961-Q1"),
        ("1969-12", "1970-11", "1969-Q4", "1970-Q4"), ("1973-11", "1975-03", "1973-Q4", "1975-Q1"),
        ("1980-01", "1980-07", "1980-Q1", "1980-Q3"), ("1981-07", "1982-11", "1981-Q3", "1982-Q4"),
        ("1990-07", "1991-03", "1990-Q3", "1991-Q1"), ("2001-03", "2001-11", "2001-Q1", "2001-Q4"),
        ("2007-12", "2009-06", "2007-Q4", "2009-Q2"), ("2020-02", "2020-04", "2019-Q4", "2020-Q2")]


# ── periods: an integer per grid, so arithmetic on dates is arithmetic on integers ────────────────
def idx(p: str, grid: str) -> int:
    if grid == "M":
        return int(p[:4]) * 12 + int(p[5:7]) - 1
    if grid == "Q":
        return int(p[:4]) * 4 + int(p[-1]) - 1
    return int(p[:4])


def lab(i: int, grid: str) -> str:
    if grid == "M":
        return f"{i // 12}-{i % 12 + 1:02d}"
    if grid == "Q":
        return f"{i // 4}-Q{i % 4 + 1}"
    return str(i)


def sig6(x: float) -> float:
    """Six significant digits, as the page stores every number."""
    return float(f"{x:.6g}")


def fmt(x) -> str:
    return "" if x is None else f"{x:.6g}"


def stored(ind: dict) -> dict:
    """{period index: value} of an indicator's stored readings (nulls left out)."""
    s = idx(ind["s"], ind["grid"])
    return {s + k: v for k, v in enumerate(ind["v"]) if v is not None}


def write(name: str, rows: list[dict]) -> None:
    out = HERE / "output"
    out.mkdir(exist_ok=True)
    with open(out / f"{name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ══ STAGE 1 ══════════════════════════════════════════════════════════════════════════════════════
BASIS = {"M": idx("1990-01", "M"), "Q": idx("1990-Q1", "Q"), "A": 1990}


def percentiles(ind: dict) -> tuple[dict, float]:
    """({period: percentile} from the basis start, percentile of the latest native reading)."""
    vals = stored(ind)
    basis = [v for t, v in vals.items() if t >= BASIS[ind["grid"]]]

    def rank(x: float) -> float:
        below = sum(b < x for b in basis)
        equal = sum(b == x for b in basis)
        r = 100 * (below + 0.5 * equal) / len(basis)
        return 100 - r if ind["riskier"] == "lower" else r

    return {t: rank(v) for t, v in vals.items() if t >= BASIS[ind["grid"]]}, rank(ind["now"])


def quarter_values(iid: str, ind: dict, p: dict, q0: int, q1: int) -> tuple[list, int]:
    """An indicator's heat-map value in each quarter q0..q1 (with the four-quarter carry), and the
    number of quarters carried at the end."""
    p = {t: sig6(v) for t, v in p.items()}
    raw = {}
    for q in range(q0, q1 + 1):
        y, k = divmod(q, 4)
        if ind["grid"] == "M":
            months = [p[m] for m in range(y * 12 + 3 * k, y * 12 + 3 * k + 3) if m in p]
            if months:
                raw[q] = sig6(sum(months) / len(months))
        elif ind["grid"] == "Q":
            if q in p:
                raw[q] = p[q]
        else:
            year = y + 1 if iid in BUDGET and 3 * k + 3 >= 10 else y     # Oct-Dec: the next fiscal year
            if year in p:
                raw[q] = p[year]
    out, last, last_q = [], None, None
    for q in range(q0, q1 + 1):
        if q in raw:
            last, last_q = raw[q], q
            out.append(last)
        else:
            out.append(last if last_q is not None and q - last_q <= 4 else None)
    held = next((n for n, q in enumerate(range(q1, q0 - 1, -1)) if q in raw), q1 - q0 + 1)
    return out, held


def stage1(data: dict) -> dict:
    ind = data["ind"]
    areas = {a: list(parts) for a, parts in data["heat"]["parts"].items()}   # the six areas, in order
    pct_rows, p_rows, pct_by = [], [], {}
    for a, ids in areas.items():
        for i in ids:
            p, now = percentiles(ind[i])
            pct_by[i] = p
            s = idx(ind[i]["s"], ind[i]["grid"])
            for t, v in sorted(p.items()):
                p_rows.append({"key": f"{i}|{t - s}", "id": i, "period": lab(t, ind[i]["grid"]), "p": fmt(v)})
            pct_rows.append({"key": i, "id": i, "now": ind[i]["now"], "now_date": ind[i]["now_date"],
                             "pct": fmt(now)})
    write("percentiles", p_rows)
    write("pct", pct_rows)

    # The heat map runs through the quarter in progress on the day the file was built.
    asof = dt.date.fromisoformat(data["meta"]["asof"])
    q0, q1 = BASIS["Q"], asof.year * 4 + (asof.month - 1) // 3
    rows, parts, held = {}, {}, {}
    for a, ids in areas.items():
        parts[a] = {}
        for i in ids:
            parts[a][i], held[(a, i)] = quarter_values(i, ind[i], pct_by[i], q0, q1)
        rows[a] = []
        for k in range(q1 - q0 + 1):
            xs = [parts[a][i][k] for i in ids if parts[a][i][k] is not None]
            rows[a].append(sig6(sum(xs) / len(xs)) if xs else None)
    write("heat_rows", [{"key": f"{a}|{k}", "area": a, "quarter": lab(q0 + k, "Q"), "cell": fmt(v)}
                        for a in areas for k, v in enumerate(rows[a])])
    write("heat_parts", [{"key": f"{a}|{i}|{k}", "area": a, "id": i, "quarter": lab(q0 + k, "Q"), "value": fmt(v)}
                         for a in areas for i in areas[a] for k, v in enumerate(parts[a][i])])
    write("heat_held", [{"key": f"{a}|{i}", "area": a, "id": i, "held": n} for (a, i), n in held.items()])
    years = []
    for a in areas:
        for y in range(q0 // 4, q1 // 4 + 1):
            cells = [rows[a][q - q0] for q in range(4 * y, 4 * y + 4) if q0 <= q <= q1 and rows[a][q - q0] is not None]
            years.append({"key": f"{a}|{y - q0 // 4}", "area": a, "year": y,
                          "cell": fmt(sig6(sum(cells) / len(cells))) if cells else ""})
    write("heat_years", years)

    # The page's own sample (`checks`), from the numbers above.
    checks = []
    for c in data.get("checks", []):
        if c["what"] == "pct":
            i = c["id"]
            g = ind[i]["grid"]
            v = (next(r["pct"] for r in pct_rows if r["id"] == i) if c["at"] == "now"
                 else fmt(pct_by[i].get(idx(c["at"], g))) if idx(c["at"], g) in pct_by[i] else "")
            checks.append({"key": f"pct|{i}|{c['at']}", "value": v})
        elif c["what"] == "heat":
            q = idx(c["at"], "Q")
            checks.append({"key": f"heat|{c['area']}|{c['at']}", "value": fmt(rows[c["area"]][q - q0])})
    write("checks", checks)

    signals(data)
    return {"areas": areas, "pct": pct_by}


def signals(data: dict) -> None:
    alarms_out, recs_out, counts_out, last_on, tested_out = [], [], [], [], []
    ind = data["ind"]
    for pos, row in enumerate(data["signals"]["rows"]):
        t = row.get("tested")
        if not t:
            continue                                      # Kalshi's contract has no rule
        g = t["grid"]
        N, QUIET, K = (12, 12, 3) if g == "M" else (4, 4, 1)
        recs = [(idx(a, "M"), idx(b, "M")) if g == "M" else (idx(c, "Q"), idx(d, "Q")) for a, b, c, d in NBER]
        s0 = idx(t["s"], g)
        reads = {s0 + k: v for k, v in enumerate(t["v"]) if v is not None}
        first, last = min(reads), max(reads)
        on = sorted(p for p, v in reads.items() if CMP[row["cmp"]](v, row["threshold"]))

        spans = []                                        # alarms as [s, e]
        for p in on:
            if spans and p - spans[-1][1] <= QUIET:
                spans[-1][1] = p
            else:
                spans.append([p, p])
        res = []
        for s, e in spans:
            kind, peak = None, None
            peak = next((P for P, T in recs if P < s <= T), None)
            if peak is not None:
                kind = "late"
            else:
                peak = next((P for P, T in recs if s <= P <= e + N), None)
                if peak is not None:
                    kind = "hit"
                else:
                    peak = next((P for P, T in recs if T < s <= T + K), None)
                    kind = "late" if peak is not None else ("open" if e + N > last else "false")
            res.append((s, e, kind, peak))
            alarms_out.append({"key": f"{pos}|{len(res) - 1}", "signal": row["id"], "first": lab(s, g),
                               "last": lab(e, g), "n": e - s + 1, "kind": kind,
                               "peak": "" if peak is None else lab(peak, g), "lead": "" if peak is None else peak - s})
        judged = []
        for j, (P, T) in enumerate(recs):
            if P - first < N:
                continue
            after = recs[j - 1][1] + K if j else None     # readings must come after the previous trough + K
            good = [(s, e) for s, e, kind, _ in res if kind != "late"]
            window = [p for p in on if P - N <= p <= P and (after is None or p > after)
                      and any(s <= p <= e for s, e in good)]
            if window:
                s, e = next((s, e) for s, e in good if s <= window[0] <= e)
                fo = next(p for p in on if s <= p <= e and (after is None or p > after))
                kind = "warned"
            else:
                late = [p for p in on if P < p <= T + K]
                kind, fo = ("late", late[0]) if late else ("missed", None)
            judged.append(kind)
            recs_out.append({"key": f"{pos}|{len(judged) - 1}", "signal": row["id"], "peak": lab(P, g),
                             "kind": kind, "first_on": "" if fo is None else lab(fo, g),
                             "lead": "" if fo is None else P - fo})
        kinds = [r[2] for r in res]
        counts = {"alarms": len(res), "before": kinds.count("hit"), "after": kinds.count("late"),
                  "false": kinds.count("false"), "open": kinds.count("open"), "judged": len(judged),
                  "warned": judged.count("warned"), "late": judged.count("late"), "missed": judged.count("missed")}
        counts_out += [{"key": f"{pos}|{k}", "signal": row["id"], "count": k, "value": v} for k, v in counts.items()]
        last_on.append({"key": str(pos), "signal": row["id"], "last_on": lab(on[-1], g) if on else ""})

        # The two signal series derived from stored readings.
        if row["id"] == "claims":
            c = stored(ind["claims"])
            months = [m for m in sorted(c) if m < max(c)]            # the month in progress is left out
            avg3 = {m: sum(c[m - j] for j in range(3)) / 3 for m in months if all(m - j in c for j in range(3))}
            for m in sorted(avg3):
                prev = [avg3[m - k] for k in range(1, 13) if m - k in avg3]
                if len(prev) == 12:
                    tested_out.append({"key": f"{pos}|{m - s0}", "signal": "claims", "period": lab(m, "M"),
                                       "value": fmt(100 * (avg3[m] / min(prev) - 1))})
        if row["id"] == "sloos":
            src = ind[row["series"]]
            for q, v in stored(src).items():
                m = (q // 4) * 12 + (q % 4) * 3 + 1               # the survey quarter's first month, plus one
                tested_out.append({"key": f"{pos}|{m - s0}", "signal": "sloos", "period": lab(m, "M"),
                                   "value": fmt(v)})
    write("signal_alarms", alarms_out)
    write("signal_recessions", recs_out)
    write("signal_counts", counts_out)
    write("signal_last_on", last_on)
    write("signal_tested", tested_out)


# ══ STAGE 2: the inputs, from their publishers ═══════════════════════════════════════════════════
def monthly_mean(daily: dict) -> dict:
    """{'YYYY-MM': mean} of {date string 'YYYY-MM-DD': value}."""
    by = {}
    for d, v in daily.items():
        by.setdefault(d[:7], []).append(v)
    return {m: sum(vs) / len(vs) for m, vs in by.items()}


def csv_rows(url: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(get(url).lstrip("﻿"))))


def quarter_label(d) -> str:
    d = pd.Timestamp(d)
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


# Robert Shiller's file. Its address changes with every upload, so it is read off the home page.
def shiller_cape() -> dict:
    page = get("https://shillerdata.com/")
    m = re.search(r'(?:https?:)?//[^"\'\s<>()]+/ie_data\.xls[^"\'\s<>()]*', page)
    url = m.group(0).replace("&amp;", "&")
    url = "https:" + url if url.startswith("//") else url
    raw = pd.read_excel(io.BytesIO(get(url, binary=True)), sheet_name="Data", header=None)
    head = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "Date"][0]
    cols = [str(c).strip() for c in raw.loc[head]]
    out = {}
    for _, r in raw.loc[head + 1:].iterrows():
        d, v = r.iloc[0], r.iloc[cols.index("CAPE")]
        if isinstance(d, (int, float)) and 1800 < d < 2200 and isinstance(v, (int, float)) and v == v:
            y = int(d)
            out[f"{y}-{int(round((d - y) * 100)):02d}"] = float(v)   # the date is YYYY.MM: 2025.1 is October
    return out


def bea_q(table: str, code: str) -> dict:
    df = bea_nipa(table, "Q", _pace=12)
    s = df[df["code"] == code].drop_duplicates("date").set_index("date")["value"]
    return {quarter_label(d): float(v) for d, v in s.items()}


def gdp() -> dict:
    """Nominal GDP, $ millions at an annual rate (BEA table 1.1.5, line 1)."""
    return bea_q("T10105", "A191RC")


_Z1: dict = {}


def z1(table: str, code: str) -> dict:
    """One series of the Federal Reserve's Financial Accounts (Z.1), from the Board's own zip of CSV tables:
    {'YYYY-Qn': $ millions}. Before 1952 the accounts are annual, dated to the fourth quarter."""
    if "zip" not in _Z1:
        _Z1["zip"] = zipfile.ZipFile(io.BytesIO(get(
            "https://www.federalreserve.gov/releases/z1/current/z1_csv_files.zip", binary=True, timeout=180)))
    df = pd.read_csv(_Z1["zip"].open(f"csv/{table}.csv"), dtype=str)
    out = {}
    for d, v in zip(df["date"], df[code + ".Q"]):
        try:
            out[d.replace(":", "-")] = float(v)
        except ValueError:
            continue                                      # "ND": no data
    return out


def ratio(num: dict, den: dict, scale: float = 100.0) -> dict:
    return {k: scale * num[k] / den[k] for k in num if k in den and den[k]}


def mktcap_gdp() -> dict:
    """All U.S. corporate stock at market value (Z.1 table F.51.1: nonfinancial corporations' issues plus
    domestic financial corporations' issues, less closed-end funds' and ETFs' shares, which the financial
    line counts on top of the stocks the funds hold), percent of the quarter's GDP."""
    parts = {c: z1("F51_1_s", c) for c in ("LM103164105", "LM793164105", "LM554090005", "LM564090005")}
    x = {d: parts["LM103164105"][d] + parts["LM793164105"][d] - parts["LM554090005"].get(d, 0.0)
         - parts["LM564090005"].get(d, 0.0) for d in parts["LM103164105"] if d in parts["LM793164105"]}
    return ratio(x, gdp())


def vix() -> dict:
    rows = csv_rows("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv")
    return monthly_mean({dt.datetime.strptime(r["DATE"], "%m/%d/%Y").date().isoformat(): float(r["CLOSE"])
                         for r in rows})


def ebp_file(col: str, scale: float = 1.0) -> dict:
    rows = csv_rows("https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv")
    return {r["date"][:7]: float(r[col]) * scale for r in rows if r[col] not in ("", "NA", "NaN")}


def nfci() -> dict:
    rows = csv_rows("https://api.data.chicagofed.org/NFCI/nfci-data-series-csv.csv")
    return monthly_mean({dt.datetime.strptime(r["Friday_of_Week"], "%m/%d/%Y").date().isoformat(): float(r["NFCI"])
                         for r in rows if r["NFCI"]})


def ofr_fsi() -> dict:
    rows = csv_rows("https://www.financialresearch.gov/financial-stress-index/data/fsi.csv")
    return monthly_mean({r["Date"]: float(r["OFR FSI"]) for r in rows if r["OFR FSI"] not in ("", "NA")})


# The FDIC's sums over insured institutions, by quarter, from its public API.
FDIC_QBP = "INSFDIC:1 AND IBA:0 AND CONSERVE:0"         # the Quarterly Banking Profile's universe
FDIC_CALL = FDIC_QBP + " AND FORMCFR:1"                 # Call Report filers (securities' fair values)
FDIC_DIF = "INSFDIC:1"                                  # the insurance fund tables' universe


def fdic(filters: str, fields: str) -> list[dict]:
    body = json.loads(get("https://api.fdic.gov/banks/financials",
                          {"filters": filters, "agg_by": "REPDTE", "agg_sum_fields": fields,
                           "agg_limit": "400", "limit": "0"}))
    rows = [r["data"] for r in body["data"]]
    for r in rows:
        y, m = int(r["REPDTE"][:4]), int(r["REPDTE"][4:6])
        r["q"] = f"{y}-Q{(m - 1) // 3 + 1}"
    return rows


def bank_capital_leverage() -> dict:
    """Tier 1 capital over average total assets (the FDIC's leverage ratio), percent."""
    return {r["q"]: 100 * r["sum_RBCT1"] / r["sum_AVASSETJ"]
            for r in fdic(FDIC_QBP, "RBCT1,AVASSETJ") if r.get("sum_RBCT1") and r.get("sum_AVASSETJ")}


def bank_unrealized_pct_tier1() -> dict:
    """Securities' fair value less amortized cost (available for sale plus held to maturity), percent of
    tier 1 capital, Call Report filers; from 1994, when fair values were first reported."""
    out = {}
    for r in fdic(FDIC_CALL, "RBCT1,SCAA,SCAF,SCHA,SCHF"):
        g = lambda f: r.get("sum_" + f) or 0  # noqa: E731
        if (g("SCHA") or g("SCAA")) and g("RBCT1"):
            out[r["q"]] = 100 * (g("SCAF") - g("SCAA") + g("SCHF") - g("SCHA")) / g("RBCT1")
    return out


def uninsured_deposits_share() -> dict:
    """Estimated uninsured deposits, percent of domestic deposits, all insured institutions."""
    out = {}
    for r in fdic(FDIC_DIF, "DEPDOM,DEPINS,DEPUNINS"):
        dom, ins, un = r.get("sum_DEPDOM") or 0, r.get("sum_DEPINS") or 0, r.get("sum_DEPUNINS") or 0
        if dom and un and ins + un >= 0.9 * dom:          # 1984 Q1 has no usable insured figure
            out[r["q"]] = 100 * un / dom
    return out


def fred_m(sid: str) -> dict:
    return {d.strftime("%Y-%m"): float(v) for d, v in fred(sid).items()}


def fred_q(sid: str) -> dict:
    return {quarter_label(d): float(v) for d, v in fred(sid).items()}


def fred_d(sid: str) -> dict:
    return {d.strftime("%Y-%m-%d"): float(v) for d, v in fred(sid).items()}


def h8_nonbank_share() -> dict:
    """Bank loans to nondepository financial institutions, percent of all loans and leases, all commercial
    banks, seasonally adjusted, weekly (H.8, as FRED republishes it)."""
    nb, tot = fred_d("LNFACBW027SBOG"), fred_d("TOTLL")
    return monthly_mean({d: 100 * v / tot[d] for d, v in nb.items() if tot.get(d)})


def sofr_iorb() -> dict:
    """SOFR (the New York Fed's own API: FRED's copy lacks the rate's first day, April 2, 2018) minus the
    Board's rate on reserve balances (on excess reserves before July 29, 2021), basis points."""
    iorb = {**fred_d("IOER"), **fred_d("IORB")}
    body = json.loads(get("https://markets.newyorkfed.org/api/rates/secured/sofr/search.json",
                          {"startDate": "2018-04-02", "endDate": dt.date.today().isoformat()}))
    sofr = {r["effectiveDate"]: float(r["percentRate"]) for r in body["refRates"]}
    return monthly_mean({d: round((v - iorb[d]) * 100, 4) for d, v in sofr.items() if d in iorb})


def bd_leverage() -> dict:
    """Security brokers and dealers' total financial assets over their equity capital (Z.1)."""
    return ratio(fred_q("BOGZ1FL664090005Q"), fred_q("BOGZ1FL665080003Q"), 1.0)


def hh_delinq() -> dict:
    t = hhdc_sheet("Page 12 Data")["ALL"].dropna()
    return {quarter_label(d): float(v) for d, v in t.items()}


def nfc_interest_coverage() -> dict:
    """(Profits before tax + net interest) / net interest, nonfinancial corporations (BEA table 1.14)."""
    pbt, ni = bea_q("T11400", "A464RC"), bea_q("T11400", "B471RC")
    return {q: (pbt[q] + ni[q]) / ni[q] for q in pbt if q in ni and ni[q] > 0}


def term_premium_acm() -> dict:
    x = pd.read_excel(io.BytesIO(get("https://www.newyorkfed.org/medialibrary/media/research/data_indicators/"
                                     "ACMTermPremium.xls", binary=True, timeout=180)), sheet_name="ACM Daily")
    dates = pd.to_datetime(x["DATE"], format="%d-%b-%Y")                  # "25-Nov-2026"
    return monthly_mean({d.strftime("%Y-%m-%d"): float(v) for d, v in zip(dates, x["ACMTP10"]) if v == v})


def bey(d: float) -> float:
    """3-month bill, discount basis -> bond-equivalent yield, the New York Fed's conversion (percent)."""
    return 100 * (365 * d / 100) / (360 - 91 * d / 100)


def spread_10y3m() -> dict:
    y10, bill = fred_m("GS10"), fred_m("TB3MS")
    return {m: round(y10[m] - bey(bill[m]), 6) for m in y10 if m in bill}


def spread_2s10s() -> dict:
    y10, y2 = fred_m("GS10"), fred_m("GS2")
    return {m: round(y10[m] - y2[m], 6) for m in y2 if m in y10}


def ny_prob() -> dict:
    """The New York Fed's probability, moved back twelve months to the month of the spread behind it."""
    x = pd.read_excel(io.BytesIO(get("https://www.newyorkfed.org/medialibrary/media/research/capital_markets/"
                                     "allmonth.xls", binary=True)))
    out = {}
    for d, p in zip(pd.to_datetime(x["Date"]), x["Rec_prob"]):
        if p == p:
            m = d.year * 12 + d.month - 1 - 12
            out[f"{m // 12}-{m % 12 + 1:02d}"] = 100 * float(p)
    return out


def sahm() -> dict:
    """Three-month average unemployment rate (at least two of its three months, the month itself among
    them) minus the lowest such average of the previous twelve months (at least eleven of them), rounded
    to two decimals. BLS's rate, as FRED republishes it (UNRATE = LNS14000000)."""
    ur = {idx(m, "M"): v for m, v in fred_m("UNRATE").items()}
    avg = {}
    for t in range(min(ur) + 2, max(ur) + 1):
        win = [ur[m] for m in (t - 2, t - 1, t) if m in ur]
        if t in ur and len(win) >= 2:
            avg[t] = sum(win) / len(win)
    out = {}
    for t in sorted(avg):
        prev = [avg[t - k] for k in range(1, 13) if t - k in avg]
        if len(prev) >= 11:
            out[lab(t, "M")] = round(avg[t] - min(prev), 2)
    return out


def claims() -> dict:
    """Monthly mean of weekly initial claims, seasonally adjusted; a week belongs to its Saturday's month
    (the Labor Department's series, as FRED republishes it: ICSA)."""
    return monthly_mean(fred_d("ICSA"))


def spf_recess2() -> dict:
    x = pd.read_excel(io.BytesIO(get("https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/"
                                     "survey-of-professional-forecasters/data-files/files/mean_recess_level.xlsx",
                                     binary=True)))
    return {f"{int(y)}-Q{int(q)}": float(v) for y, q, v in zip(x["YEAR"], x["QUARTER"], x["RECESS2"])
            if isinstance(v, (int, float)) and v == v}


# id -> (rebuilder, where it comes from). Every other scored series is recorded (see RECORDED).
REBUILT = {
    "cape": (shiller_cape, "Robert Shiller, ie_data.xls (shillerdata.com)"),
    "mktcap_gdp": (mktcap_gdp, "Federal Reserve Z.1 (z1_csv_files.zip, table F.51.1) over BEA GDP (table 1.1.5)"),
    "vix": (vix, "Cboe, VIX_History.csv"),
    "gz_spread": (lambda: ebp_file("gz_spread"), "Federal Reserve Board, ebp_csv.csv"),
    "ebp": (lambda: ebp_file("ebp"), "Federal Reserve Board, ebp_csv.csv"),
    "nfci": (nfci, "Federal Reserve Bank of Chicago, nfci-data-series-csv.csv"),
    "ofr_fsi": (ofr_fsi, "Office of Financial Research, fsi.csv"),
    "sofr_iorb": (sofr_iorb, "New York Fed SOFR API, less the Board's IORB/IOER (FRED: IORB, IOER)"),
    "bank_capital_leverage": (bank_capital_leverage, "FDIC BankFind API, sums of RBCT1 and AVASSETJ"),
    "bank_unrealized_pct_tier1": (bank_unrealized_pct_tier1, "FDIC BankFind API, Call Report filers"),
    "uninsured_deposits_share": (uninsured_deposits_share, "FDIC BankFind API, DEPUNINS over DEPDOM"),
    "bank_cre_delinq": (lambda: fred_q("DRCRELEXFACBS"), "Federal Reserve Board charge-off and delinquency rates (FRED: DRCRELEXFACBS)"),
    "h8_nonbank_share": (h8_nonbank_share, "Federal Reserve Board H.8 (FRED: LNFACBW027SBOG over TOTLL)"),
    "bd_leverage": (bd_leverage, "Federal Reserve Z.1 (FRED: BOGZ1FL664090005Q over BOGZ1FL665080003Q)"),
    "hh_debt_gdp": (lambda: ratio(z1("D3_s", "LA154104005"), gdp()), "Federal Reserve Z.1 (table D.3) over BEA GDP"),
    "hh_dsr": (lambda: fred_q("TDSP"), "Federal Reserve Board household debt service ratio (FRED: TDSP)"),
    "hh_delinq": (hh_delinq, "New York Fed Household Debt and Credit Report workbook, page 12"),
    "bank_card_delinq": (lambda: fred_q("DRCCLACBS"), "Federal Reserve Board charge-off and delinquency rates (FRED: DRCCLACBS)"),
    "bank_mortgage_delinq": (lambda: fred_q("DRSFRMACBS"), "Federal Reserve Board charge-off and delinquency rates (FRED: DRSFRMACBS)"),
    "biz_debt_gdp": (lambda: ratio(z1("D3_s", "LA144104005"), gdp()), "Federal Reserve Z.1 (table D.3) over BEA GDP"),
    "nfc_interest_coverage": (nfc_interest_coverage, "BEA table 1.14 (A464RC, B471RC)"),
    "term_premium_acm": (term_premium_acm, "New York Fed, ACMTermPremium.xls"),
    # the series behind the recession signals
    "spread_10y3m_m53": (spread_10y3m, "Federal Reserve Board H.15 (FRED: GS10, TB3MS)"),
    "spread_2s10s_m": (spread_2s10s, "Federal Reserve Board H.15 (FRED: GS10, GS2)"),
    "ny_prob": (ny_prob, "New York Fed, allmonth.xls"),
    "sahm": (sahm, "BLS unemployment rate (FRED: UNRATE)"),
    "claims": (claims, "Labor Department weekly claims (FRED: ICSA)"),
    "ebp_recession_prob": (lambda: ebp_file("est_prob", 100.0), "Federal Reserve Board, ebp_csv.csv"),
    "sloos_ci": (lambda: fred_q("DRTSCILM"), "Federal Reserve Board loan officer survey (FRED: DRTSCILM)"),
    "spf_recess2": (spf_recess2, "Federal Reserve Bank of Philadelphia, mean_recess_level.xlsx"),
}
RECORDED = {
    "fwd_pe_fsr": "the Federal Reserve's Financial Stability Report chart data, posted twice a year from a "
                  "licensed source; each report restates the whole history",
    "equity_premium_fsr": "the same Financial Stability Report chart data",
    "problem_banks_pct": "the FDIC's problem bank counts, assembled from quarterly profile workbooks and four "
                         "archived PDF profiles",
    "cftc_lev_net_short": "CFTC Traders in Financial Futures positions, combined across contracts",
    "margin_debt_gdp": "FINRA's margin statistics workbook",
    "ai_capex_ocf": "five companies' filings with the SEC, aggregated by hand-coded rules",
    "fed_debt_gdp": "CBO's historical budget data and Treasury's Monthly Treasury Statement",
    "fed_deficit_gdp": "the same budget files",
    "fed_netint_gdp": "the same budget files",
    "fed_netint_receipts": "the same budget files",
}


def stage2(data: dict) -> None:
    rows, summary = [], []
    for iid, (fn, source) in REBUILT.items():
        ind = data["ind"][iid]
        g = ind["grid"]
        s = idx(ind["s"], g)
        pub = stored(ind)
        mine = {idx(p, g): v for p, v in fn().items()}
        start = max(BASIS[g], s, min(mine))
        end = max(pub)
        if ind["freq"] in ("D", "W"):
            end -= 1                                      # the month in progress is not compared
        n = worst = 0
        for t in range(start, end + 1):
            if t not in mine:
                continue
            v = sig6(mine[t])
            rows.append({"key": f"{iid}|{t - s}", "id": iid, "period": lab(t, g), "rebuilt": fmt(v),
                         "published": fmt(pub.get(t))})
            if t in pub:
                n += 1
                worst = max(worst, abs(v - pub[t]))
        summary.append({"id": iid, "status": "rebuilt", "source": source, "from": lab(start, g),
                        "to": lab(end, g), "compared": n, "max_abs_diff": fmt(worst)})
        print(f"  {iid:28} {n:5} periods {lab(start, g)}..{lab(end, g)}  max diff {worst:.6g}")
    for iid, why in RECORDED.items():
        summary.append({"id": iid, "status": "recorded", "source": why, "from": "", "to": "", "compared": "",
                        "max_abs_diff": ""})
    write("inputs", rows)
    write("inputs_summary", summary)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage1", action="store_true", help="only the arithmetic on the published readings")
    args = ap.parse_args()
    data = published(PUBLISHED)
    scored = [i for i, v in data["ind"].items() if v.get("area")]
    assert len(scored) == 32 and set(REBUILT) | set(RECORDED) >= set(scored), "the scored list changed"
    stage1(data)
    print(f"Stage 1: {len(scored)} scored indicators, the heat map since 1990 Q1, "
          f"{sum(1 for r in data['signals']['rows'] if r.get('tested'))} recession signals.")
    if not args.stage1:
        print("Stage 2: the inputs, against the page's stored readings:")
        stage2(data)


if __name__ == "__main__":
    main()
