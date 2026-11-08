# Real Net Worth by Wealth Group

**On econvitals.org:** [Other › Household Finance](https://econvitals.org/other/#household) and [Household finance detail › Wealth and Debt by Group](https://econvitals.org/other/householdfinancedetail/#groups), the chart “Real Net Worth by Wealth Group.” Method note: [Methods](https://econvitals.org/methods/#real-net-worth-by-wealth-group).

**What it is.** The Federal Reserve Board’s Distributional Financial Accounts split household net worth among wealth groups: the bottom 50 percent, the next 40 percent, the next 9 percent and the top 1 percent of households ranked by wealth (the top 1 percent is the sum of the Board’s top 0.1 percent and next 0.9 percent). Econvitals deflates each group’s net worth in dollars by BEA’s quarterly PCE price index and indexes it to its own level in the fourth quarter of 2019 = 100, so each line shows how much that group’s wealth has grown, after inflation, since just before the pandemic.

The groups are fixed shares of households ranked by wealth, not the same households over time. The accounts cover households only — about 95 percent of the household-and-nonprofit sector in the Financial Accounts — and are revised with each quarterly release.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY` for the price index; the Board’s file needs no key). Writes `output/real_net_worth_index.csv`.

**Data.**

- The Board’s Distributional Financial Accounts, the single zip file at [federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip](https://www.federalreserve.gov/releases/z1/dataviz/download/zips/dfa.zip) (from the [DFA page](https://www.federalreserve.gov/releases/z1/dataviz/dfa/)). The script reads `dfa-networth-levels.csv`, column “Net worth” (millions of dollars, nominal), rows `Bottom50`, `Next40`, `Next9`, and `RemainingTop1` plus `TopPt1` for the top 1 percent. FRED republishes the same four series as `WFRBLB50107`, `WFRBLN40080`, `WFRBLN09053` and `WFRBLT01026`.
- FRED `PCECTPI` — BEA’s PCE chain-type price index, quarterly, seasonally adjusted (NIPA table 1.1.4).

**How close.** Reproduces the published series exactly: checked every night over the last 60 quarters to within 0.001 index point (the site rounds to three decimals). The Board restates the whole history with each quarterly release, so for a day or so after a new release the site and this script can be on different vintages; that shows up as a mismatch across many quarters at once and clears when the site refreshes.
