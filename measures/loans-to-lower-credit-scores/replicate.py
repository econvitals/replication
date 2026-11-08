"""Loans to Lower Credit Scores — rebuilds the chart on
econvitals.org/other/householdfinancedetail/#housing.

    python replicate.py        # no key needed; writes output/loans_under_660.csv

The share of new mortgage and auto loan money going to borrowers with credit scores below 660:
origination volume in the two bands below 660 (under 620, and 620 to 659) over total originations,
from the New York Fed's Household Debt and Credit Report.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.finance import hhdc_sheet, hhdc_workbook  # noqa: E402

# The report's workbook: "Page 6 Data" is mortgage origination volume by credit score,
# "Page 8 Data" is auto loan origination volume by credit score, both billions of dollars.
shares = {}
for sheet, name in (("Page 6 Data", "mortgage_under660"), ("Page 8 Data", "auto_under660")):
    t = hhdc_sheet(sheet)[["<620", "620-659", "TOTAL"]].dropna()
    t = t[t["TOTAL"] > 0]
    shares[name] = 100 * (t["<620"] + t["620-659"]) / t["TOTAL"]

out = pd.DataFrame(shares)            # mortgages start in 2003 Q1, auto loans in 2004 Q1
out.index.name = "date"
save(out, HERE, "loans_under_660")
print(f"Household Debt and Credit Report, {hhdc_workbook()[0]}")
print(out.tail(4).round(3).to_string())
