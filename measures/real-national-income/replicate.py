"""Real National Income — rebuilds the real national income chart on
econvitals.org/gdp/gdpdetail/#sec-other.

    python replicate.py        # needs FRED_API_KEY; writes output/real_national_income.csv

BEA publishes national income (compensation, profits, rents, interest and proprietors' income,
net of depreciation) only in current dollars. Econvitals divides it by the GDP price index and
shows the growth of the result: the 1-quarter change at an annual rate and the 4-quarter change.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402

START = "2010-01-01"
nominal = fred("NICUR", START)        # national income, $ billions, SAAR (BEA table 1.7.5)
prices = fred("GDPCTPI", START)       # GDP chain-type price index, 2017 = 100 (BEA table 1.1.4)

real = (nominal / prices).dropna()    # an index: only its growth means anything
out = pd.DataFrame({"q1_ann": 100 * ((real / real.shift(1)) ** 4 - 1),
                    "q4_yoy": 100 * (real / real.shift(4) - 1)})
save(out.dropna(how="all"), HERE, "real_national_income")
print(out.tail(4).round(2).to_string())
