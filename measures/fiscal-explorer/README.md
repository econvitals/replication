# Fiscal Explorer

**On econvitals.org:** the [Fiscal Explorer](https://econvitals.org/tools/fiscal-explorer/) (and its [methodology page](https://econvitals.org/tools/fiscal-explorer/methodology.html)), also embedded under [Fiscal › Make your own](https://econvitals.org/fiscal/). Method note: [Methods](https://econvitals.org/methods/#fiscal-explorer).

**What it is.** The Explorer starts from CBO’s February 2026 baseline, reproduced to the dollar, and lets a visitor change the economy, change policy or move three house levers, then recomputes debt year by year. This folder rebuilds that starting point — the data set the page carries — and works through two pieces of the arithmetic the page runs on it:

- **The baseline.** Federal revenues, outlays, net interest, the primary and total deficit, and debt held by the public, fiscal years 1901–2056, in billions of dollars and as a percent of GDP.
- **The fiscal gap.** The permanent cut in the primary deficit (the deficit before interest), from 2027, that would hold debt in 2056 at its 2025 share of GDP: **2.37 percent of GDP**. With *d* the debt ratio, *r* CBO’s average interest rate on the debt and *g* nominal GDP growth, it is (*d*₂₀₅₆ − *d*₂₀₂₅) divided by the sum, over 2027–2056, of the compounded factor (1 + *r*)/(1 + *g*) from each year to 2056.
- **The interest-rate dial.** Treasury rates one percentage point higher from 2027, the economy unchanged. CBO’s existing debt reprices as it rolls over (one-sixth of the gap closes each year, for an average maturity of about six years); the extra debt the shock creates is new borrowing and pays the full higher rate at once. Debt in 2056 comes to **214.3 percent of GDP**, against 175.1 percent in CBO’s baseline.

**What the browser adds on top (not replicated here).** The economic levers (productivity, the labor force, interest rates and inflation, scaled from CBO’s published sensitivities), Jason Furman’s three “other approximate rules,” the named policy alternatives and the rules for discretionary spending, fixed-size and goal-seeking scenarios, an interest rate that rises with debt, the detail by revenue source and program, and the charts and downloads. Touch nothing and the page shows the numbers rebuilt here.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`; Treasury’s Fiscal Data API needs no key). Writes:

- `output/baseline.csv` — one row per fiscal year: the source of that year’s figures, GDP, the six budget aggregates in billions of dollars and each as a percent of GDP (`*_pct`). Rows are dated January 1 of the fiscal year; `date_dec31` carries the December 31 dating that the site’s debt chart uses.
- `output/fiscal_gap.csv` — the fiscal gap and its ingredients.
- `output/rate_scenario.csv` — debt and net interest as a percent of GDP, baseline and with rates one point higher.
- `output/live_page_check.csv` — every dollar figure set beside the copy built into the live page (see “How close”).

**Data.**

| Years | Revenues, outlays, deficit, net interest, debt | GDP (the denominator) |
| :---: | :---: | :---: |
| 1901–1929 | OMB Historical Tables 1.1 (net interest from 1940, Table 3.1; debt from 1940, Table 7.1) | Census GNP, scaled to BEA at 1929 |
| 1930–1961 | the same OMB tables | OMB Table 1.2 |
| 1962–1990 | CBO, historical budget data | OMB Table 1.2 |
| 1991–2024 | CBO, historical budget data | BEA, fiscal-year average of quarterly GDP |
| 2025 | CBO baseline (an actual year in CBO’s table) | BEA |
| 2026 | Treasury, final Monthly Treasury Statement | BEA |
| 2027–2036 | CBO baseline, Table 1-1 | CBO |
| 2037–2056 | CBO extended baseline (percent of GDP × CBO’s GDP) | CBO |

Files in `inputs/` (CBO’s website refuses scripted downloads; CBO, OMB and Census data are U.S. government works and free to redistribute). `inputs/cut_inputs.py` shows exactly which cells each column was cut from.

- `cbo_budget_projections_2026-02.csv` — CBO, *The Budget and Economic Outlook: 2026 to 2036* (February 2026), [www.cbo.gov/publication/61882](https://www.cbo.gov/publication/61882), file `51118-2026-02-Budget-Projections.xlsx`, Table 1-1. Billions of dollars, 2025–2036; deficits negative, as CBO prints them.
- `cbo_historical_budget_data_2026-02.csv` — same publication, file `51134-2026-02-Historical-Budget-Data.xlsx`, sheets 1 (revenues, outlays, total surplus, debt held by the public) and 3 (net interest). Billions of dollars, 1962–2024.
- `cbo_ltbo_extended_baseline_2026-02.csv` — CBO, *The Long-Term Budget Outlook: 2026 to 2056* (February 2026), [www.cbo.gov/publication/62044](https://www.cbo.gov/publication/62044), file `51119-2026-02-25-LTBO-Budget.xlsx`, sheet “1. Summary Ext Baseline.” Percent of GDP and GDP in trillions, 2026–2056.
- `cbo_ltbo_interest_and_growth_2026-02.csv` — same publication, file `57054-2026-02-LTBO-econ.xlsx`, sheet 1: the average interest rate on debt held by the public (fiscal year) and nominal GDP growth, 2025–2056.
- `omb_historical_tables_fy2027.csv` — OMB, *Historical Tables*, Budget of the U.S. Government, Fiscal Year 2027, [whitehouse.gov/omb/information-resources/budget/historical-tables](https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/): Tables 1.1 (receipts, outlays, surplus; millions), 1.2 (GDP; billions), 3.1 (net interest; millions) and 7.1 (debt held by the public, percent of GDP), 1901–1990.
- `census_hsus_series_f1_gnp.csv` — Census Bureau, *Historical Statistics of the United States, Colonial Times to 1970*, Part 1, Series F 1 (gross national product, current prices), p. 224, [census.gov](https://www2.census.gov/library/publications/1975/compendia/hist_stats_colonial-1970/hist_stats_colonial-1970p1-chF.pdf), 1900–1929.

Fetched when the script runs: FRED series `GDP` (BEA, quarterly) and `GDPA` (BEA, annual, for 1929), each as published on November 1, 2026; and Treasury’s Fiscal Data API, Monthly Treasury Statement Tables 1, 6 and 9 for September 2026.

Three conventions worth knowing. Fiscal years run October–September from 1977 and July–June before that. Before 1930 nobody published a fiscal-year GDP, so the denominator is Census’s GNP averaged over the two calendar years a July–June fiscal year spans and scaled by BEA’s 1929 GDP over Census’s 1929 GNP; it is good to about a tenth of a point of GDP, and before 1914 other reconstructions run as much as 18 percent higher. And debt held by the public for fiscal 2026 is Treasury’s “total borrowing from the public,” CBO’s own measure.

**How close.** Reproduces the Explorer exactly: every dollar figure matches the copy built into the live page to within $1 million (858 figures; the page rounds to $1 million), and the fiscal gap and the rate-dial path agree with the page’s own engine to a millionth of a percentage point. The script makes that comparison on every run that can reach econvitals.org, and fails if any figure differs by more than $2 million while the page carries the same build date.

The nightly check compares two published series, the tightest that holds given each file’s rounding:

- net interest as a percent of GDP, 1995–2036, against the published Federal Debt Service series (the same numbers as the net interest chart on the Fiscal page), within 0.0001 point (that file rounds to four decimals);
- debt as a percent of GDP, 2027–2056, against the CBO line of the published debt chart, within 0.001 point (three decimals).

Why only those: the Explorer’s full data set lives inside its page, not in the published data repository the nightly check reads. Two other published fiscal charts — the history on that debt chart and the deficit since 1901 — were drawn before BEA’s September 2026 GDP revision and before fiscal 2026 closed, so for 2021–2026 they differ from the Explorer (debt by up to 0.6 point of GDP in 2026); those years are left out of the comparison rather than covered by a looser tolerance.

**Gaps.** Debt held by the public for 1930–1939 is not rebuilt: the Explorer takes those ten debt-to-GDP ratios from an extended OMB series carried by a commercial data service, while OMB’s own Table 7.1 starts in 1940, so this replication starts debt there. Nine deficits between 1962 and 1993 differ by $1 million, because the page takes them from OMB’s printed balance and CBO rounds them the other way.

**When the Explorer is rebuilt** (a new CBO outlook, or a BEA revision it chooses to take), move `VINTAGE` at the top of `replicate.py` to the new build date and recut `inputs/` for a new CBO vintage. Until then the live-page check reports the mismatch in build dates and skips itself.
