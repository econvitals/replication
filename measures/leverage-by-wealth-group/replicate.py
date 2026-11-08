"""Household Leverage by Wealth Group — rebuilds the chart on
econvitals.org/other/householdfinancedetail/#groups.

    python replicate.py        # no key needed; writes output/leverage_by_group.csv

Each wealth group's total liabilities as a percent of its total assets, from the Federal Reserve
Board's Distributional Financial Accounts. Both are in the same nominal dollars, so no deflator.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.finance import dfa_by_wealth_group  # noqa: E402

# Bottom 50%, next 40%, next 9% and top 1% of households ranked by wealth, millions of dollars.
# The top 1% is the Board's top 0.1% plus its next 0.9%, summed before dividing.
liabilities = dfa_by_wealth_group("Liabilities")
assets = dfa_by_wealth_group("Assets")

leverage = 100 * liabilities / assets
leverage.index.name = "date"
save(leverage, HERE, "leverage_by_group")
print(leverage.tail(4).round(3).to_string())
