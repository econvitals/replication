"""Recession Explorer — rebuilds the arithmetic of econvitals.org/tools/recession-explorer/ from agency data.

    python replicate.py        # needs FRED_API_KEY and BEA_API_KEY

The page measures every U.S. recession since 1948, as the NBER dates them, on some fifty series. This
script rebuilds those series from the agencies that publish them and recomputes, for each of the twelve
recessions, the three things every chart and table on the page is made from:

1. THE TREND each baseline subtracts. A baseline is the NBER peak plus the series' own pace over a window
   that ends at the peak:

       n10   the 10 years ending at the peak ("10-year trend", the page's default)
       n5    the 5 years ending there ("5-year trend")
       pp    since the last business-cycle peak at least five years earlier ("Peak to peak"; for 1953-54
             the 1948 peak, under five years earlier, is all there is)
       act   no trend ("Actual")

   The pace is COMPOUND growth per period for a level (the level at the window's end over the level at its
   start, to the power one over its length) and the AVERAGE CHANGE per period for a rate that takes a
   trend (the employment-population and participation rates). The unemployment rate, the long-term share
   of the unemployed, claims and the federal funds rate take no trend: zero under every baseline. A trend
   needs five years of data before the peak (with five to ten the 10-year trend uses what exists); nothing
   before 1947 is used, so 1948-49 has no trend and appears only as the actual change.

2. THE GAP FROM TREND, k periods after the peak:

       a level   100 * ((x[k] / x[0]) / (1 + g) ** k - 1)      percent above or below trend
       a rate    x[k] - x[0] - k * d                          percentage points

   and THE LOW POINT: the worst gap within 36 months of the peak, or before the next recession began, under
   each baseline (the lowest where down is bad, the highest where up is bad); with the plain series' own
   low, the trough, and the periods until the series was back at its peak level.

3. WHAT SLOWED GDP: BEA's contributions to real GDP growth (Table 1.1.2), each scaled so the quarter's
   pieces add up to GDP's growth computed from the level, compounded over the recession; each piece's trend
   contribution is its share of GDP's growth over the baseline window times what trend growth would have
   added; the gap is divided by the trend path at the trough. So the six (consumption, business investment,
   housing, inventories, government, net exports) add up EXACTLY to real GDP's gap at the trough. The
   script asserts that for every recession and baseline.

Writes to output/:
    paces.csv           series x recession x baseline: the trend per period and the periods it was taken over
    readings.csv        series x recession x baseline x k: the gap from trend, from two years before the peak
                        to the end of the low-point window
    scorecard.csv       series x recession: trough, plain low, back to peak, and the low point under each baseline
    contributions.csv   recession x baseline: the seventeen contributions, their total and GDP's change

Then check.json compares them with the page's own data file (tools/recession-explorer/data.json).

LEFT OUT: the S&P 500 (the page's closes come from Financial Modeling Prep under license and cannot be
redistributed; its arithmetic is the same as any other level's, with no trend), and the "Today" view (the
same arithmetic with the peak set 6 to 24 months back; it moves with every release). See README.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_nipa, bls_flat, fred, save  # noqa: E402
from common.labor import bls_ln  # noqa: E402

FIRST_YEAR = 1947                  # nothing earlier is used: the quarterly accounts begin in 1947
MIN_YEARS = 5                      # years of data a trend needs before the peak
LOW_WINDOW_MONTHS = 36             # the low point is searched this far past the peak (or to the next peak)
PRE = {1: 24, 3: 8}                # periods written before each peak (the page's charts start here)
BASELINES = ["n10", "n5", "pp", "act"]
TRENDS = ["n10", "n5", "pp"]


# ── time: an integer month index, year * 12 + (month - 1); a quarter is keyed by its first month ────
def ym(y: int, m: int) -> int:
    return y * 12 + (m - 1)


def yq(y: int, q: int) -> int:
    return ym(y, 3 * q - 2)


def label(t: int, step: int) -> str:
    y, m = divmod(t, 12)
    return f"{y}Q{m // 3 + 1}" if step == 3 else f"{y}-{m + 1:02d}"


def to_t(index) -> list[int]:
    return [ym(d.year, d.month) for d in pd.DatetimeIndex(index)]


def as_dict(s: pd.Series) -> dict:
    s = s.dropna()
    s = s[s.index >= pd.Timestamp(f"{FIRST_YEAR}-01-01")]
    return dict(zip(to_t(s.index), s.astype(float).values))


# ── the recessions: NBER's monthly and quarterly peaks and troughs ─────────────────────────────────
# https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions
RECESSIONS = [
    ("1948", ym(1948, 11), ym(1949, 10), yq(1948, 4), yq(1949, 4)),
    ("1953", ym(1953, 7), ym(1954, 5), yq(1953, 2), yq(1954, 2)),
    ("1957", ym(1957, 8), ym(1958, 4), yq(1957, 3), yq(1958, 2)),
    ("1960", ym(1960, 4), ym(1961, 2), yq(1960, 2), yq(1961, 1)),
    ("1969", ym(1969, 12), ym(1970, 11), yq(1969, 4), yq(1970, 4)),
    ("1973", ym(1973, 11), ym(1975, 3), yq(1973, 4), yq(1975, 1)),
    ("1980", ym(1980, 1), ym(1980, 7), yq(1980, 1), yq(1980, 3)),
    ("1981", ym(1981, 7), ym(1982, 11), yq(1981, 3), yq(1982, 4)),
    ("1990", ym(1990, 7), ym(1991, 3), yq(1990, 3), yq(1991, 1)),
    ("2001", ym(2001, 3), ym(2001, 11), yq(2001, 1), yq(2001, 4)),
    ("2007", ym(2007, 12), ym(2009, 6), yq(2007, 4), yq(2009, 2)),
    ("2020", ym(2020, 2), ym(2020, 4), yq(2019, 4), yq(2020, 2)),
]
RECS = []
for i, (key, pm, tm, pq, tq) in enumerate(RECESSIONS):
    nxt = RECESSIONS[i + 1] if i + 1 < len(RECESSIONS) else None
    # The peak that opens the peak-to-peak window: the most recent one at least five years earlier.
    prior = next((r for r in reversed(RECESSIONS[:i]) if pm - r[1] >= MIN_YEARS * 12), None)
    if prior is None and i == 1:
        prior = RECESSIONS[0]                     # 1953-54: the 1948 peak is all there is
    RECS.append({"key": key, "has_trend": i > 0,  # 1948-49: under two years of accounts before its peak
                 "peak": {1: pm, 3: pq}, "trough": {1: tm, 3: tq},
                 "next": {1: nxt[1], 3: nxt[3]} if nxt else {1: None, 3: None},
                 "prior": {1: prior[1], 3: prior[3]} if prior else None})


# ── the series ─────────────────────────────────────────────────────────────────────────────────────
# key: (frequency step, kind, which way is worse). kind: level = percent of the peak, own compound
# trend; rate_trend = points, own average-change trend; rate = points, no trend.
SERIES = {
    "gdp": (3, "level", "down"), "fspdp": (3, "level", "down"), "gdi": (3, "level", "down"),
    "c": (3, "level", "down"), "dur": (3, "level", "down"), "nondur": (3, "level", "down"),
    "svc": (3, "level", "down"), "bfi": (3, "level", "down"), "str": (3, "level", "down"),
    "equip": (3, "level", "down"), "ipp": (3, "level", "down"), "res": (3, "level", "down"),
    "gov": (3, "level", "down"), "def": (3, "level", "down"), "nondef": (3, "level", "down"),
    "sl": (3, "level", "down"), "x": (3, "level", "down"), "m": (3, "level", "down"),
    "jobs": (1, "level", "down"), "hemp": (1, "level", "down"), "ur": (1, "rate", "up"),
    "ltu": (1, "rate", "up"), "lfpr_prime": (1, "rate_trend", "down"), "claims": (1, "rate", "up"),
    "hours_q": (3, "level", "down"), "hours_m": (1, "level", "down"),
    **{k: (1, "rate_trend", "down") for k in [
        "epop", "epop_prime", "epop_men", "epop_women", "epop_pmen", "epop_pwomen", "epop_1624", "epop_55",
        "epop_white", "epop_black", "epop_hisp", "epop_lths", "epop_hs", "epop_sc", "epop_ba"]},
    "ip": (1, "level", "down"), "inc": (1, "level", "down"), "dpi": (1, "level", "down"),
    "pce_m": (1, "level", "down"), "mts": (1, "level", "down"), "ffr": (1, "rate", "down"),
}

# BEA, quarterly from 1947: real GDP (Table 1.1.6), GDI and final sales to private domestic purchasers
# (1.17.6), and the real quantity index of every component (1.1.3).
BEA_Q = {
    "gdp": ("T10106", "A191RX"), "gdi": ("T11706", "A261RX"), "fspdp": ("T11706", "LB000003"),
    "c": ("T10103", "DPCERA"), "dur": ("T10103", "DDURRA"), "nondur": ("T10103", "DNDGRA"),
    "svc": ("T10103", "DSERRA"), "bfi": ("T10103", "A008RA"), "str": ("T10103", "B009RA"),
    "equip": ("T10103", "Y033RA"), "ipp": ("T10103", "Y001RA"), "res": ("T10103", "A011RA"),
    "gov": ("T10103", "B822RA"), "def": ("T10103", "B824RA"), "nondef": ("T10103", "B825RA"),
    "sl": ("T10103", "B829RA"), "x": ("T10103", "B020RA"), "m": ("T10103", "B021RA"),
}
# BEA, monthly from 1959: real consumer spending (2.8.3), real income excluding transfers and real
# disposable income (2.6).
BEA_M = {"pce_m": ("T20803", "DPCERA"), "inc": ("T20600", "W875RX"), "dpi": ("T20600", "A067RX")}
# BEA Table 1.1.2, contributions to percent change in real GDP.
SIX = ["C", "BFI", "Res", "Inv", "G", "NX"]
CONTRIB = {"C": "DPCERY", "BFI": "A008RY", "Res": "A011RY", "Inv": "A014RY", "G": "A822RY", "NX": "A019RY",
           "Dur": "DDURRY", "Nondur": "DNDGRY", "Svc": "DSERRY", "Str": "A009RY", "Equip": "Y033RY",
           "IP": "Y001RY", "Def": "A824RY", "Nondef": "A825RY", "SL": "A829RY", "X": "A020RY", "M": "A021RY"}
# BLS household survey (Current Population Survey), seasonally adjusted.
LN = {
    "hemp": "LNS12000000", "ur": "LNS14000000", "ltu": "LNS13025703", "lfpr_prime": "LNS11300060",
    "epop": "LNS12300000", "epop_prime": "LNS12300060", "epop_men": "LNS12300001",
    "epop_women": "LNS12300002", "epop_pmen": "LNS12300061", "epop_pwomen": "LNS12300062",
    "epop_1624": "LNS12324887", "epop_55": "LNS12324230", "epop_white": "LNS12300003",
    "epop_black": "LNS12300006", "epop_hisp": "LNS12300009", "epop_lths": "LNS12327659",
    "epop_hs": "LNS12327660", "epop_sc": "LNS12327689", "epop_ba": "LNS12327662",
}


def bea_lines(table: str, codes: list[str], freq: str, dataset: str = "NIPA") -> dict:
    """{code: {t: value}} for several series of one BEA table."""
    df = bea_nipa(table, freq, dataset=dataset, _pace=12)
    out = {}
    for c in codes:
        rows = df[df["code"] == c].drop_duplicates("date").set_index("date")["value"]
        if rows.empty:
            raise RuntimeError(f"BEA {table} has no series {c}")
        out[c] = as_dict(rows)
    return out


def bls_monthly(survey: str, filename: str, sid: str) -> dict:
    df = bls_flat(survey, filename)
    df = df[(df["series_id"] == sid) & df["period"].str.match(r"M(0[1-9]|1[0-2])")]
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values,
                  index=pd.to_datetime(df["year"] + "-" + df["period"].str[1:] + "-01"))
    return as_dict(s)


def bls_quarterly(survey: str, filename: str, sid: str) -> dict:
    df = bls_flat(survey, filename)
    df = df[(df["series_id"] == sid) & df["period"].isin(["Q01", "Q02", "Q03", "Q04"])]
    months = (df["period"].str[2].astype(int) * 3 - 2).astype(str).str.zfill(2)
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values,
                  index=pd.to_datetime(df["year"] + "-" + months + "-01"))
    return as_dict(s)


def load() -> tuple[dict, dict, dict]:
    """({series key: {t: value}} (mts as two unjoined segments), {t: {piece: contribution}}, {t: real GDP})."""
    raw: dict = {}
    for freq, spec in (("Q", BEA_Q), ("M", BEA_M)):
        tables: dict = {}
        for k, (table, code) in spec.items():
            tables.setdefault(table, []).append((k, code))
        for table, pairs in tables.items():
            got = bea_lines(table, [c for _, c in pairs], freq)
            for k, code in pairs:
                raw[k] = got[code]
    got = bea_lines("T10102", list(CONTRIB.values()), "Q")
    contrib: dict = {}
    for name, code in CONTRIB.items():
        for t, v in got[code].items():
            contrib.setdefault(t, {})[name] = v
    contrib = {t: v for t, v in contrib.items() if len(v) == len(CONTRIB)}
    # Real manufacturing and trade sales: two BEA underlying-detail tables on different bases (SIC through
    # 1996 in 1996 dollars, NAICS from 1997 in 2017 dollars). They share no month and are never joined.
    mts_a = bea_lines("U002AU", ["KHPMT"], "M", "NIUnderlyingDetail")["KHPMT"]
    mts_b = bea_lines("U002BU", ["KPMT"], "M", "NIUnderlyingDetail")["KPMT"]
    assert max(mts_a) == ym(1996, 12) and min(mts_b) == ym(1997, 1), "the two sales tables no longer meet at 1996/1997"
    raw["mts"] = [mts_a, mts_b]
    # BLS: payroll jobs and aggregate weekly hours (Current Employment Statistics), hours worked in the
    # nonfarm business sector (productivity), and the household survey.
    raw["jobs"] = bls_monthly("ce", "ce.data.00a.TotalNonfarm.Employment", "CES0000000001")
    raw["hours_m"] = bls_monthly("ce", "ce.data.05c.TotalPrivate.ProductionEmployeeHoursAndEarnings", "CES0500000034")
    raw["hours_q"] = bls_quarterly("pr", "pr.data.1.AllData", "PRS85006033")
    ln = bls_ln(list(LN.values()))
    for k, sid in LN.items():
        raw[k] = as_dict(ln[sid])
    # The Federal Reserve's industrial production (G.17) and federal funds rate (H.15, monthly average),
    # and the Labor Department's weekly initial claims (seasonally adjusted, dated by the week-ending
    # Saturday), all as FRED republishes them unchanged.
    raw["ip"] = as_dict(fred("INDPRO"))
    raw["ffr"] = as_dict(fred("FEDFUNDS"))
    weekly = fred("ICSA", start="1967-01-01")
    by_month = weekly.groupby(to_t(weekly.index)).mean()
    by_month = by_month[by_month.index < max(by_month.index)]          # the last month may be partial
    # claims per 1,000 payroll jobs (jobs are in thousands)
    raw["claims"] = {t: v / raw["jobs"][t] for t, v in by_month.items() if t in raw["jobs"]}
    return raw, contrib, raw["gdp"]


# ── the arithmetic ─────────────────────────────────────────────────────────────────────────────────
def series_for(raw: dict, key: str, rec: dict) -> dict:
    """The data a recession sees: for manufacturing and trade sales, the table holding its peak."""
    x = raw[key]
    if isinstance(x, list):
        step = SERIES[key][0]
        return next((seg for seg in x if rec["peak"][step] in seg), {})
    return x


def run_length(x: dict, a: int, periods: int, step: int) -> int:
    """How many whole periods of unbroken data there are in the `periods` ending at a."""
    n, t = 0, a
    while n < periods and t in x and (t - step) in x:
        n += 1
        t -= step
    return n


def trend(x: dict, step: int, kind: str, rec: dict, baseline: str):
    """(trend per period, periods it was taken over); (None, None) where the baseline has no reading."""
    a = rec["peak"][step]
    if a not in x:
        return None, None
    if baseline == "act" or kind == "rate":
        return 0.0, None
    if not rec["has_trend"]:
        return None, None
    if baseline == "pp":
        if rec["prior"] is None:
            return None, None
        start = rec["prior"][step]
        n = (a - start) // step
        if start not in x or run_length(x, a, n, step) < n:
            return None, None
    else:
        n = run_length(x, a, (10 if baseline == "n10" else 5) * 12 // step, step)
        if n < MIN_YEARS * 12 // step:
            return None, None
    first = x[a - n * step]
    pace = (x[a] / first) ** (1 / n) - 1 if kind == "level" else (x[a] - first) / n
    return pace, n


def gap(x: dict, step: int, kind: str, rec: dict, g: float, k: int):
    a = rec["peak"][step]
    t = a + k * step
    if t not in x:
        return None
    if kind == "level":
        return 100 * ((x[t] / x[a]) / (1 + g) ** k - 1)
    return x[t] - x[a] - k * g


def last_k(x: dict, step: int, rec: dict, cap_months: int | None = None) -> int:
    """The last period after the peak a recession's path reaches: the next recession's peak, the end of
    the data, or `cap_months` past the peak, whichever is first."""
    p = rec["peak"][step]
    end = max(x)
    if rec["next"][step] is not None:
        end = min(end, rec["next"][step])
    if cap_months is not None:
        end = min(end, p + cap_months)
    return (end - p) // step


def scorecard(x: dict, step: int, bad: str, rec: dict) -> dict:
    p = rec["peak"][step]
    t = rec["trough"][step]
    out = {"trough": (t - p) // step if t in x else None, "low": None, "back": None}
    sign = -1 if bad == "up" else 1
    ks = [k for k in range(1, last_k(x, step, rec, LOW_WINDOW_MONTHS) + 1) if p + k * step in x]
    if not ks:
        return out
    low = min(ks, key=lambda k: (sign * (x[p + k * step] - x[p]), k))
    out["low"] = low
    if sign * (x[p + low * step] - x[p]) >= 0:
        out["back"] = 0                                  # it never fell below its peak level
    else:
        out["back"] = next((k for k in range(low + 1, last_k(x, step, rec) + 1)
                            if p + k * step in x and sign * (x[p + k * step] - x[p]) >= 0), None)
    return out


class Contributions:
    """contrib[t][piece] = BEA's contribution to the annualized percent change in real GDP in quarter t."""

    def __init__(self, contrib: dict, gdp: dict):
        self.c, self.gdp = contrib, gdp

    def growth(self, t: int) -> float:                     # quarterly growth of the level, a fraction
        return self.gdp[t] / self.gdp[t - 3] - 1

    def quarter(self, t: int, k: str) -> float:
        """BEA's annual-rate contribution scaled so the six add up to the quarter's growth exactly. When
        the six add up to almost nothing (under 0.2 point at an annual rate) scaling would divide by
        nearly zero: each piece is then a quarter of its annual rate, and the six share what is left in
        proportion to their size."""
        total = sum(self.c[t][s] for s in SIX) / 100
        c = self.c[t][k] / 100
        if abs(total) > 0.002:
            return c * self.growth(t) / total
        if k not in SIX:
            return c / 4
        size = sum(abs(self.c[t][s]) for s in SIX) / 100
        return c / 4 + ((self.growth(t) - total / 4) * abs(c) / size if size else 0.0)

    def compound(self, a: int, k: int):
        """Each piece compounded over the k quarters after a, in fractions of GDP at a; and GDP's ratio."""
        level, cum = 1.0, {p: 0.0 for p in CONTRIB}
        for i in range(1, k + 1):
            t = a + 3 * i
            for p in CONTRIB:
                cum[p] += self.quarter(t, p) * level
            level *= 1 + self.growth(t)
        return cum, level

    def window(self, rec: dict, baseline: str):
        if baseline != "act" and not rec["has_trend"]:
            return None
        a, end = rec["peak"][3], rec["trough"][3]
        if a not in self.gdp or (a + 3) not in self.c or end not in self.c:
            return None
        k = (end - a) // 3
        cum, ratio = self.compound(a, k)
        out = {"quarters": k, "gdp": 100 * (ratio - 1), "trend_growth": None}
        if baseline == "act":
            out["v"] = {p: 100 * cum[p] for p in CONTRIB}
        else:
            if baseline == "pp":
                if rec["prior"] is None:
                    return None
                periods = need = (a - rec["prior"][3]) // 3
            else:
                periods, need = (10 if baseline == "n10" else 5) * 4, MIN_YEARS * 4
            n, t = 0, a
            while n < periods and t in self.c and (t - 3) in self.gdp:
                n += 1
                t -= 3
            if n < need:
                return None
            base, base_ratio = self.compound(a - 3 * n, n)
            share = {p: base[p] / (base_ratio - 1) for p in CONTRIB}   # each piece's share of trend growth
            g = base_ratio ** (1 / n) - 1
            path = (1 + g) ** k                                         # the trend path at the trough
            out["trend_growth"] = 100 * ((1 + g) ** 4 - 1)
            out["v"] = {p: 100 * (cum[p] - share[p] * (path - 1)) / path for p in CONTRIB}
        out["total"] = sum(out["v"][p] for p in SIX)
        return out


# ── run ────────────────────────────────────────────────────────────────────────────────────────────
def main() -> None:
    raw, contrib, gdp = load()
    paces, readings, cards = [], [], []
    for key, (step, kind, bad) in SERIES.items():
        for rec in RECS:
            x = series_for(raw, key, rec)
            if rec["peak"][step] not in x:
                continue
            K = last_k(x, step, rec, LOW_WINDOW_MONTHS)
            card = {"key": f"{key}|{rec['key']}", "series": key, "recession": rec["key"], **scorecard(x, step, bad, rec)}
            sign = -1 if bad == "up" else 1
            for b in BASELINES:
                g, n = trend(x, step, kind, rec, b)
                if b != "act":
                    paces.append({"key": f"{key}|{rec['key']}|{b}", "series": key, "recession": rec["key"],
                                  "baseline": b, "pace": None if g is None else f"{g:.15g}", "periods": n})
                if g is None:
                    continue
                for k in range(-PRE[step], K + 1):
                    v = gap(x, step, kind, rec, g, k)
                    if v is not None:
                        readings.append({"key": f"{key}|{rec['key']}|{b}|{k}", "series": key,
                                         "recession": rec["key"], "baseline": b, "k": k, "gap": v})
                vals = [(sign * v, k) for k in range(1, K + 1) if (v := gap(x, step, kind, rec, g, k)) is not None]
                card[f"low_point_{b}"] = min(vals)[1] if vals else None
            cards.append(card)

    C = Contributions(contrib, gdp)
    rows, contrib_long = [], []
    for rec in RECS:
        for b in BASELINES:
            w = C.window(rec, b)
            if w is None:
                continue
            # ONE SET OF DEFINITIONS: the six add up to real GDP's gap from trend at the trough
            g, _ = trend(gdp, 3, "level", rec, b)
            at_trough = gap(gdp, 3, "level", rec, g, w["quarters"])
            assert abs(at_trough - w["total"]) < 1e-9, (rec["key"], b, at_trough, w["total"])
            rows.append({"key": f"{rec['key']}|{b}", "recession": rec["key"], "baseline": b,
                         "quarters": w["quarters"], "gdp_change": w["gdp"], "trend_growth": w["trend_growth"],
                         **w["v"], "total": w["total"], "gdp_gap_at_trough": at_trough})
            for p, v in w["v"].items():                     # long form, for the nightly comparison
                contrib_long.append({"key": f"{rec['key']}|{b}|{p}", "contribution": v})

    out = {"paces": paces, "readings": readings, "scorecard": cards, "contributions": rows,
           "contributions_long": contrib_long}
    for name, recs in out.items():
        df = pd.DataFrame(recs).set_index("key")
        whole = [c for c in df.columns if c in ("periods", "quarters", "k", "trough", "low", "back") or c.startswith("low_point_")]
        df[whole] = df[whole].astype("Int64")             # periods are whole numbers, blank where there is none
        save(df, HERE, name)
    low = pd.DataFrame(cards).melt(id_vars=["key"], value_vars=[f"low_point_{b}" for b in BASELINES])
    low["key"] = low["key"] + "|" + low["variable"].str[len("low_point_"):]
    low = low.dropna(subset=["value"]).set_index("key")[["value"]].rename(columns={"value": "low_point"})
    save(low.astype("Int64"), HERE, "low_points")

    print(f"{len(paces)} trends, {len(readings):,} gaps from trend, {len(cards)} scorecards, "
          f"{len(rows)} recession-baseline contribution sets (each adds up to GDP's gap at the trough).")
    d = pd.DataFrame(rows).set_index("key")
    print("Real GDP at the trough, percent of trend (10-year trend):")
    for rec in RECS[1:]:
        r = d.loc[f"{rec['key']}|n10"]
        print(f"  {rec['key']}: {r['total']:6.1f}   consumption {r['C']:5.1f}  investment {r['BFI']:5.1f}"
              f"  housing {r['Res']:5.1f}  inventories {r['Inv']:5.1f}  government {r['G']:5.1f}  net exports {r['NX']:5.1f}")


if __name__ == "__main__":
    main()
