"""Release-Day Estimate — rebuilds median and trimmed-mean CPI and PCE from the agencies' detail.

    python replicate.py        # needs BEA_API_KEY and FRED_API_KEY; CPI detail from BLS bulk files

On econvitals.org: the trimmed-mean and median charts on Inflation › CPI and › PCE, the CPI and
PCE detail pages, and the asterisked rows of the inflation tables. The Cleveland Fed (median
CPI, 16% trimmed-mean CPI, median PCE) and the Dallas Fed (trimmed-mean PCE) publish these hours
or a day after BLS and BEA. Econvitals rebuilds each from the 8:30 a.m. component detail with
the banks' published recipes, shows the rebuild for the newest month only, and replaces it with
the bank's figure when that posts.

This script rebuilds all four for every month since 2015 and writes, for each, the 1-month
change at an annual rate (the charts' bars) and the 3-month change at an annual rate (their
line), beside the bank's own figure:

  * CPI (Cleveland Fed): 45 components, each one's 1-month change in its seasonally adjusted
    index (the four regional owners' equivalent rent indexes, which BLS publishes unadjusted,
    are adjusted here); weights are the Cleveland Fed's current component weights rolled back
    through history with each component's unadjusted index. Median = the change at the 50th
    percentile of the weight distribution; trimmed mean = drop 8% of the weight from each end.
  * PCE (Dallas Fed): BEA's 177 components (inputs/dallas_trimmed_mean_components.csv), each
    weighted by its Fisher spending share across the two months; drop the lowest 24% and the
    highest 31% of the weight. The median PCE estimate is the 50th percentile of the same
    distribution (the Cleveland Fed's own component set differs a little).
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_wide, fred, get, save  # noqa: E402
from common.tracking import bls_levels, mom, seasonal_adjust, trimmed_mean, weighted_median  # noqa: E402

START = "2015-01"
CLEVELAND_WEIGHTS = ("https://www.clevelandfed.org/-/media/files/webcharts/mediancpi/"
                     "mediancpi_component_table.csv?sc_lang=en")
CLEVELAND_MEDIAN_PCE = ("https://www.clevelandfed.org/-/media/files/webcharts/medianpce/"
                        "median-pce-full-history.csv")


def as_period(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = s.index.to_period("M")
    return s


# ------------------------------------------------------------------------------ CPI
comp = pd.read_csv(HERE / "inputs" / "cleveland_median_cpi_components.csv")
national = [s for s in comp["bls_series"] if s[4:8] == "0000"]
L = bls_levels(set(national) | {"CUUR" + s[4:] for s in national})
for s in comp["bls_series"]:                  # the four regional OER indexes, from FRED
    if s not in L:
        L[s] = as_period(fred(s))

anchor = pd.read_csv(io.StringIO(get(CLEVELAND_WEIGHTS)))
anchor = dict(zip(anchor["Component"], anchor["Relative Importance (Normalized)"].astype(float)))
change, weight = {}, {}
for c in comp.itertuples():
    lvl = L[c.bls_series].loc[START:]
    if c.adjust_here == "yes":                # BLS publishes regional OER unadjusted only
        lvl = seasonal_adjust(lvl, START)     # the stand-in; see README on X-13
    change[c.component] = mom(lvl) / 100
    weight[c.component] = L["CUUR" + c.bls_series[4:]].loc[START:]
change, weight = pd.DataFrame(change), pd.DataFrame(weight)
t0 = weight.dropna().index[-1]
weight = weight * pd.Series({n: anchor[n] / weight.at[t0, n] for n in weight.columns})

cpi = {}
for t in change.index:
    ok = change.loc[t].notna() & weight.loc[t].notna() if t in weight.index else None
    if ok is None or ok.sum() < 43:           # a month needs at least 43 of the 45 components
        continue
    x, w = change.loc[t, ok].values, weight.loc[t, ok].values
    cpi[t] = (100 * weighted_median(x, w), 100 * trimmed_mean(x, w, 0.08, 0.08))
cpi = pd.DataFrame(cpi, index=["median_cpi", "trimmed_mean_cpi"]).T   # 1-month % change


# ------------------------------------------------------------------------------ PCE
def bea_table(name: str) -> pd.DataFrame:
    years = ",".join(str(y) for y in range(int(START[:4]), pd.Timestamp.today().year + 1))
    return as_period(bea_wide(name, "M", years, dataset="NIUnderlyingDetail"))


dallas = pd.read_csv(HERE / "inputs" / "dallas_trimmed_mean_components.csv")
lines = sorted(set(dallas["bea_line"]))
price = bea_table("U20404")[lines]                # price indexes by product
spend = bea_table("U20405")[lines]                # spending by product, current dollars
qty = spend / price
pce = {}
for t in price.index[1:]:
    t1 = t - 1
    p_chg = price.loc[t] / price.loc[t1] - 1
    a, b = qty.loc[t] * price.loc[t1], qty.loc[t1] * price.loc[t1]   # Fisher shares
    if p_chg.isna().any() or a.isna().any() or b.isna().any():
        continue
    w = 0.5 * a / a.sum() + 0.5 * b / b.sum()
    pce[t] = (100 * weighted_median(p_chg.values, w.values),
              100 * trimmed_mean(p_chg.values, w.values, 0.24, 0.31))
pce = pd.DataFrame(pce, index=["median_pce", "trimmed_mean_pce"]).T   # 1-month % change


# ------------------------------------------------------------------------------ the banks' own
med_pce = pd.read_csv(io.StringIO(get(CLEVELAND_MEDIAN_PCE)))
med_pce = pd.Series(pd.to_numeric(med_pce.iloc[:, 1], errors="coerce").values,
                    index=pd.to_datetime(med_pce.iloc[:, 0], format="%m/%d/%Y").dt.to_period("M"))
official = {
    "median_cpi": as_period(fred("MEDCPIM157SFRBCLE")),            # 1-month % change
    "trimmed_mean_cpi": as_period(fred("TRMMEANCPIM157SFRBCLE")),
    "median_pce": med_pce.dropna(),
    # the Dallas Fed publishes a 1-month change at an annual rate; put it back on the month
    "trimmed_mean_pce": (((1 + as_period(fred("PCETRIM1M158SFRBDAL")) / 100) ** (1 / 12) - 1) * 100),
}


def annual(monthly: pd.Series, n: int) -> pd.Series:
    """n-month change at an annual rate, compounding 1-month changes (in %)."""
    growth = (1 + monthly / 100).rolling(n).apply(np.prod, raw=True)
    return (growth ** (12 / n) - 1) * 100


rows = []
for name, ours in pd.concat([cpi, pce], axis=1).items():
    ours = ours.dropna()
    ours = ours.reindex(pd.period_range(ours.index.min(), ours.index.max(), freq="M"))
    bank = official[name].reindex(ours.index)
    out = pd.DataFrame({"chg_1m_ann": annual(ours, 1), "chg_3m_ann": annual(ours, 3),
                        "official_1m": bank, "ours_1m": ours})
    # The Dallas Fed rounds its published rate to two decimals; compare in its own units.
    out["official_1m_ann"] = annual(bank, 1) if name != "trimmed_mean_pce" else \
        as_period(fred("PCETRIM1M158SFRBDAL")).reindex(ours.index)
    out.index = out.index.to_timestamp()
    out.index.name = "date"
    save(out, HERE, name.replace("_", "-"))
    d = (out["ours_1m"] - out["official_1m"]).dropna()
    rows.append((name, len(d), d.abs().mean(), d.tail(24).abs().max()))

print("rebuild against the bank's own figure, 1-month change (not annualized), percentage points:")
for name, n, avg, worst in rows:
    print(f"  {name:18} {n} months, average difference {avg:.4f}; worst of the last 24 months {worst:.4f}")
