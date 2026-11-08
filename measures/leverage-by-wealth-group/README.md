# Household Leverage by Wealth Group

**On econvitals.org:** [Household finance detail › Wealth and Debt by Group](https://econvitals.org/other/householdfinancedetail/#groups), the chart “Household Debt Relative to Assets, by Wealth Group.” Method note: [Methods](https://econvitals.org/methods/#leverage-by-wealth-group).

**What it is.** Each wealth group’s total liabilities — mortgages, consumer credit and other debt — as a percent of its total assets, from the Federal Reserve Board’s Distributional Financial Accounts, for the bottom 50 percent, the next 40 percent, the next 9 percent and the top 1 percent of households ranked by wealth. A higher number means a group carries more debt for each dollar it owns. Both sides are in the same dollars, so the ratio needs no price deflator.

The groups are fixed shares of households ranked by wealth, not the same households over time; the accounts are revised with each quarterly release.

**Run it.** `python replicate.py` (no key needed). Writes `output/leverage_by_group.csv`.

**Data.** The Board’s Distributional Financial Accounts, the single zip file at [federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip](https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip) (from the [DFA page](https://www.federalreserve.gov/releases/z1/dataviz/dfa/)). The script reads `dfa-networth-levels.csv`, columns “Liabilities” and “Assets” (millions of dollars), rows `Bottom50`, `Next40`, `Next9`, and `RemainingTop1` plus `TopPt1` for the top 1 percent. The top 1 percent’s liabilities and assets are each summed across its two rows before dividing.

**How close.** Reproduces the published series exactly: checked every night over the last 60 quarters to within 0.001 percentage point (the site rounds to three decimals). The Board restates the whole history with each quarterly release, so for a day or so after a new release the site and this script can be on different vintages.
