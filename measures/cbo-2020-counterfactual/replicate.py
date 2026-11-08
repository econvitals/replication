"""CBO-2020 Counterfactual — rebuilds ten of the 47 series on econvitals.org/tools/cbo-jan2020/.

    python replicate.py            # data as they stood the day the live page was last built
    python replicate.py --latest   # today's data instead

Needs FRED_API_KEY. Writes one CSV per series to output/.

Each series has two lines: what actually happened (from FRED) and CBO's January 2020
projection, put on today's footing by one of four rules:

    "mult"   levels and indexes: CBO's growth path, scaled so 2019 Q4 equals today's data
    "none"   rates: shown exactly as CBO projected them
    "share"  percent of GDP: CBO's component over CBO's own GDP; actual over actual GDP
    "add"    series that cross zero (net exports): CBO's path shifted, not scaled, to 2019 Q4

CBO's projection is the file in inputs/ (CBO's website refuses scripted downloads; see the
README for where it comes from).
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, get, key, published, save  # noqa: E402

ANCHOR = pd.Period("2019Q4")          # the quarter where the CBO line is pinned to the data
WINDOW_START = pd.Period("2018Q1")    # the page starts here

# The page is rebuilt by hand, not every day, while BEA and BLS keep revising the data. So by
# default this script asks FRED for the data as they stood on the day the page was last built
# (FRED keeps every past vintage, "ALFRED"); --latest uses today's data instead.
if "--latest" in sys.argv:
    AS_OF = None
else:
    AS_OF = published("tools/cbo-jan2020/data.json")["meta"]["generated"]
TODAY = pd.Timestamp(AS_OF or pd.Timestamp.today()).normalize()


def fred_series(series_id: str) -> pd.Series:
    """A FRED series from 2014 on: today's vintage, or the one in force on AS_OF."""
    if AS_OF is None:
        return fred(series_id, start="2014-01-01")
    params = {"series_id": series_id, "api_key": key("FRED_API_KEY"), "file_type": "json",
              "observation_start": "2014-01-01", "realtime_start": AS_OF, "realtime_end": AS_OF}
    obs = json.loads(get("https://api.stlouisfed.org/fred/series/observations", params))
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs["observations"]})
    return pd.to_numeric(s, errors="coerce").dropna()


# CBO's January 2020 quarterly projection (and its record of history before 2020).
cbo = pd.read_csv(HERE / "inputs" / "cbo_jan2020_quarterly.csv")
cbo.index = pd.PeriodIndex(cbo.pop("quarter"), freq="Q")

# id on the page -> (CBO column or (numerator, denominator), FRED id, rule, scale on FRED)
SERIES = {
    "gdp_nominal":          ("gdp", "GDP", "mult", 1.0),
    "real_gdp":             ("real_gdp", "GDPC1", "mult", 1.0),
    "core_pce_price_index": ("core_pce_price_index", "PCEPILFE", "mult", 1.0),
    "cpiu":                 ("cpiu", "CPIAUCSL", "mult", 1.0),
    "unemployment":         ("unemployment_rate", "UNRATE", "none", 1.0),
    # CBO did not publish an employment-population ratio; the CBO line is its civilian
    # employment divided by its civilian noninstitutional population (16 and over).
    "epop":                 (("empl_civ_16yo", "population_civ_16yo"), "EMRATIO", "none", 1.0),
    "payrolls":             ("empl_payroll_nf", "PAYEMS", "mult", 1e-3),   # thousands -> millions
    "ten_year":             ("treasury_note_rate_10yr", "GS10", "none", 1.0),
    "compensation_pct_gdp": ("compensation", "W209RC1", "share", 1.0),
    "real_net_exports":     ("real_net_exports", "NETEXC", "add", 1.0),
}


def quarterly_actual(fred_id: str, scale: float) -> pd.Series:
    """A FRED series averaged to quarters, keeping only quarters that are complete.

    A quarter counts once it has ended and, for a monthly series, all three of its months
    are published. (A month missing in the middle of the record, such as October 2025,
    when the government shutdown stopped the CPI and the household survey, just leaves
    the quarter as the average of the months that exist.)
    """
    raw = fred_series(fred_id) * scale
    q = raw.groupby(raw.index.to_period("Q")).mean()
    q = q[q.index.to_timestamp(how="end") <= TODAY]
    months_in_last = raw[raw.index.to_period("Q") == q.index.max()].index.month.nunique()
    monthly = raw.groupby(raw.index.to_period("Q")).size().max() > 1
    if monthly and months_in_last < 3:
        q = q.iloc[:-1]
    return q


def cbo_path(col) -> pd.Series:
    if isinstance(col, tuple):
        num, den = col
        return (cbo[num] / cbo[den] * 100.0).dropna()
    return cbo[col].dropna()


gdp_actual = quarterly_actual("GDP", 1.0)
gdp_cbo = cbo["gdp"]

latest = []
for sid, (col, fred_id, rule, scale) in SERIES.items():
    actual = quarterly_actual(fred_id, scale)
    path = cbo_path(col)
    if rule == "none":
        a, f = actual, path
    elif rule == "mult":
        a, f = actual, path / path[ANCHOR] * actual[ANCHOR]
    elif rule == "add":
        a, f = actual, path - path[ANCHOR] + actual[ANCHOR]
    elif rule == "share":
        a, f = (actual / gdp_actual * 100.0).dropna(), path / gdp_cbo * 100.0
    last = a.dropna().index.max()
    quarters = pd.period_range(WINDOW_START, last, freq="Q")
    out = pd.DataFrame({"actual": a.reindex(quarters),
                        "forecast": f.reindex(quarters).where(quarters >= ANCHOR)})
    out.index = out.index.astype(str)
    out.index.name = "date"
    save(out.round(6), HERE, sid)
    row = out.iloc[-1]
    latest.append((sid, out.index[-1], row["actual"], row["forecast"]))

print("Data as of", AS_OF or "today")
print(pd.DataFrame(latest, columns=["series", "latest", "actual", "CBO Jan 2020"])
      .round(3).to_string(index=False))
