# Labor Market Tightness Measures

**On econvitals.org:** [Labor › JOLTS](https://econvitals.org/labor/#jolts), the full-width chart “Measures of Labor Market Tightness.” Method note: [Methods](https://econvitals.org/methods/#labor-market-tightness).

**What it is.** Five BLS gauges of how tight the job market is — the prime-age (25–54) employment rate, the unemployment rate with its sign flipped, job openings per unemployed worker, the quits rate and the job openings rate — each expressed as the number of standard deviations (measured over 2001–2018) it sits from its February 2020 level, so the five can share one axis with positive meaning tighter:

> standardized(t) = (x(t) − x(February 2020)) ÷ standard deviation of x, January 2001 to December 2018

The quits rate is quits ÷ payroll employment and the openings rate is openings ÷ (openings + payroll employment), both built from the published levels rather than read as BLS’s one-decimal rates. The standardization and the February 2020 reference point are house choices; the underlying data are BLS’s.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). Writes `output/labor_market_tightness.csv`, one column per gauge.

**Data.** Six BLS series, read from FRED, which republishes them unchanged:

| FRED series | BLS series | What |
|:-:|:-:|:-:|
| `LNS12300060` | LNS12300060 | Employment-population ratio, ages 25–54 (household survey, seasonally adjusted) |
| `UNRATE` | LNS14000000 | Unemployment rate |
| `UNEMPLOY` | LNS13000000 | Number unemployed |
| `JTSJOL` | JTS000000000000000JOL | Job openings (JOLTS) |
| `JTSQUL` | JTS000000000000000QUL | Quits (JOLTS) |
| `PAYEMS` | CES0000000001 | Nonfarm payroll employment |

**How close.** Reproduces the published chart exactly: every one of the 308 months since January 2001, on all five lines, within 0.0001 standard deviation (the largest difference is 0.00005, the site’s rounding to four decimals). The nightly check compares the whole history at that tolerance. A month appears only when all six series have it, so October 2025 (no household survey, because of the federal shutdown) is missing, and the newest month waits for JOLTS, which BLS publishes about a month after the jobs report for the same month.
