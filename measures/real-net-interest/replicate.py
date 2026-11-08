"""Real Net Interest — rebuilds the real net interest series on econvitals.org/fiscal/ and in the
Fiscal Explorer.

    python replicate.py      # needs FRED_API_KEY; writes output/real_net_interest.csv

Part of the interest the government pays only compensates lenders for expected inflation. Real
net interest strips that part out, fiscal year by fiscal year:

    real net interest[t] = net interest[t] - expected inflation[t] x debt held by the public[t-1]

Expected inflation is proxied by the trailing five-year growth of the core PCE price index, from
the third quarter (when the fiscal year ends) five years earlier to the third quarter of year t.
Past quarters are BEA's; future quarters grow BEA's latest level at CBO's projected rate.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.cbo import fiscal_year_gdp, fred_as_of, read_input, treasury_year_end  # noqa: E402
from common.econdata import save  # noqa: E402

# The day the published series was built. BEA revises GDP and core PCE prices, so both are
# taken as FRED published them that day; move this date when the series is rebuilt.
VINTAGE = "2026-11-01"
YEARS = range(1995, 2037)

# ------------------------------------------------------------- 1. expected inflation
monthly = fred_as_of("PCEPILFE", VINTAGE, start="1990-01-01")   # core PCE price index, 2017=100
by_q = monthly.groupby(monthly.index.to_period("Q"))
core = by_q.mean()[by_q.size() == 3]                             # complete quarters only
last = core.index.max()
cbo_q = read_input(HERE, "cbo_core_pce_projection_2026-02.csv")["core_pce_index"]
cbo_q.index = pd.PeriodIndex(cbo_q.index, freq="Q")
# Splice: from the last quarter BEA has published, grow BEA's level at CBO's projected rate.
future = cbo_q[cbo_q.index > last] * core[last] / cbo_q[last]
core = pd.concat([core, future])
expected = pd.Series({t: (core[pd.Period(f"{t}Q3")] / core[pd.Period(f"{t - 5}Q3")]) ** 0.2 - 1
                      for t in YEARS}, name="expected_inflation")

# ------------------------------------------------------------- 2. net interest and debt, $ billions
hist = read_input(HERE, "cbo_historical_budget_data_2026-02.csv")   # 1990-2024
proj = read_input(HERE, "cbo_budget_projections_2026-02.csv")       # 2025-2036 (2025 actual)
ni = pd.concat([hist["net_interest"], proj["net_interest"]])
debt = pd.concat([hist["debt_held_public"], proj["debt_held_public"]])
# A fiscal year Treasury has closed that CBO still projects (fiscal 2026): Treasury's figures.
for y in range(2026, 2037):
    actual = treasury_year_end(y, as_of=VINTAGE)
    if actual is None:
        break
    ni.loc[y], debt.loc[y] = actual["net_interest"], actual["debt_held_public"]

# ------------------------------------------------------------- 3. fiscal-year GDP, $ billions
gdp = fiscal_year_gdp(VINTAGE)                                       # BEA, completed years
gdp = pd.concat([gdp, proj.loc[proj.index > gdp.index.max(), "gdp"]])   # CBO after that

# ------------------------------------------------------------- 4. real net interest
years = list(YEARS)
prior_debt = debt.loc[[y - 1 for y in years]].values
real = ni.loc[years] - expected.loc[years] * prior_debt
out = pd.DataFrame({"net_interest": ni.loc[years], "debt_end_of_prior_year": prior_debt,
                    "expected_inflation_pct": 100 * expected.loc[years], "real_net_interest": real,
                    "gdp": gdp.loc[years]})
out["net_interest_pct"] = 100 * out["net_interest"] / out["gdp"]
out["real_net_interest_pct"] = 100 * out["real_net_interest"] / out["gdp"]
out.index = pd.to_datetime([f"{y}-01-01" for y in years])
out.index.name = "date"
save(out, HERE, "real_net_interest")
print(f"Core PCE from BEA through {last}, CBO's projected growth after.")
print(out[["expected_inflation_pct", "net_interest_pct", "real_net_interest_pct"]]
      .iloc[[0, -12, -11, -10, -1]].round(3).to_string())
