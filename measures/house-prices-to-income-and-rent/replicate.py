"""House Prices Relative to Income and Rent — rebuilds the chart on
econvitals.org/other/householdfinancedetail/#housing.

    python replicate.py        # needs FRED_API_KEY; writes output/house_price_ratios.csv

Two ratios, each rebased so that January 2000 = 100:
  price to income = FHFA purchase-only house price index / disposable personal income per person
  price to rent   = FHFA purchase-only house price index / CPI for rent of primary residence
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402

BASE = pd.Timestamp("2000-01-01")

# FHFA purchase-only house price index, U.S., monthly, seasonally adjusted (Jan 1991 = 100).
hpi = fred("HPIPONM226S")
# BEA disposable personal income per capita, current dollars, monthly, SAAR (NIPA table 2.6).
dpi = fred("A229RC0")
# BLS CPI-U rent of primary residence, seasonally adjusted (series CUSR0000SEHA).
rent = fred("CUSR0000SEHA")


def rebased_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    ratio = (num / den).dropna()
    return 100 * ratio / ratio.loc[BASE]


out = pd.DataFrame({"price_to_income": rebased_ratio(hpi, dpi),
                    "price_to_rent": rebased_ratio(hpi, rent)})
out.index.name = "date"
save(out, HERE, "house_price_ratios")
print(out.tail(4).round(3).to_string())
