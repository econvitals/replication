"""Real Retail Sales — rebuilds retail sales adjusted for inflation, the figures the Econvitals
retail sales release email quotes ("adjusted for inflation, retail sales were ...").

    python replicate.py        # needs CENSUS_API_KEY; writes output/real_retail.csv

The Census Bureau publishes retail sales in dollars only. The usual shortcut divides them by the
headline consumer price index, but two-thirds of the CPI is services that stores do not sell.
Instead each kind of store is deflated by the CPI prices of what it sells (CATS below), and the
totals are combined month by month with a Törnqvist index on sales shares: each month's price
change for a total is the average of its stores' price changes, weighted by their shares of
sales in that month and the one before. Real sales are nominal sales divided by that price index
(2017 = 100), so they are in millions of 2017 dollars.

Where a kind of store maps to several CPI prices, they are weighted either by fixed shares (a
judgment, stated in CATS) or, where marked "ri", by BLS's relative importance of each price in
December of the year before. Before 2013 the 2012 weights are used. The October 2025 CPI, which
BLS never published, is filled by log-linear interpolation, as Econvitals does.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bls_flat, get, key, save  # noqa: E402
from common.tracking import bls_levels  # noqa: E402

BASE_YEAR = 2017
FALLBACK = "SACL1E"          # core goods: a store whose own prices do not exist yet (pre-1999)
# Econvitals adds each year's December weights by hand when BLS publishes them in February;
# this is the last year it has. Raise it in step, or the two drift apart for one year.
LAST_RI_YEAR = 2025

# Census category -> (label, {CPI item: "ri" | fixed share}). Item codes are BLS's
# (CUSR0000 + code is the seasonally adjusted U.S. index).
CATS = {
    "441": ("Motor vehicles and parts",          {"SETA01": 0.60, "SETA02": 0.30, "SETC": 0.10}),
    "442": ("Furniture and home furnishings",    {"SEHJ": "ri", "SEHH": "ri", "SEHL": "ri"}),
    "443": ("Electronics and appliances",        {"SEHK": "ri", "SERAC": "ri", "SEEEC": "ri"}),
    "444": ("Building materials and garden",     {"SEHM": 1.0}),
    "445": ("Food and beverage stores",          {"SAF11": "ri", "SEFW": "ri"}),
    "446": ("Health and personal care",          {"SAM1": "ri", "SEGB": "ri"}),
    "447": ("Gasoline stations",                 {"SETB": 0.80, "SAF11": 0.10, "SEGA": 0.10}),
    "448": ("Clothing and accessories",          {"SAA": 1.0}),
    "451": ("Sporting goods, hobby, books",      {"SERC": "ri", "SERE": "ri", "SERG": "ri"}),
    "452": ("General merchandise",               {"SACL1E": 0.60, "SAF11": 0.40}),
    "453": ("Miscellaneous stores",              {"SACL1E": 1.0}),
    "454": ("Nonstore retailers",                {"SACL1E": 1.0}),
    "722": ("Food services and drinking places", {"SEFV": "ri", "SEFX": "ri"}),
}
# The control group (what BEA uses for consumer spending): total less autos, gasoline,
# building materials and restaurants.
CONTROL_OUT = ("441", "447", "444", "722")
AGGREGATES = {   # output name -> (Census code of the published total, member stores)
    "total":            ("44X72", list(CATS)),
    "ex_autos":         ("44Y72", [c for c in CATS if c != "441"]),
    "ex_autos_gas":     ("44W72", [c for c in CATS if c not in ("441", "447")]),
    "ex_food_services": ("44000", [c for c in CATS if c != "722"]),
    "control":          ("control", [c for c in CATS if c not in CONTROL_OUT]),
}
ITEMS = sorted({i for _l, m in CATS.values() for i in m} | {FALLBACK})


# ------------------------------------------------------------------------------ data
def marts() -> dict[str, dict[pd.Period, float]]:
    """Census Monthly Retail Trade: seasonally adjusted sales, $ millions, by category."""
    text = get("https://api.census.gov/data/timeseries/eits/marts",
               {"get": "cell_value,data_type_code,category_code,seasonally_adj,time_slot_id",
                "for": "us:1", "time": "from 1992-01", "data_type_code": "SM",
                "seasonally_adj": "yes", "key": key("CENSUS_API_KEY")}, timeout=120)
    df = pd.DataFrame(json.loads(text))
    df.columns = df.iloc[0]
    df = df.iloc[1:].loc[:, ~df.columns.duplicated()]
    out: dict[str, dict] = {}
    for r in df.itertuples(index=False):
        out.setdefault(r.category_code, {})[pd.Period(r.time, "M")] = float(r.cell_value)
    total = out["44X72"]
    out["control"] = {m: total[m] - sum(out[c][m] for c in CONTROL_OUT) for m in total
                      if all(m in out[c] for c in CONTROL_OUT)}
    return out


def fill_gaps(s: pd.Series) -> dict[pd.Period, float]:
    """Log-linear interpolation across missing months inside the series (October 2025)."""
    s = s.dropna().sort_index()
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    return dict(np.exp(np.log(full).interpolate()))


def relative_importance() -> dict[int, dict[str, float]]:
    """{year: {item: December relative importance}} from BLS's CPI bulk "aspect" file."""
    a = bls_flat("cu", "cu.aspect")
    a = a[(a["aspect_type"] == "I") & (a["period"] == "M12") & a["series_id"].str.startswith("CUUR0000")]
    out: dict[int, dict] = {}
    for r in a.itertuples(index=False):
        yr = int(r.year)
        if yr <= LAST_RI_YEAR:
            out.setdefault(yr, {})[r.series_id[8:]] = float(r.value)
    return out


nominal = marts()
levels = bls_levels({"CUSR0000" + i for i in ITEMS})
cpi = {i: fill_gaps(levels["CUSR0000" + i].loc["1992-01":]) for i in ITEMS}
RI = relative_importance()


# ------------------------------------------------------------------------------ construction
def weight(item, w, m: pd.Period):
    if w != "ri":
        return w
    yr = min(max(m.year - 1, min(RI)), max(RI))
    return RI[yr].get(item)


def store_growth(mapping: dict, m: pd.Period):
    """Weighted mean log price change of a store's CPI prices from the month before to m. None
    when a price that has started stops short of m (the month waits for it)."""
    p = m - 1
    if any(cpi[i] and max(cpi[i]) < m for i in mapping):
        return None
    num = den = 0.0
    for item, w in mapping.items():
        s = cpi[item]
        if m in s and p in s:
            wt = weight(item, w, m)
            if wt:
                num += wt * math.log(s[m] / s[p])
                den += wt
    if den:
        return num / den
    s = cpi[FALLBACK]
    return math.log(s[m] / s[p]) if m in s and p in s else None


def index_from_growth(gr: dict) -> dict:
    """Chain monthly log changes into an index with the 2017 average = 100."""
    ks = sorted(gr)
    lvl, out = 0.0, {ks[0] - 1: 0.0}
    for k in ks:
        if k - 1 not in out:                 # a gap restarts the chain
            out, lvl = {k - 1: 0.0}, 0.0
        lvl += gr[k]
        out[k] = lvl
    base = [v for k, v in out.items() if k.year == BASE_YEAR]
    b = sum(base) / len(base) if len(base) == 12 else out[min(out)]
    return {k: 100 * math.exp(v - b) for k, v in out.items()}


months = pd.period_range("1992-02", max(nominal["44X72"]), freq="M")
growth = {c: {} for c in CATS}
for c, (_label, mapping) in CATS.items():
    for m in months:
        g = store_growth(mapping, m)
        if g is not None:
            growth[c][m] = g

cols = {}
for name, (code, members) in AGGREGATES.items():
    g = {}
    for m in months:
        p = m - 1
        if not all(m in growth[c] and m in nominal[c] and p in nominal[c] for c in members):
            continue
        t1 = sum(nominal[c][m] for c in members)
        t0 = sum(nominal[c][p] for c in members)
        g[m] = sum(0.5 * (nominal[c][m] / t1 + nominal[c][p] / t0) * growth[c][m] for c in members)
    price = index_from_growth(g)
    cols[f"real_{name}"] = pd.Series({m: nominal[code][m] / (v / 100) for m, v in price.items()
                                      if m in nominal[code]})
    cols[f"price_{name}"] = pd.Series(price)

df = pd.DataFrame(cols).sort_index()
df.index = df.index.to_timestamp()
df.index.name = "date"
print(save(df.round(4), HERE, "real_retail"))
print(df.tail(3).round(1).to_string())
