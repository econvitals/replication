# Econvitals PCE-Equivalent Inflation Measures

**On econvitals.org:** [Inflation › Underlying](https://econvitals.org/inflation/#underlying), the two adjusted tables (PCE and CPI). Method note: [Methods](https://econvitals.org/methods/#pce-equivalent-measures).

**What it is.** Every core inflation measure runs at its own average level: CPI-based measures run hotter than PCE, and median and trimmed-mean measures have typical gaps of their own. For each measure Econvitals computes the fixed number of percentage points that, added to it, makes its long-run average equal the long-run average of overall PCE inflation — the “Adj.” column in the tables:

    Adj. = average annual overall PCE inflation − average annual inflation of the measure, over the window

The reference window is January 1996 to January 2020 for the CPI measures and January 1977 to January 2020 for the PCE measures (January 1987 to January 2020 for market-based core PCE and median PCE, whose data start later). Averages are compound annual rates between the two months; overall PCE is BEA’s price index (table 2.8.4, `DPCERG`). After the adjustment every row answers the same question — what PCE inflation does this measure imply? — so a 2% reading means on target in every row. Each row of a table is the measure’s 1-, 3-, 6- and 12-month annualized rate plus Adj., for the newest month every measure has.

The constants as computed from the data available in November 2026:

| Measure | Adj. (pp) | Window |
| :-: | :-: | :-: |
| PCE: overall | 0.00 | 1977–2020 |
| PCE: core | 0.02 | 1977–2020 |
| PCE: core ex housing | 0.23 | 1977–2020 |
| PCE: core ex housing and used cars | 0.22 | 1977–2020 |
| PCE: core services ex housing | −0.76 | 1977–2020 |
| PCE: market-based core | 0.11 | 1987–2020 |
| PCE: median | −0.50 | 1987–2020 |
| PCE: trimmed mean | 0.00 | 1977–2020 |
| CPI: overall | −0.39 | 1996–2020 |
| CPI: core | −0.28 | 1996–2020 |
| CPI: core ex shelter | 0.20 | 1996–2020 |
| CPI: core ex shelter and used cars | 0.11 | 1996–2020 |
| CPI: core services ex shelter | −1.12 | 1996–2020 |
| CPI: median | −0.67 | 1996–2020 |
| CPI: trimmed mean | −0.36 | 1996–2020 |

The adjustment is a historical average, so a measure whose gap to PCE has shifted will read a little high or low. The constants are Econvitals’ and fixed, not an agency’s. The Core Services ex Shelter row on the CPI side is itself an Econvitals aggregate ([its folder](../core-services-cpi-ex-shelter/)), and so is Core ex Housing and Used Cars on the PCE side ([its folder](../core-pce-ex-housing-used-vehicles/)).

**Run it.** `python replicate.py` (needs free `FRED_API_KEY` and `BEA_API_KEY`). Writes `output/adjusted_pce.csv` and `output/adjusted_cpi.csv` (one row per measure: `delta` is Adj., `h1`, `h3`, `h6`, `h12` the adjusted rates) and `output/adjustments.csv` (each constant to six decimals and the window it used). The measures are assembled in [`common/inflation.py`](../../common/inflation.py).

**Data.** The same fifteen measures as the [Ecumenical Underlying Inflation](../ecumenical-underlying-inflation/) — its README lists every series. In short: BEA table 2.8.4 price indexes; BLS seasonally adjusted CPI indexes from BLS’s bulk files; the Cleveland Fed’s median CPI, trimmed-mean CPI and median PCE and the Dallas Fed’s trimmed-mean PCE, whose full histories set the calibration for those rows. Between BEA’s PCE release and the banks’ posts (about a business day), the median and trimmed-mean PCE rows use Econvitals’ own estimates from BEA’s detail, exactly as the site does; that README explains how.

**How close.** Reproduces both tables exactly: every Adj. constant and every adjusted rate matches the published table (`sections.inflation.adjusted` in `data/dashboard.json`, stored to six decimals) with no difference at that precision, for September 2026 as of November 2026. The nightly check uses a tolerance of 0.000001 percentage point. The folder is marked “recorded inputs” only because the CPI core-services-ex-shelter row needs that series back to 1996 for its constant, and its history before March 2012 is a recorded file (BLS publishes the weights it needs only from then). The table’s tracker view (shown between the CPI and PCE releases) uses the [Econvitals PCE Tracking Estimate](https://econvitals.org/methods/#pce-tracking-estimate) for its newest month and is not rebuilt here.
