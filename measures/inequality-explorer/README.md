# Inequality Explorer

**On econvitals.org:** the [Inequality Explorer](https://econvitals.org/tools/inequality-explorer/) tool. Method note: [Methods](https://econvitals.org/methods/#inequality-explorer).

**What it is.** Every number in the Explorer starts from the Congressional Budget Office’s *The Distribution of Household Income, 2023* (September 2026): average incomes and each of their components, taxes and transfers, income shares, tax and transfer rates, household counts and the income needed to enter each group, for ten income groups and every year since 1979, and CBO’s own Gini coefficients. Most of what the page shows is CBO’s, as printed. Where it shows something CBO does not publish, Econvitals computes it from CBO’s figures, and this script does the same arithmetic in the open:

- **Growth** in average income by group, as an index (1979 = 100) and as the percent change between two years.
- **Two income definitions CBO does not publish:** income after transfers and taxes with Medicare and Medicaid and CHIP counted at 40 cents per dollar of government spending (“health at 40¢”), or left out (“ex health”). Each starts from CBO’s nearest published total (income after transfers and taxes) and changes only the pieces that differ.
- **Income shares under those definitions**, weighting each income group by the number of households CBO’s own printed shares imply (a share is the group’s average income times its households over the total, so the households follow from the share). CBO prints the counts themselves only to 0.1 million, which is ±4 percent for the top 1 percent.
- **A Gini for those definitions:** CBO’s Gini for income after transfers and taxes, moved by the difference the eight non-overlapping income groups show between the two definitions.
- **“All nonelderly” households**, Econvitals’ combination of CBO’s households with children and its nonelderly childless households: counts added; dollar averages weighted by the implied household counts and rounded to $100 as CBO prints its own; rates as CBO’s two printed rates weighted by each part’s income before transfers and taxes; shares as CBO’s two printed shares weighted by each type’s total of that income.

**Run it.** `python replicate.py` (no keys). It reads the two CBO files in `inputs/` and writes, to `output/`:

| file | what |
|:---:|:---:|
| `headline.csv` | CBO’s top 1 percent, top 10 percent, highest fifth and lowest fifth shares and its four Gini coefficients, 1979–2023; mean over median income |
| `growth_index_after.csv` | average income after transfers and taxes by group, 1979 = 100 |
| `growth_1979_2023.csv` | percent change in average income, 1979–2023, market income and income before and after transfers and taxes |
| `rates_2023.csv` | CBO’s federal tax and means-tested transfer rates and shares by group, plus social insurance as a percent of income before transfers and taxes |
| `health_alternatives.csv` | the top 1 percent’s share and the Gini with health benefits at 40¢ or left out, 1979–2023 |
| `average_income_2023_health_alternatives.csv` | average income by group under each of those definitions |
| `rebuilt_share_gaps.csv` | how far CBO’s printed shares are from the same shares rebuilt with the implied household counts, for every ranking and household type |
| `nonelderly_2023.csv` | the “all nonelderly” combination, 2023 |

It then reads the page’s own data files from econvitals.org and compares every number it can with them (it carries on, and says so, if the site cannot be reached or has moved to a newer CBO edition).

**Data.** Both files are from CBO’s report page, [www.cbo.gov/publication/62761](https://www.cbo.gov/publication/62761), the September 2026 edition (data for 1979–2023, in 2023 dollars). CBO’s website refuses scripted downloads, so they ship here; CBO’s data are a U.S. government work and free to redistribute.

- `inputs/62761-additional-data-for-researchers.zip` (668 KB) — CBO’s “Additional Data for Researchers” file, unchanged (SHA-256 `11a328f9e6731cd277abef8e2a6bad896c4d3813bb04617a2c467e718ed8e7c5`): 36 tables, 12 for each of CBO’s three ways of ranking households. The script reads Tables 1–12.
- `inputs/62761-figure-18-gini.csv` (1 KB) — the Gini coefficients from Figure 18 (“Income Inequality, by Measure of Income”) of CBO’s “Data Underlying Figures” workbook, copied as printed to three decimals. The workbook itself is 12 MB, and this is the only sheet the script needs.

**How close.** Exact. Every number the script reads or builds that the page also stores — CBO’s tables under all three rankings and four household types, the Gini, the medians, the income thresholds and the “all nonelderly” combination, 410,310 numbers in all — matches the page’s data files to within 1e-16. The 40¢ and ex-health shares and Gini, which the page computes in the browser, were checked against the page’s own code and agree to within 1e-14. The rebuilt shares come within 0.143 percentage point of CBO’s printed shares for every group, ranking and household type, and within 0.084 for the top 1 percent of all households under CBO’s headline ranking, the figures the page states.

**Why the nightly check does not compare it.** The Explorer’s numbers are published only in the page’s own files ([data.json](https://econvitals.org/tools/inequality-explorer/data.json) and data-full.json), not in the published data set the nightly check reads, and the CBO income charts that are in that data set still come from CBO’s previous edition (data through 2022). So `check.json` says “documented”, and the comparison lives in the script instead: run it and it says whether the page still matches.

**What the browser adds on top.** The charts and controls; a custom income definition built from any combination of market-income pieces, programs and taxes (this script shows the two named alternatives); ratios of group averages and per-person values; the step-by-step chart, which spreads the gap between rebuilt and printed values over the steps so they add up to CBO’s change; the change-between-two-years view, with a “rounding and weighting gap” bar; grouped Lorenz curves; and CBO’s figure-only top slices (99th–99.9th, 99.9th–99.99th and top 0.01 percent) and refundable credits, which the page shows as CBO printed them and this script does not read.

**Caveats** (from the Methods page). Wherever CBO prints a share the page shows CBO’s, not the rebuilt one. A Gini for a definition CBO does not publish is an approximation, and the grouped Lorenz curves understate inequality within groups. CBO does not say whether its households-with-children type includes households headed by someone 65 or older. The 40-cent valuation is consistent with Amy Finkelstein, Nathaniel Hendren and Erzo F. P. Luttmer, “The Value of Medicaid: Interpreting Results from the Oregon Health Insurance Experiment,” *Journal of Political Economy* 127, no. 6 (2019).
