"""Core PCE ex Housing and Used Vehicles — rebuilds the chart on econvitals.org/inflation/pcedetail/.

    python replicate.py        # needs BEA_API_KEY; writes output/core_pce_ex_housing_used.csv

BEA publishes core PCE excluding housing but not a version that also strips out used vehicles.
This removes used motor vehicles from BEA's core-ex-housing price index month by month with a
Törnqvist chain (the formula is in common/inflation.py, core_pce_ex_housing_used_vehicles):

    s_t        = used-vehicle spending / (core PCE spending - housing spending)
    s̄          = average of last month's and this month's s
    Δln(index) = [Δln(core PCE ex housing) - s̄ · Δln(used-vehicle prices)] / (1 - s̄)

BEA series (all monthly): table 2.8.4 IA001176 (PCE excluding food, energy, and housing);
table 2.4.4U DNPVRG (price of net purchases of used motor vehicles); table 2.4.5U DNPURC + DUTRRC
(spending on used autos and used light trucks), DPCCRC (PCE excluding food and energy) and
DHSGRC (housing). Rebuilt from the current BEA vintage, so revisions flow through.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import annualized, core_pce_ex_housing_used_vehicles  # noqa: E402

index = core_pce_ex_housing_used_vehicles()
out = index.to_frame("index")
out["chg_1m_ann"] = annualized(index, 1)     # 1-month change, annual rate (the chart's bars)
out["chg_3m_ann"] = annualized(index, 3)     # 3-month change, annual rate (the chart's line)
save(out, HERE, "core_pce_ex_housing_used")
print(out.tail(4).round(3).to_string())
