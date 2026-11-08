# Econvitals Underlying Unit Labor Costs

**On econvitals.org:** [Home › Wages](https://econvitals.org/#wages) (the tile under the wage table) and [Labor › Wages](https://econvitals.org/labor/#wages) (the chart beside the table). Method note: [Methods](https://econvitals.org/methods/#wage-tracker).

**What it is.** A measure of the underlying growth rate of unit labor costs. It differs from BLS’s unit labor costs in three ways: it is based on several measures of wage growth; it uses trend productivity growth over the cycle rather than the much more volatile actual productivity growth over the last quarter or year; and it is expressed in units that match PCE price inflation. At 2%, wages are growing at a pace consistent with 2% inflation given today’s productivity growth.

1. **Five wage gauges**, each as its 12-month (or four-quarter) percent change: the Employment Cost Index (wages and salaries, private industry), the Atlanta Fed Wage Growth Tracker, average hourly earnings, nonfarm business compensation per hour and median usual weekly earnings. A quarterly gauge sits on the last month of its quarter and is carried forward up to five months, until the next print.
2. **PCE-equivalent units.** Each gauge is shifted by its own average gap to PCE inflation over 2007–2019, so all five read as the PCE inflation rate that pace of wage growth went with in 2007–2019.
3. **Averaged** over whichever gauges have a value that month, with weights equal to one over each gauge’s variance since 2007, which favors the steadier gauges (today about 31% the Employment Cost Index, 26% average hourly earnings, 25% the Atlanta Fed tracker and 9% each for compensation per hour and weekly earnings). The line ends at the latest month with a monthly print (average hourly earnings or the Atlanta Fed tracker).
4. **Productivity adjustment.** From 2022 Q1 on, the result is lowered by trend productivity growth — output per hour in the nonfarm business sector, annualized from the 2019 Q4 business-cycle peak to each quarter — minus its 2007–2019 pace (2006 Q4 to 2019 Q4, about 1.6% a year). The adjustment is zero before 2022 Q1: through 2019 by construction, and in 2020–21 because the pandemic’s shift in who was working distorted measured productivity and wages alike. Each quarter’s adjustment carries forward until the next one.

Average hourly earnings is BLS’s all-employee series from March 2007 (the series begins in March 2006, so that is its first 12-month change), and the production and nonsupervisory series before that. A house composite, not a BLS series.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`, and `openpyxl`, the package pandas uses to read Excel files). Writes `output/wage_pce_equivalent.csv`: `value` (the headline), `unadjusted` (the thin line on the chart), one column per gauge (the dots, on the same adjusted basis; a quarterly gauge only on its quarter-end month) and `productivity_adjustment`.

**Data.**

| Source | Series | What |
|:-:|:-:|:-:|
| FRED | `ECIWAG` (BLS CIS2020000000000I) | Employment Cost Index, wages and salaries, private industry (quarterly) |
| FRED | `CES0500000003` | Average hourly earnings, all private employees |
| FRED | `AHETPI` (BLS CES0500000008) | Average hourly earnings, production and nonsupervisory employees |
| FRED | `COMPNFB` (BLS PRS85006103) | Nonfarm business compensation per hour (quarterly) |
| FRED | `LEU0252881500Q` | Median usual weekly earnings, full-time workers (quarterly) |
| FRED | `PCEPI` (BEA Table 2.8.4) | PCE price index |
| FRED | `OPHNFB` (BLS PRS85006093) | Nonfarm business output per hour (quarterly) |
| Atlanta Fed | `wage-growth-data.xlsx`, sheet “data_overall”, column “Overall” | Wage Growth Tracker, 3-month moving average |

The Wage Growth Tracker comes from the Bank’s own workbook, linked from its [tracker page](https://www.atlantafed.org/research-and-data/data/wage-growth-tracker), because the Bank’s file can be a few days ahead of FRED’s copy (`FRBATLWGT3MMAUMHWGO`), and the site reads the Bank’s; if the workbook cannot be reached, the script uses FRED’s copy. The two were identical over the whole history when this was written.

**How close.** Reproduces the published chart exactly when run in the same calendar month as the site’s last update: all 238 months of the headline and the unadjusted line, and every gauge dot, within 0.0001 point (the largest difference is 0.00005, the site’s rounding to four decimals).

One feature of the method makes the date you run it matter slightly. The variance weights are computed over every month up to the current calendar month, including the months in which a quarterly print is being carried forward past the last monthly reading. So with no new data at all, each month that passes changes the weights a little, and the whole headline line moves by up to about 0.002 point (most in 2020, when the gauges disagreed most; under 0.0006 point in the last three years). The nightly check therefore allows 0.002 point on the headline and the unadjusted line, enough for one month’s drift between the site’s last update and the check, and 0.0001 point on the five gauges, which do not depend on the weights.

Shutdown gaps: the Atlanta Fed tracker has no October 2025 and median weekly earnings has no 2025 Q4, so the 12-month change that would need either is blank, not stretched over a longer span.
