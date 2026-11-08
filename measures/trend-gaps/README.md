# Trend Gaps

**On econvitals.org:** the [Economy vs. Trend tool](https://econvitals.org/tools/trend-gaps/). Method note: [Methods](https://econvitals.org/methods/#trend-gaps).

**What it is.** For about 90 U.S. series — output, productivity, jobs, wages, prices and income — Econvitals fits a pre-pandemic trend, carries it to today, and reports the gap between each series and its trend. This folder rebuilds the tool’s headline series: the eight concept tiles (real GDP, labor productivity, payroll employment, household employment, ECI wages, real ECI wages, the PCE price index, real disposable income per person) and the CPI, which the page’s opening sentence uses.

- **The end point** is February 2020 for monthly series and 2019 Q4 for quarterly ones. Time is measured as year + (month − 1)/12.
- **Fitted trends:** a straight line through the logarithm of the series over the 2, 5 (the page’s default) or 10 years ending at the end point, carried forward.
- **Peak to peak:** constant growth from the 2007 business-cycle peak (December 2007 / 2007 Q4) or the 2001 peak (March 2001 / 2001 Q1) to the end point, extended.
- **Hodrick–Prescott:** a smoothed trend through the logarithm from 2000 to the end point (λ = 1,600 quarterly, 129,600 monthly), extended at the trend’s growth over its final year.
- **CBO January 2020:** CBO’s projection from *The Budget and Economic Outlook: 2020 to 2030*, re-anchored so 2019 Q4 matches the actual; monthly series put each CBO quarter at its middle month and interpolate between them (in logs). Real ECI’s CBO line is CBO’s ECI divided by CBO’s CPI.
- **The gap** is 100 × (actual ÷ trend − 1), in percent. A price level above trend is a cumulative gap, not an inflation rate. Real wages are nominal wages divided by CPI-U: each quarter’s ECI over that quarter’s average CPI, indexed to 2019 Q4 = 100 (October 2025 has no CPI because of the shutdown, so 2025 Q4 averages November and December). Data are today’s vintage.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). It writes `output/gaps.csv` (each series’ latest gap under each of the seven trends) and `output/levels.csv` (each series from 2000 and its re-anchored CBO path, one row per series and date). `output/site_gaps.csv` and `output/site_levels.csv` apply the same arithmetic to the series the site publishes, for the nightly comparison.

**Data.**

- FRED: `GDPC1` (BEA real GDP), `OPHNFB` (BLS nonfarm business output per hour), `PAYEMS` (BLS payroll employment), `CE16OV` (BLS household-survey employment), `ECIWAG` (BLS Employment Cost Index, private wages and salaries), `PCEPI` (BEA PCE price index), `A229RX0` (BEA real disposable personal income per capita), `CPIAUCSL` (BLS CPI-U, seasonally adjusted). Employment is shown in millions; everything else in its publisher’s units.
- `inputs/cbo_jan2020_quarterly.csv`: the seven columns of CBO’s January 2020 quarterly economic projections this folder uses (real GDP, nonfarm business output per hour, payroll and household employment, the ECI for wages and salaries, CPI-U and the PCE price index), 2019 Q1–2030 Q4. CBO’s website does not answer scripted downloads, so the columns are shipped here; CBO’s work is a U.S. government publication.

**How close.** Reproduces the published tool exactly: on November 8, 2026 every one of the 2,471 published values for these series and their CBO paths matched, and so did every series’ latest gap under every trend. The check allows 0.0001 on levels (the site publishes four decimals) and 0.001 percentage point on gaps. The page fits its trends in the browser from the series it publishes; the Python here was checked against the page’s own JavaScript on the published data, and agrees to within a millionth of a percentage point.

**What is not rebuilt here.** The other ~85 series on the page (GDP’s components, jobs by industry, other wage measures, CPI and PCE splits, the employment and participation rates) — the arithmetic is the same, with only the series list longer, and rates use a flat window average instead of a fitted trend; and the “fit from a chosen year” trend, which depends on a slider.
