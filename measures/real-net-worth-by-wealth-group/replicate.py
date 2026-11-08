"""Real Net Worth by Wealth Group — rebuilds the chart on econvitals.org/other/#household and
econvitals.org/other/householdfinancedetail/#groups.

    python replicate.py        # needs FRED_API_KEY; writes output/real_net_worth_index.csv

Each wealth group's net worth (Federal Reserve Board, Distributional Financial Accounts) divided by
the quarterly PCE price index, then indexed to the group's own level in 2019 Q4 = 100.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402
from common.finance import dfa_by_wealth_group  # noqa: E402

BASE = pd.Timestamp("2019-10-01")       # 2019 Q4, the quarter before the pandemic

# Net worth of the bottom 50%, next 40%, next 9% and top 1% of households ranked by wealth,
# millions of dollars, nominal. The top 1% is the Board's top 0.1% plus its next 0.9%.
net_worth = dfa_by_wealth_group("Net worth")

# BEA's PCE chain-type price index, quarterly, seasonally adjusted (NIPA table 1.1.4).
pce = fred("PCECTPI")

real = net_worth.div(pce, axis=0).dropna()
index = 100 * real / real.loc[BASE]
index.index.name = "date"
save(index, HERE, "real_net_worth_index")
print(index.tail(4).round(3).to_string())
