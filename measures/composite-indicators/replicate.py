"""Econvitals Composite Activity and Inflation Indicators — rebuilds the ABSOLUTE half of the
2-by-2 grid and charts on econvitals.org/#surprise (how unusual each indicator's latest reading
is against its own history since 2013). The SURPRISE half needs an archive of consensus
forecasts that is not public; the README explains.

    python replicate.py        # needs FRED_API_KEY; writes output/absolute.csv

Each of fourteen indicators is put on one scale: subtract its typical (median) reading over 2013
to the year before, divide by the typical spread (1.4826 x the median absolute deviation), cap at
4, and flip the unemployment rate so positive always means more activity or more inflation. Each
Friday's index is a weighted average of the readings dated up to 185 days earlier, each weighted
by its theme weight times exp(-age / 45 days), so a fresh reading dominates and an old one fades.

Econvitals rebuilds the index on Friday mornings. Its FRED inputs are the ones posted through the
day before, so a report released that Friday at 8:30 (the jobs report, say) enters the following
week; this script reads FRED as of that Thursday to match. Michigan's tables come direct.
"""
import csv
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import get, key, save  # noqa: E402

START, TAU, CAP_DAYS, CLIP, MIN_OBS = 2013, 45.0, 185, 4.0, 8
TODAY = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
FRIDAY = TODAY - pd.DateOffset(days=(TODAY.weekday() - 4) % 7)    # the latest Friday, today if one
ASOF = (FRIDAY - pd.DateOffset(days=1)).strftime("%Y-%m-%d")      # FRED as it stood the day before

# id: (axis, theme, sign, source, transform). Sources are FRED ids, "a-b-c" for a difference, or
# ("sca", file, column) for the University of Michigan's Surveys of Consumers tables.
INDICATORS = {
    "Nonfarm payrolls":         ("activity", "Labor", +1, "PAYEMS", "diff"),
    "Unemployment rate":        ("activity", "Labor", -1, "UNRATE", "level"),
    "Job openings":             ("activity", "Labor", +1, "JTSJOL", "level"),
    "Real GDP":                 ("activity", "Real activity", +1, "A191RL1Q225SBEA", "level"),
    "Retail control group":     ("activity", "Real activity", +1,
                                 "RSAFS-RSMVPD-RSGASS-RSBMGESD-RSFSDP", "pct"),
    "Personal income":          ("activity", "Real activity", +1, "PI", "pct"),
    "Housing starts":           ("activity", "Real activity", +1, "HOUST", "level"),
    "Consumer sentiment":       ("activity", "Real activity", +1, ("sca", "tbmics.csv", "ICS_ALL"), "level"),
    "Core PCE":                 ("inflation", "Prices", +1, "PCEPILFE", "yoy"),
    "Core CPI":                 ("inflation", "Prices", +1, "CPILFENS", "yoy"),
    "Core PPI":                 ("inflation", "Prices", +1, "PPICOR", "yoy"),
    "Employment cost index":    ("inflation", "Wages & expectations", +1, "ECIALLCIV", "pct"),
    "Average hourly earnings":  ("inflation", "Wages & expectations", +1, "CES0500000003", "yoy"),
    "1-year inflation expectations": ("inflation", "Wages & expectations", +1,
                                      ("sca", "tbmpx1px5.csv", "PX_MD"), "level"),
}


def fred_asof(series_id: str) -> pd.Series:
    """A FRED series as it stood on ASOF (FRED keeps every past vintage)."""
    params = {"series_id": series_id, "api_key": key("FRED_API_KEY"), "file_type": "json",
              "observation_start": "1999-01-01", "realtime_start": ASOF, "realtime_end": ASOF}
    obs = json.loads(get("https://api.stlouisfed.org/fred/series/observations", params))
    if "observations" not in obs:
        raise RuntimeError(f"FRED {series_id}: {obs.get('error_message', obs)}")
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs["observations"]})
    return pd.to_numeric(s, errors="coerce").dropna()


def michigan(filename: str, column: str) -> pd.Series:
    """A Surveys of Consumers monthly table (sca.isr.umich.edu); FRED's copy runs a month late."""
    months = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]
    rows = {}
    for r in csv.DictReader(io.StringIO(get("https://www.sca.isr.umich.edu/files/" + filename))):
        month, year = (r.get("Month") or "").strip(), (r.get("YYYY") or "").strip()
        if month in months and year.isdigit() and (r.get(column) or "").strip():
            rows[pd.Timestamp(int(year), months.index(month) + 1, 1)] = float(r[column])
    return pd.Series(rows).sort_index()


def reading(source, transform: str) -> pd.Series:
    if isinstance(source, tuple):
        return michigan(source[1], source[2])
    first, *minus = source.split("-")
    s = fred_asof(first)
    for m in minus:
        s = (s - fred_asof(m)).dropna()
    # Changes step through the observations as published, as Econvitals' build does. With no
    # October 2025 core CPI, its "12-month" change spans 13 months from November 2025 through
    # October 2026; kept, to match the site (see the README).
    return {"level": s, "diff": s.diff(), "pct": 100 * s.pct_change(),
            "yoy": 100 * (s / s.shift(12) - 1)}[transform].dropna()


def standardized(s: pd.Series, sign: int) -> pd.Series:
    """Each reading against the median and robust spread of 2013 through the prior year."""
    out = {}
    for d, v in s.items():
        window = s[(s.index.year >= START) & (s.index.year < d.year)]
        if len(window) < MIN_OBS:
            continue
        sigma = 1.4826 * (window - window.median()).abs().median()
        if sigma > 0:
            out[d] = sign * float(np.clip((v - window.median()) / sigma, -CLIP, CLIP))
    return pd.Series(out)


# Balanced weights: the two themes on each axis count equally, indicators equally within a theme.
themes = pd.Series({k: (v[0], v[1]) for k, v in INDICATORS.items()})
weight = {k: 1 / (2 * (themes == themes[k]).sum()) for k in INDICATORS}

z = {name: standardized(reading(src, tf), sign)
     for name, (axis, theme, sign, src, tf) in INDICATORS.items()}

grid = pd.date_range("2015-01-02", FRIDAY, freq="W-FRI")
out = pd.DataFrame(index=grid)
for axis in ("activity", "inflation"):
    events = pd.concat([pd.DataFrame({"date": s.index, "z": s.values, "w": weight[n]})
                        for n, s in z.items() if INDICATORS[n][0] == axis])
    values = []
    for t in grid:
        age = (t - events["date"]).dt.days
        live = (age >= 0) & (age <= CAP_DAYS)
        w = events["w"][live] * np.exp(-age[live] / TAU)
        values.append((w * events["z"][live]).sum() / w.sum() if w.sum() > 0 else np.nan)
    out[axis] = values
out.index.name = "date"
save(out, HERE, "absolute")

latest = pd.DataFrame({n: {"latest": z[n].index[-1].date(), "z": round(z[n].iloc[-1], 2)}
                       for n in INDICATORS}).T
print(f"Index through Friday {FRIDAY.date()}, FRED inputs as of {ASOF}. Each indicator's latest reading, in standard deviations:")
print(latest.to_string())
print("\nAbsolute composites:")
print(out.tail(4).round(3).to_string())
