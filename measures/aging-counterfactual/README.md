# Aging Counterfactual

**On econvitals.org:** [Demographic detail › Aging-Only Counterfactual, Since a Chosen Peak](https://econvitals.org/labor/demographicdetail/#counterfactual) — the hypothetical-versus-actual charts for the participation rate and the employment rate, and the contribution tables beside them, for each of three peaks. Method note: [Methods](https://econvitals.org/methods/#aging-counterfactual).

**What it is.** Start at a business-cycle peak — March 2001, December 2007 or February 2020 — and ask: if no age-and-sex group had changed its behavior since then, where would the participation or employment rate be today, given only how the population aged? That is the hypothetical line:

> hypothetical(t) = actual(t) − [cumulative behavior(t) − cumulative behavior(peak)]

which starts at the actual rate in the peak month and then moves only with the changing mix of groups. The gap to the actual rate is the behavior change, and the contribution tables split that gap by age group (16–24, 25–54, 55+) and sex: each of the 30 age-and-sex groups’ monthly behavior contributions, summed over the months after the peak through the latest month, then added up into three age groups. The pieces sum exactly to the total.

It is the same chained decomposition as the [age-adjusted rates](../age-adjusted-labor-rates/) (its README describes the 30 groups, the seasonal scaling and the formula; the code is in [`common/labor.py`](../../common/labor.py)), anchored at the chosen peak rather than at the latest month.

**Run it.** `python replicate.py`. No key needed. Writes, for each rate (`lfpr`, `epop`) and peak (`2001`, `2007`, `2020`):

- `output/<rate>_counterfactual_<peak>.csv` — `actual` from January of the peak year and `hypothetical` from the peak month;
- `output/<rate>_contributions_<peak>.csv` — the table, one row per age group plus a total, columns Women, Men and Total, in percentage points rounded to three decimals as on the site;
- `output/<rate>_contributions_<peak>_by_sex.csv` — the same table turned on its side, which the nightly check uses.

**Data.** The same 118 BLS Current Population Survey series as the age-adjusted rates, from BLS’s bulk household-survey file (`download.bls.gov/pub/time.series/ln/ln.data.1.AllData`, about 400 MB, streamed and cached until BLS posts a new version). No key needed.

**How close.** Reproduces the published charts and tables exactly. The twelve lines (actual and hypothetical, two rates, three peaks) agree with the site to within 0.000001 point over every month (the site publishes them unrounded), and every one of the 72 numbers in the six tables matched exactly when this was written. The nightly check compares the lines over their whole length at 0.000001, and from each table the four age-group totals and the three sex totals at 0.001 (one unit in the third decimal, in case the rounding of a number sitting on a boundary flips). The checker reads a table by one label column, so it sees only those seven totals, not the six individual age-by-sex cells.

The page’s year-by-year “Demographic contributions” chooser is not rebuilt here. Its data file (yearly contributions, 1991 through 2025) is not regenerated with the monthly series, and simply adding up each calendar year’s monthly contributions does not give its numbers, so it has not been possible to pin down its exact yearly convention.
