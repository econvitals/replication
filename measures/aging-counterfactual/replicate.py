"""Aging Counterfactual — rebuilds the "Aging-Only Counterfactual, Since a Chosen Peak" charts and
the contribution tables beside them on econvitals.org/labor/demographicdetail/#counterfactual.

    python replicate.py        # no key needed; writes output/<rate>_counterfactual_<peak>.csv
                               # and output/<rate>_contributions_<peak>.csv

Start at a business-cycle peak (March 2001, December 2007 or February 2020) and ask where the
participation or employment rate would be today if no age-and-sex group had changed its
behavior since then, given only how the population aged:

    hypothetical(t) = actual(peak) + cumulative composition change from the peak to t
                    = actual(t) - [cumulative behavior(t) - cumulative behavior(peak)]

The gap between actual and hypothetical is the behavior change. The tables split that gap by
age group and sex: each of the 30 age-by-sex cells' behavior contributions, summed over the
months since the peak, then added up into three age groups. The pieces sum exactly to the
total. The month-by-month split itself is in common/labor.py.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.labor import BANDS, chained_decomposition  # noqa: E402

PEAKS = {"2001": "2001-03-01", "2007": "2007-12-01", "2020": "2020-02-01"}
AGE_GROUP = {age: label for band, label in (("16_24", "16-24"), ("25_54", "25-54"),
                                            ("55plus", "55+")) for age in BANDS[band]}

frame, within = chained_decomposition("16plus")
latest = frame.index[-1]

for peak, month in PEAKS.items():
    for rate in ("lfpr", "epop"):
        actual, cumw = frame[f"{rate}_actual"], frame[f"{rate}_cumw"]
        hypothetical = (actual - (cumw - cumw[month])).loc[month:]
        chart = pd.DataFrame({"actual": actual, "hypothetical": hypothetical})
        save(chart.loc[f"{month[:4]}-01-01":], HERE, f"{rate}_counterfactual_{peak}")

        # Contributions since the peak, by cell, then by broad age group x sex.
        since = within[rate].loc[within[rate].index > month].sum()
        table = since.groupby([since.index.map(lambda c: AGE_GROUP[c[1:]]),
                               since.index.str[0].map({"f": "Women", "m": "Men"})]).sum()
        table = table.unstack()[["Women", "Men"]]
        table["Total"] = table.sum(axis=1)
        table.loc["Total"] = table.sum()
        table.index.name = "grp"
        save(table.round(3), HERE, f"{rate}_contributions_{peak}")
        # The same table turned on its side (one row per sex), for checking the column totals.
        save(table.round(3).T.rename_axis("sex"), HERE, f"{rate}_contributions_{peak}_by_sex")

    print(f"since {month[:7]}: participation {frame['lfpr_actual'][latest]:.2f} in "
          f"{latest:%b %Y}; behavior change {frame['lfpr_cumw'][latest] - frame['lfpr_cumw'][month]:+.3f} pp")
