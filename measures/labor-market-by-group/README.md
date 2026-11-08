# Labor Market by Group

**On econvitals.org:** [Demographic detail › Labor Market by Group](https://econvitals.org/labor/demographicdetail/#bygroup), the interactive table of participation, employment and unemployment rates for any combination of sex, age, race and ethnicity, and education. Method note: [Methods](https://econvitals.org/methods/#labor-market-by-group).

**What it is.** Monthly Current Population Survey microdata — the individual survey responses, distributed by IPUMS at the University of Minnesota — collapsed into cells by sex, single year of age, five race and ethnicity groups and four education groups, so a visitor can read participation, employment and unemployment for any combination and the change from a chosen date, with an averaging window to smooth small samples. These are raw rates, not adjusted for anything; differences across groups mix behavior and composition. Not a BLS-published table. Rates for small groups are noisy; the averaging window helps.

The script:

1. keeps people 16 and over with a positive final weight who are in the civilian labor force or out of it (`LABFORCE` 1 or 2), and puts each in a cell by month, sex, single year of age (80 means 80 and over), race and ethnicity (Hispanic of any race, then non-Hispanic White, Black, Asian, and everyone else) and education (less than a high school diploma, high school diploma or equivalent, some college or an associate degree, bachelor’s degree or more — `EDUC` below 73, below 81, below 111, and the rest);
2. adds up, in each cell, the weighted population, labor force and employment (`EMPSTAT` 10 or 12), and the unweighted counts the page uses to flag small samples;
3. pools the cells over the windows the page offers — the latest 12 or 3 months, compared with the same months at a business-cycle peak (the 12 months ending March 2001, December 2007 or February 2020; for the 3-month window, the same season in 2000, 2007 or 2019) or a year earlier — and writes them in the file the page reads. A calendar month missing on either side of a comparison is dropped from both; today that drops October, because October 2025 was not collected.

The page computes the rates from those pooled totals in your browser.

**Get the data.** IPUMS’s terms do not allow its microdata to be redistributed, so this folder has none. Request an extract yourself (free, with an account) at [cps.ipums.org](https://cps.ipums.org/cps/):

| Setting | Choose |
|:-:|:-:|
| Samples | Every **Basic Monthly** sample from January 2000 to the latest month. For March, take the basic monthly sample (named like `cps2019_03b`), not the ASEC (`cps2019_03s`). There is no October 2025. |
| Variables | `AGE`, `SEX`, `RACE`, `HISPAN`, `EDUC`, `EMPSTAT`, `LABFORCE`, `WTFINL` (IPUMS adds `YEAR`, `MONTH` and its technical variables automatically) |
| Data format | CSV (IPUMS delivers it gzipped, `.csv.gz`) |
| Structure | Rectangular, person records |

A 2000-to-date extract is large — about 40 million person records. You can split it into several extracts (one per decade, say) and pass them all. Cite the data the way IPUMS asks; the citation, with its version number, comes with your extract.

**Run it.** `python replicate.py cps_00001.csv.gz [cps_00002.csv.gz ...]`. No key needed. Writes `output/cells.csv` (the collapsed cells, one row per month × sex × age × race × education) and `output/labor-by-group.json` (the page’s file: for each comparison and window, the pooled weighted labor force, employment and population and unweighted counts by sex × age group × race × education). It reads the extract in pieces of two million records, so it never holds the whole file in memory.

**How close.** Not compared with the site every night, because the check would need the microdata. When this folder was written, the script was checked two ways against the extracts Econvitals itself uses: its cells matched Econvitals’ cells exactly for the two years tested (2017, and 2026 through July), and from the same cells it produced a file identical, number for number, to the published construction, including the January and February cases where a 3-month window reaches back before the 2000–01 peak’s data begin. The published file is refreshed each month once IPUMS posts the latest month, which is usually a few weeks after the jobs report; its `through` field says how far it runs.
