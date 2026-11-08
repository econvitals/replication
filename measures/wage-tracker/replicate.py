"""Econvitals Underlying Unit Labor Costs — rebuilds the chart at econvitals.org/labor/#wages
(also the tile under the wage table on the home page).

    python replicate.py        # needs FRED_API_KEY; writes output/wage_pce_equivalent.csv

Five wage gauges, each put in "PCE-inflation-equivalent" units and averaged, then lowered by how
much faster productivity has grown since 2019 than it did in 2007-2019:

  1. Each gauge as its 12-month (or four-quarter) percent change. A quarterly gauge is placed on
     the last month of its quarter and carried forward up to five months, until the next print.
  2. Each gauge minus its own average gap to PCE inflation over 2007-2019, so all five read as
     "the PCE inflation rate this pace of wage growth would have meant in 2007-2019."
  3. A weighted average of whichever gauges are available that month, with weights equal to one
     over each gauge's variance since 2007 (the steadier gauges count more). The line ends at the
     latest month that has a monthly gauge.
  4. From 2022 Q1 on, minus (trend productivity growth - its 2007-2019 pace), where trend growth
     is the annualized growth of output per hour from 2019 Q4 to that quarter and the 2007-2019
     pace is 2006 Q4 to 2019 Q4. The adjustment is zero before 2022.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402
from common.labor import atlanta_fed_wage_tracker  # noqa: E402

MONTHS = pd.date_range("1980-01-01", date.today(), freq="MS")
CARRY = 5                               # months a quarterly print is carried forward


def yoy(s: pd.Series) -> pd.Series:
    """Percent change from the same date a year earlier, matched by date, so a missing
    observation (median weekly earnings has no 2025 Q4) gives a blank, not a 5-quarter change."""
    return 100 * (s / s.shift(freq=pd.DateOffset(years=1)) - 1).reindex(s.index)


def quarterly_on_months(s: pd.Series, carry: int = CARRY) -> pd.Series:
    """A quarterly series (dated at the quarter's first month, as FRED does) placed on the
    quarter's last month and carried forward `carry` months."""
    s = s.dropna().copy()
    s.index = s.index + pd.DateOffset(months=2)
    s = s.reindex(MONTHS)
    return s.ffill(limit=carry) if carry else s


# 1. The five gauges, each as a 12-month change, on a monthly calendar.
ahe_all = yoy(fred("CES0500000003"))    # average hourly earnings, all private employees (2006+)
ahe_pns = yoy(fred("AHETPI"))           # ... production and nonsupervisory employees (longer)
quarterly = {
    "ECI_wages": yoy(fred("ECIWAG")),          # Employment Cost Index, wages and salaries, private
    "COMP_hour": yoy(fred("COMPNFB")),         # nonfarm business compensation per hour
    "MUWE": yoy(fred("LEU0252881500Q")),       # median usual weekly earnings, full-time workers
}
gauges = pd.DataFrame({
    "ECI_wages": quarterly_on_months(quarterly["ECI_wages"]),
    "WGT_overall": atlanta_fed_wage_tracker().reindex(MONTHS),   # already a 12-month change
    "AHE_spliced": ahe_all.combine_first(ahe_pns).reindex(MONTHS),
    "COMP_hour": quarterly_on_months(quarterly["COMP_hour"]),
    "MUWE": quarterly_on_months(quarterly["MUWE"]),
})
pce = yoy(fred("PCEPI")).reindex(MONTHS)        # PCE price index, 12-month change

# 2. PCE-equivalent units: subtract each gauge's average 2007-2019 gap to PCE inflation.
gap = gauges.sub(pce, axis=0).loc["2007-01-01":"2019-12-01"].mean()
norm = gauges - gap

# 3. Inverse-variance weighted average over the gauges present each month. As on the site, the
#    variance runs from 2007 to the current calendar month, carried-forward quarterly values
#    included, so the weights drift slightly as months pass (see README, "How close").
w = 1 / norm.loc["2007-01-01":].std() ** 2
composite = norm.mul(w).sum(axis=1, min_count=1) / norm.notna().mul(w).sum(axis=1)
composite = composite.where(norm[["WGT_overall", "AHE_spliced"]].notna().any(axis=1))

# 4. The productivity adjustment, in percentage points, from 2022 Q1.
oph = fred("OPHNFB")                    # nonfarm business output per hour (quarterly index)
q = oph.groupby(oph.index.to_period("Q")).mean()
peak, b0, b1 = pd.Period("2019Q4"), pd.Period("2006Q4"), pd.Period("2019Q4")
bench = (q[b1] / q[b0]) ** (4 / (b1 - b0).n) - 1
adj_q = pd.Series({p: 0.0 if p < pd.Period("2022Q1")
                   else 100 * ((v / q[peak]) ** (4 / (p - peak).n) - 1 - bench)
                   for p, v in q.items()})
adj_q.index = adj_q.index.to_timestamp() + pd.DateOffset(months=2)       # quarter's last month
adj = adj_q.reindex(MONTHS.union(adj_q.index)).ffill().reindex(MONTHS).fillna(0.0)

# The published table: the headline, the line before the adjustment, and each gauge's dot on the
# same adjusted basis (a quarterly gauge only on its own quarter-end month).
out = pd.DataFrame({"value": composite - adj, "unadjusted": composite})
for k in gauges:
    dot = norm[k] - adj
    if k in quarterly:
        printed = quarterly_on_months(quarterly[k], carry=0).notna()
        dot = dot.where(printed)
    out[k] = dot
out["productivity_adjustment"] = adj
out = out.dropna(subset=["value"]).loc["2007-01-01":]

save(out, HERE, "wage_pce_equivalent")
print("weights (share):", (w / w.sum()).round(3).to_dict())
print(out[["value", "unadjusted", "productivity_adjustment"]].tail(4).round(3).to_string())
