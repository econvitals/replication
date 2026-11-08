"""Core Services CPI ex Shelter — rebuilds Econvitals' aggregate behind the CPI row of the
PCE-equivalent table on econvitals.org/inflation/#underlying.

    python replicate.py        # no key needed; writes output/core_services_cpi_ex_shelter.csv

BLS's "services less rent of shelter" still contains energy services. This takes BLS's core
services index (services less energy services) and strips out the whole shelter index, month by
month, using BLS's relative-importance weights (common/inflation.py, core_services_cpi_ex_shelter):

    growth_t = [H · (B_t / B_t-1 - 1) - I · (C_t / C_t-1 - 1)] / (H - I)

where B is core services, C is shelter, and H and I are their relative-importance weights in the
previous month. BLS publishes those weights monthly only from March 2012, so January 1990 to
March 2012 is Econvitals' recorded history (inputs/cses_index_1990_2012.csv) and the rebuilt
series is joined to its March 2012 level.

BLS series (seasonally adjusted indexes; weights on the not-seasonally-adjusted twins):
CUSR0000SASLE services less energy services, CUSR0000SAH1 shelter; relative importance of
CUUR0000SASLE and CUUR0000SAH1. All from BLS's public bulk files (download.bls.gov).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import annualized, core_services_cpi_ex_shelter  # noqa: E402

index = core_services_cpi_ex_shelter()
out = index.asfreq("MS").to_frame("index")
out["chg_1m_ann"] = annualized(index, 1)
out["chg_3m_ann"] = annualized(index, 3)
out["chg_12m"] = annualized(index, 12)
save(out.dropna(how="all"), HERE, "core_services_cpi_ex_shelter")   # October 2025 has no CPI
print(out.tail(4).round(3).to_string())
