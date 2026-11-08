# Econvitals Inflation Dispersion Index

**On econvitals.org:** [Inflation › CPI](https://econvitals.org/inflation/#cpi), the chart “Standard Deviation of Inflation Across Categories”. Method note: [Methods](https://econvitals.org/methods/#inflation-dispersion).

**What it is.** How spread out price changes are across the CPI basket: 12-month inflation for 177 detailed CPI categories, weighted by their share of spending, summarized as a weighted standard deviation. High means inflation is concentrated in a few categories; low means prices are rising in step. A house index; no agency publishes it.

Each month, with π_i the 12-month inflation of category i and w_i its weight:

    π̄     = Σ w_i π_i                  the spending-weighted mean (close to CPI inflation)
    sigma = √( Σ w_i (π_i − π̄)² )      percentage points

The 177 categories are the lowest-level items (codes beginning `SE` or `SS`) in BLS’s relative-importance table for December 2023, and their weights are that table’s CPI-U values, scaled to sum to one. The weights are fixed; the indexes are CPI-U, U.S. city average, not seasonally adjusted (`CUUR0000` + item code), and 12-month changes compare the same calendar month a year apart. Each month the weights are rescaled over the categories that have a 12-month change, so a category that starts late does not tilt the result. A month where less than half the basket (by weight) has one is left blank: before December 1983 too few of these categories existed, and in October 2025 BLS collected no prices. The chart’s caption (“88th percentile of history”) is the share of months since December 1983 at or below the latest reading; the script prints it.

**Run it.** `python replicate.py` (no key needed). Writes `output/inflation_dispersion.csv`: `sigma` and, for reference, the weighted mean. The category list, weights and indexes come from `cpi_strata_panel` in [`common/inflation.py`](../../common/inflation.py), shared with the [skewness index](../inflation-skewness/). The first run downloads about 20 MB of BLS files.

**Data.** From BLS, no key:

- The relative-importance table, December 2023: `https://www.bls.gov/cpi/tables/relative-importance/2023.xlsx` (Table 1, the CPI-U column).
- Item names and codes: `cu.item` in BLS’s bulk files at download.bls.gov/pub/time.series/cu/.
- Monthly indexes for the 177 items: the eight U.S. city-average item-group bulk files (`cu.data.11.USFoodBeverage` through `cu.data.18.USOtherGoodsAndServices`).

**How close.** Reproduces the published series to the last published digit over its whole history (513 months, December 1983 through September 2026, as of November 2026); the nightly check compares every month within 0.0001 percentage point (the site rounds to four decimals).
