"""Ecumenical Underlying Inflation — rebuilds the two ecumenical series on econvitals.org/inflation/.

    python replicate.py        # needs FRED_API_KEY and BEA_API_KEY; writes output/ecumenical_pce.csv
                               # and output/ecumenical_cpi.csv

The ecumenical reading is the median of many underlying-inflation numbers: eight PCE measures
(or seven CPI measures), each at 3-, 6- and 12-month annualized rates, each first put in
PCE-equivalent units by adding its fixed long-run gap to overall PCE inflation. The measures and
the adjustment are built in common/inflation.py; this script takes the median.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import (CPI_WINDOWS, OPTIONAL_PCE, PCE_WINDOWS, annualized,  # noqa: E402
                              cpi_measures, pce_equivalent_adjustments, pce_measures, table_month)

START = "2017-06-01"     # where the published charts' data begin


def ecumenical(measures: dict, windows, optional=()) -> pd.DataFrame:
    """Median of every measure's PCE-equivalent 3-, 6- and 12-month rates, month by month."""
    adj = pce_equivalent_adjustments(measures, windows)
    end = table_month(measures, optional)      # only months every live measure has
    # A measure rebuilt from detail that has not reached the newest month is left out, never guessed.
    measures = {k: v for k, v in measures.items() if k not in optional or end in v.index}
    rates = pd.concat({(name, h): annualized(s, h) + adj[name][0]
                       for name, s in measures.items() for h in (3, 6, 12)}, axis=1)
    # Months the core index exists (the CPI has none for October 2025), from START to `end`.
    core = measures["Core"]
    months = core.index[(core.index >= START) & (core.index <= end)]
    # pandas' median skips a blank: a window that cannot be computed is left out, not filled.
    out = rates.reindex(months).median(axis=1).to_frame("ecumenical")
    # The comparison line on each chart: core inflation over 6 months, in PCE-equivalent units.
    out["core_6m"] = annualized(core, 6).reindex(months) + adj["Core"][0]
    return out


pce = ecumenical(pce_measures(), PCE_WINDOWS, OPTIONAL_PCE).rename(columns={"core_6m": "core_pce_6m"})
cpi = ecumenical(cpi_measures(), CPI_WINDOWS).rename(columns={"core_6m": "pce_equiv_core_cpi_6m"})
save(pce, HERE, "ecumenical_pce")
save(cpi, HERE, "ecumenical_cpi")
print("PCE-based\n", pce.tail(3).round(3).to_string(), "\nCPI-based\n", cpi.tail(3).round(3).to_string())
