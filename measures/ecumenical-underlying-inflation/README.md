# Econvitals Ecumenical Underlying Inflation

**On econvitals.org:** [Inflation › Underlying](https://econvitals.org/inflation/#underlying) (the two tiles), [Inflation › PCE](https://econvitals.org/inflation/#pce) (the chart “Underlying PCE Inflation”) and [PCE inflation detail](https://econvitals.org/inflation/pcedetail/). The full CPI-based series behind the second tile is published as `data/underlying-inflation-cpi.json` in the [Econvitals data repository](https://github.com/econvitals/econvitals-data). Method note: [Methods](https://econvitals.org/methods/#ecumenical-underlying-inflation).

**What it is.** A way to avoid taking a stance on the many time horizons or ways to measure inflation (Jason Furman started it in 2023). It takes eight PCE inflation measures (overall, core, core ex housing, core ex housing and used cars, core services ex housing, market-based core, median and trimmed mean) or seven CPI measures (overall, core, core ex shelter, core ex shelter and used cars, core services ex shelter, median and trimmed mean). Each is first put on a common footing by adding its long-run average gap to overall PCE inflation (the [PCE-equivalent step](../pce-equivalent-measures/)). Then each measure’s 3-, 6- and 12-month annualized rates are computed — 24 numbers for PCE, 21 for CPI — and the reading is their median. No single measure decides it, so a one-month swing in any one of them barely moves it.

The reading is computed only for a month every live measure has, from June 2017 on. A window that cannot be computed is left out rather than guessed: BLS collected no CPI for October 2025, so that month has no CPI-based reading, and a 3- or 6-month CPI change that starts in October 2025 drops out of the median. (A 12-month change whose base is October 2025 uses the geometric average of September and November 2025, Econvitals’ rule for that hole.) The second line on each chart is core inflation’s 6-month annualized rate in the same PCE-equivalent units.

**Run it.** `python replicate.py` (needs free `FRED_API_KEY` and `BEA_API_KEY`). Writes `output/ecumenical_pce.csv` (`ecumenical`, `core_pce_6m`) and `output/ecumenical_cpi.csv` (`ecumenical`, `pce_equiv_core_cpi_6m`). The measures are assembled in [`common/inflation.py`](../../common/inflation.py); the first run downloads about 200 MB (mostly BEA’s two underlying-detail tables) and takes a minute or two; reruns within six hours work from the cache.

**Data.**

| Measure | PCE basis | CPI basis |
| :-: | :-: | :-: |
| Overall | BEA table 2.8.4 `DPCERG` (FRED `PCEPI`) | BLS `CUSR0000SA0` |
| Core | BEA `DPCCRG` (FRED `PCEPILFE`) | BLS `CUSR0000SA0L1E` |
| Core ex housing / ex shelter | BEA `IA001176` | BLS `CUSR0000SA0L12E` |
| … and used cars | Econvitals aggregate ([folder](../core-pce-ex-housing-used-vehicles/)) | BLS `CUSR0000SA0L12E4` |
| Core services ex housing / ex shelter | BEA `IA001260` | Econvitals aggregate ([folder](../core-services-cpi-ex-shelter/)) |
| Market-based core | BEA `DPCXRG` (from 1987) | — |
| Median | Cleveland Fed median PCE (its full-history CSV) | Cleveland Fed median CPI (FRED `MEDCPIM157SFRBCLE`) |
| Trimmed mean | Dallas Fed trimmed-mean PCE (its historical workbook) | Cleveland Fed 16% trimmed-mean CPI (FRED `TRMMEANCPIM157SFRBCLE`) |

BEA series come from the BEA API; BLS series (seasonally adjusted) from BLS’s public bulk files at download.bls.gov. The banks publish median and trimmed-mean inflation as monthly changes, so they are chained into indexes: the Cleveland Fed’s plain 1-month changes from 100 at the first month, the Dallas Fed’s 1-month annualized rates from 100 in January 1977.

**Release days.** As the method note says, Econvitals calculates its own trimmed mean and median so the reading can go out right after the PCE and CPI releases; they are designed to match the Fed banks’ figures, which post later, and are similar but not exact. For PCE the banks post about a business day after BEA, and this script does the same thing Econvitals does in the meantime: it rebuilds trimmed-mean and median PCE from BEA’s 177-component detail (tables 2.4.4U and 2.4.5U, Fisher spending weights, the Dallas Fed’s 24%/31% trim, the 50% weight point for the median; the component list is `inputs/pce_trimmed_mean_components.csv`) and uses those for the newest month. Because BEA revises the prior months in the same release, the 11 months before it use the same estimates until the bank posts, so no rate is stitched from two data vintages. Once a bank posts, its figures stand. For CPI the Cleveland Fed posts the same morning (about 11 a.m.), so the script uses only its figures; it does not rebuild Econvitals’ CPI estimate for the hours in between (that needs 45 CPI components and a seasonal adjustment of four regional rent series).

The PCE chart’s tracker view (`underlying-inflation-pce-tracker`), shown between the CPI and PCE releases, replaces the newest month with the [Econvitals PCE Tracking Estimate](https://econvitals.org/methods/#pce-tracking-estimate); that estimate is a separate measure and is not rebuilt here.

**How close.** Reproduces both published series to the last published digit over their whole history (112 PCE months and 111 CPI months, June 2017 through September 2026, as of November 2026). The nightly check compares the reading and the core line on each basis within 0.0001 percentage point; the site rounds to four decimals. The folder is marked “recorded inputs” only because the CPI basis needs core services CPI ex shelter back to 1996 for its PCE-equivalent adjustment, and BLS publishes the weights that series needs only from March 2012; its earlier history is a recorded file (see [that folder](../core-services-cpi-ex-shelter/)). The PCE basis comes entirely from public files. On a PCE release night the check should still match, since the script follows the same rule as the site; it can differ for a few hours if a bank has posted and the site has not yet rebuilt.
