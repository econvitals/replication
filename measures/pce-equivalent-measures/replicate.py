"""PCE-Equivalent Inflation Measures — rebuilds the two adjusted tables on econvitals.org/inflation/#underlying.

    python replicate.py        # needs FRED_API_KEY and BEA_API_KEY; writes output/adjusted_pce.csv,
                               # output/adjusted_cpi.csv and output/adjustments.csv

Every inflation measure runs at its own average level. For each one, the "Adj." column is the
fixed number of percentage points that makes its long-run average equal overall PCE inflation's:

    Adj. = average annual PCE inflation - average annual inflation of the measure, over the window

The window is January 1996 to January 2020 for the CPI measures and January 1977 to January 2020
for the PCE measures (from January 1987 for market-based core and median PCE, whose data start
later). Each table row is then the measure's 1-, 3-, 6- and 12-month annualized rate plus Adj.,
for the newest month every measure has. The measures themselves are built in common/inflation.py.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import (CPI_WINDOWS, OPTIONAL_PCE, PCE_WINDOWS, annualized,  # noqa: E402
                              cpi_measures, pce_equivalent_adjustments, pce_measures, table_month)


def adjusted_table(measures: dict, windows, optional=()):
    adj = pce_equivalent_adjustments(measures, windows)
    end = table_month(measures, optional)
    rows = []
    for name, s in measures.items():
        if name in optional and end not in s.index:
            continue                  # a row that has not reached the table month is dropped, not carried
        row = {"label": name, "delta": adj[name][0]}
        for h in (1, 3, 6, 12):
            row[f"h{h}"] = annualized(s, h).get(end) + adj[name][0]
        rows.append(row)
    table = pd.DataFrame(rows).set_index("label")
    windows_used = pd.DataFrame([{"measure": k, "adjustment": a, "window_start": w[0][:7],
                                  "window_end": w[1][:7]} for k, (a, w) in adj.items()])
    return table, windows_used, end


pce, pce_w, pce_end = adjusted_table(pce_measures(), PCE_WINDOWS, OPTIONAL_PCE)
cpi, cpi_w, cpi_end = adjusted_table(cpi_measures(), CPI_WINDOWS)
save(pce, HERE, "adjusted_pce")
save(cpi, HERE, "adjusted_cpi")
save(pd.concat([pce_w.assign(basis="PCE"), cpi_w.assign(basis="CPI")]).set_index(["basis", "measure"]),
     HERE, "adjustments")
print(f"PCE, PCE-equivalent, {pce_end:%B %Y}\n", pce.round(2).to_string())
print(f"CPI, PCE-equivalent, {cpi_end:%B %Y}\n", cpi.round(2).to_string())
