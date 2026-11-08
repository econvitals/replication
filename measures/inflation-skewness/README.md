# Econvitals Inflation Skewness Index

**On econvitals.org:** [Inflation › CPI](https://econvitals.org/inflation/#cpi), the chart “CPI Inflation Skewness”. Method note: [Methods](https://econvitals.org/methods/#inflation-skewness).

**What it is.** The same 177 CPI categories as the [dispersion index](../inflation-dispersion/): the spending-weighted average inflation rate minus the inflation rate of the typical (median-weight) category. A positive reading means a handful of fast-rising items are lifting the average above what most categories are doing; a negative one means the reverse. A house index; no agency publishes it.

Each month, with π_i the 12-month inflation of category i and w_i its weight:

    mean   = Σ w_i π_i
    median = the π_i at which the cumulative weight, with categories sorted by π, first reaches one half
    skew   = mean − median        percentage points

The categories, the fixed weights (BLS’s relative-importance table for December 2023, CPI-U, scaled to sum to one) and the not-seasonally-adjusted CPI-U indexes are exactly those of the dispersion index; its README describes them. Weights are rescaled each month over the categories that have a 12-month change, and a month where less than half the basket has one (before December 1983, and October 2025, when BLS collected no prices) is blank. The chart’s caption (“79th percentile of history”) is the share of months since December 1983 at or below the latest reading; the script prints it.

**Run it.** `python replicate.py` (no key needed). Writes `output/inflation_skewness.csv`: `skew` and, for reference, the weighted `mean` and `median`. The panel comes from `cpi_strata_panel` in [`common/inflation.py`](../../common/inflation.py).

**Data.** BLS’s December 2023 relative-importance table (`https://www.bls.gov/cpi/tables/relative-importance/2023.xlsx`), the item list `cu.item` and the eight U.S. city-average item-group files (`cu.data.11.USFoodBeverage` through `cu.data.18.USOtherGoodsAndServices`) from BLS’s bulk files at download.bls.gov/pub/time.series/cu/. No key.

**How close.** Reproduces the published series to the last published digit over its whole history (513 months, December 1983 through September 2026, as of November 2026); the nightly check compares every month within 0.0001 percentage point (the site rounds to four decimals).
