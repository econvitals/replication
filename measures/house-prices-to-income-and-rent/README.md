# House Prices Relative to Income and Rent

**On econvitals.org:** [Household finance detail › Housing](https://econvitals.org/other/householdfinancedetail/#housing), the chart “House Prices Relative to Income and to Rents” (the price-to-income row of that page’s Housing table is the same arithmetic). Method note: [Methods](https://econvitals.org/methods/#house-prices-to-income-and-rent).

**What it is.** Two ratios that say whether house prices have outrun what households earn and what it costs to rent a home. Each divides the Federal Housing Finance Agency’s purchase-only house price index (monthly, seasonally adjusted) by a yardstick — BEA’s disposable personal income per person for the first, the BLS consumer price index for rent of primary residence for the second — and rebases the result so that January 2000 = 100. A reading of 150 means house prices have risen 50 percent more than incomes, or than rents, since 2000.

The base year is a convention: the level says how far each ratio has moved since 2000, not whether houses are over- or undervalued. FHFA’s index covers single-family homes bought with conforming mortgages, not the whole market.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). Writes `output/house_price_ratios.csv`.

**Data.** Three FRED series, each republished unchanged from its agency:

- `HPIPONM226S` — FHFA purchase-only house price index, United States, monthly, seasonally adjusted (FHFA’s own master file gives the same numbers).
- `A229RC0` — BEA disposable personal income per capita, current dollars, monthly, seasonally adjusted at an annual rate (NIPA table 2.6).
- `CUSR0000SEHA` — BLS CPI-U, rent of primary residence, seasonally adjusted.

**How close.** Reproduces the published series exactly: checked every night over the last 120 months to within 0.001 index point (the site rounds to three decimals). October 2025 has no CPI because of the federal shutdown, so the price-to-rent ratio is blank that month. The site currently leaves the price-to-income line blank in October 2025 as well; this script keeps that month, since the house price index and income both exist for it.
