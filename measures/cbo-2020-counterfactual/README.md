# CBO-2020 Counterfactual

**On econvitals.org:** the [CBO January-2020 Counterfactual Explorer](https://econvitals.org/tools/cbo-jan2020/). Method note: [Methods](https://econvitals.org/methods/#cbo-2020-counterfactual).

**What it is.** CBO’s last projection before the pandemic, from *The Budget and Economic Outlook: 2020 to 2030* (January 2020), laid against what actually happened, for 47 economic variables. Each variable is shown as two quarterly lines from 2018 Q1: the actual data and CBO’s projection, put on today’s footing by one of four rules:

- **Levels and indexes** (GDP, price indexes, payrolls): the CBO line keeps CBO’s growth path but is scaled so that 2019 Q4 equals today’s revised data: CBO line = actual in 2019 Q4 × CBO value ÷ CBO’s 2019 Q4 value. This is redone every time the page is rebuilt, so the CBO line moves slightly as history is revised. It also takes care of CBO having used 2012 dollars where today’s data use 2017 dollars.
- **Rates** (unemployment, the 10-year Treasury yield): shown exactly as CBO projected them.
- **Shares of GDP** (compensation of employees): the CBO side is CBO’s component divided by CBO’s own GDP; the actual side is the actual component divided by actual GDP.
- **Series that cross zero** (real net exports): the CBO line is shifted, not scaled, so it passes through the 2019 Q4 actual: CBO value − CBO’s 2019 Q4 value + actual 2019 Q4 value.

CBO did not publish an employment-population ratio, so the CBO line for it is constructed: CBO’s civilian employment divided by its civilian noninstitutional population (16 and over). Only complete quarters are shown; a monthly series needs all three months of a quarter published.

**What this folder rebuilds.** Ten of the 47 series, chosen to cover every rule: nominal GDP, real GDP, the core PCE price index, the CPI-U, payrolls (levels and indexes); the unemployment rate, the employment-population ratio and the 10-year Treasury yield (rates); compensation of employees as a share of GDP; and real net exports. The other 37 follow the same four rules with different inputs. The page itself adds the gallery, the sortable table, the “above/below CBO” callouts and an AI-written synthesis essay; none of that is reproduced here.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). It writes one CSV per series to `output/` (columns `date`, `actual`, `forecast`; `forecast` starts at 2019 Q4).

The page is rebuilt by hand from time to time, while the Bureau of Economic Analysis and the Bureau of Labor Statistics keep revising the data. So by default the script asks FRED for the data **as they stood on the day the page was last built** (FRED keeps every past vintage of a series; the date is read from the published page’s `meta.generated`). `python replicate.py --latest` uses today’s data instead, which is what the page will show the next time it is rebuilt.

**Data.**

- *Actuals*, from FRED: `GDP` (nominal GDP), `GDPC1` (real GDP), `PCEPILFE` (core PCE price index), `CPIAUCSL` (CPI-U), `PAYEMS` (nonfarm payrolls, converted from thousands to millions), `UNRATE` (unemployment rate), `EMRATIO` (employment-population ratio), `GS10` (10-year Treasury, monthly average), `W209RC1` (compensation of employees) and `NETEXC` (real net exports). Monthly series are averaged to quarters.
- *CBO’s projection*: `inputs/cbo_jan2020_quarterly.csv` (9 KB), the eleven quarterly columns used, 2010 Q1–2030 Q4. The values before 2020 are CBO’s own record of history. Source: Congressional Budget Office, *The Budget and Economic Outlook: 2020 to 2030*, January 2020, “10-Year Economic Projections” (CBO’s file `51135-2020-01-economicprojections.xlsx`, listed under “10-Year Economic Projections” at [cbo.gov/data/budget-economic-data](https://www.cbo.gov/data/budget-economic-data)). CBO’s website refuses scripted downloads, so the numbers ship here; CBO data are a U.S. government work and free to redistribute. This copy was taken from the quarterly CBO file Econvitals’ own build reads, not freshly from CBO’s workbook, which could not be re-downloaded for this repository; spot checks against CBO’s published January 2020 figures agree (real GDP growth of 2.2 percent over 2020, unemployment averaging 3.5 percent in 2020).

**How close.** Exact. All ten series, both lines, match the published page on every quarter (checked every night to within 0.00001 in each series’ own units; the page stores six decimals). The one exception is compensation as a share of GDP, which agrees to within 0.0002 percentage point: the page reads compensation from BEA’s own table in millions of dollars, while FRED rounds it to a tenth of a billion. The site prints that share to one decimal.

The nightly check addresses each series by its **position** in the page’s data file (`series.0.data` is nominal GDP, `series.28.data` compensation, and so on). If the page ever reorders its series the check will fail loudly rather than pass on the wrong series. The CBO projection is a recorded input, so the check confirms the method and the actual data, not CBO’s file itself.

Two quirks of the data, reproduced as the page has them: October 2025 has no CPI and no household-survey data (the government shutdown stopped both), so those series’ 2025 Q4 is the average of November and December; and because the CBO line is re-scaled to the latest 2019 Q4 data, a comprehensive revision to 2019 moves the whole CBO line a little.
