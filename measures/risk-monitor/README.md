# Risk Monitor

**On econvitals.org:** the [Risk Monitor](https://econvitals.org/lab/risk-monitor/). The page’s About tab states the method in words.

**What it is.** Where risk is building in the U.S. economy and financial system, and where it is not. The page scores 32 indicators, each against its own record since January 1990, and sorts them into six areas: stock valuations, household borrowing, business borrowing and AI financing, banks and nonbanks, funding and market stress, and government debt. It keeps no single score. Beside them it keeps the record of eight classic recession signals: how often each warned before a recession, how often it sounded only once one had begun, and how often it was a false alarm. This script rebuilds those numbers in two stages.

**Stage 1, the arithmetic (exact).** A fresh implementation of the page’s definitions, sharing no code with Econvitals’ builder. From each scored indicator’s stored readings it recomputes:

- **The percentile** of every reading since 1990 and of the latest one: 100 × (the readings below it + half of those equal to it) ÷ all the indicator’s readings from January 1990 (or from its first reading, if it began later). Where a lower reading is riskier, it is 100 minus that, so 100 is always the riskiest reading since 1990 and 0 the safest. A daily or weekly series is stored as monthly means, and its latest close is ranked among them.
- **The heat map**, six areas by quarter from 1990 Q1 through the quarter in progress. An indicator’s value in a quarter is the mean of its monthly percentiles in that quarter, its quarterly percentile, or the percentile of the year containing the quarter’s last month (for the four federal budget series, the *fiscal* year, so October to December count in the next one). A quarter with no reading keeps the latest earlier value for at most four quarters, after which the indicator drops out until it reads again. A cell is the plain mean of the indicators with a value; a year is the plain mean of its quarterly cells.
- **Each recession signal’s record.** A signal is on or off at each reading. An alarm is a run of readings with it on; once it goes off it must stay off for a year (four quarters for the survey of forecasters) before a new alarm is counted. An alarm is *late* if a recession was already under way when it began; otherwise it *warned* if a National Bureau of Economic Research peak fell while it was on or within 12 months (4 quarters) of its last reading; *late* if it began within 3 months (1 quarter) after a trough; *open* if its 12 months are not yet up; and *false* otherwise. A recession is *warned*, *late* or *missed* by the same rules. The two signal series the page derives from stored readings are rebuilt too: the percent by which jobless claims’ three-month average stands above its lowest three-month average of the previous 12 months, and the loan officer survey moved to the month it was published.

The docstring at the top of `replicate.py` states these definitions in full.

**Stage 2, the inputs.** Each scored series, and each series behind a recession signal, that can reasonably be rebuilt from its publisher’s public file is rebuilt and compared with the page’s stored readings, from 1990 (or the series’ start) to the latest: 22 of the 32 scored series and all eight signal series. The other ten scored series are *recorded*: Stage 1 reads them from the page’s data file at run time, as it reads every stored reading, and no copy is kept here.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY` and `BEA_API_KEY`; about 20 seconds the first time, then seconds while the downloads are cached). `python replicate.py --stage1` does only the arithmetic and needs no key. It writes, to `output/`:

| file | what |
|:---:|:---:|
| `percentiles.csv`, `pct.csv` | the percentile of every scored reading since 1990, and of each latest reading |
| `heat_rows.csv`, `heat_parts.csv`, `heat_held.csv`, `heat_years.csv` | the heat map: each area’s cell by quarter, each indicator’s value by quarter, the quarters carried at the end of each row, and the cells by year |
| `signal_alarms.csv`, `signal_recessions.csv`, `signal_counts.csv`, `signal_last_on.csv` | each signal’s alarms (first and last period, length, kind, the peak it is set against and the lead), the recessions it is judged on, its counts and the last period it was on |
| `signal_tested.csv` | the claims and loan officer series rebuilt from the stored readings |
| `checks.csv` | the page’s own sample of percentiles and heat-map cells |
| `inputs.csv`, `inputs_summary.csv` | every rebuilt input reading beside the page’s, and one line a series saying where it came from and how closely it matched |

The keys in the files are the positions the page’s data file uses (`cape|1750` is the 1,751st month of Shiller’s ratio); the other columns say which indicator and period each row is.

**Data.** All today’s vintage.

| input | rebuilt from | |
|:---:|:---:|:---:|
| Shiller’s price-earnings ratio | Robert Shiller, `ie_data.xls` ([shillerdata.com](https://shillerdata.com/)) | rebuilt |
| Value of U.S. stocks, percent of GDP | Federal Reserve [Financial Accounts](https://www.federalreserve.gov/releases/z1/) (table F.51.1: nonfinancial and domestic financial corporations’ shares, less closed-end funds’ and exchange-traded funds’ shares) over Bureau of Economic Analysis GDP (table 1.1.5) | rebuilt |
| Cboe Volatility Index | Cboe, [`VIX_History.csv`](https://www.cboe.com/tradable-products/vix/vix-historical-data), monthly means of daily closes | rebuilt |
| Corporate bond spread, excess bond premium, its recession probability | Federal Reserve Board, [`ebp_csv.csv`](https://www.federalreserve.gov/econres/notes/feds-notes/updating-the-recession-risk-and-the-excess-bond-premium-20161006.html) | rebuilt |
| National Financial Conditions Index | Federal Reserve Bank of Chicago, [`nfci-data-series-csv.csv`](https://www.chicagofed.org/research/data/nfci/current-data), monthly means of weekly readings | rebuilt |
| Financial Stress Index | Office of Financial Research, [`fsi.csv`](https://www.financialresearch.gov/financial-stress-index/), monthly means | rebuilt |
| Overnight repo rate minus the rate on reserves | New York Fed’s [SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr) API, less the Board’s rate on reserve balances (on excess reserves before July 29, 2021; FRED `IORB`, `IOER`), daily in basis points, monthly means | rebuilt |
| Banks’ leverage ratio, unrealized securities gains and losses against tier 1 capital, uninsured deposits | Federal Deposit Insurance Corporation [BankFind API](https://api.fdic.gov/banks/docs/), sums over insured institutions with the Quarterly Banking Profile’s filters | rebuilt |
| Delinquent commercial real estate, credit card and mortgage loans at banks | Federal Reserve Board [charge-off and delinquency rates](https://www.federalreserve.gov/releases/chargeoff/) (FRED `DRCRELEXFACBS`, `DRCCLACBS`, `DRSFRMACBS`) | rebuilt |
| Bank loans to nonbank financial firms, percent of all loans | Federal Reserve Board [H.8](https://www.federalreserve.gov/releases/h8/) (FRED `LNFACBW027SBOG` over `TOTLL`), monthly means of weekly readings | rebuilt |
| Securities dealers’ leverage | Financial Accounts, total financial assets over equity capital (FRED `BOGZ1FL664090005Q`, `BOGZ1FL665080003Q`) | rebuilt |
| Household and business debt, percent of GDP | Financial Accounts table D.3 (`LA154104005`, `LA144104005`) over GDP | rebuilt |
| Household debt service ratio | Federal Reserve Board [household debt service ratios](https://www.federalreserve.gov/releases/housedebt/) (FRED `TDSP`) | rebuilt |
| Household debt 90 or more days past due | New York Fed [Household Debt and Credit Report](https://www.newyorkfed.org/microeconomics/hhdc) workbook, page 12 | rebuilt |
| Corporate interest coverage | Bureau of Economic Analysis table 1.14: (profits before tax + net interest) ÷ net interest, nonfinancial corporations | rebuilt |
| 10-year term premium (Adrian–Crump–Moench) | New York Fed, [`ACMTermPremium.xls`](https://www.newyorkfed.org/research/data_indicators/term-premia-tabs), monthly means of daily readings | rebuilt |
| Fed’s forward price-earnings ratio and equity premium | the Board’s [Financial Stability Report](https://www.federalreserve.gov/publications/financial-stability-report.htm) chart data, posted some months after each report, from a commercial earnings-forecast source; each report restates the whole history | recorded |
| Problem banks, percent of banks | the FDIC’s problem bank counts, assembled from each quarter’s profile workbook and four archived profiles in PDF | recorded |
| Leveraged funds’ net short Treasury futures | Commodity Futures Trading Commission Traders in Financial Futures, combined across contracts | recorded |
| Margin debt, percent of GDP | FINRA’s margin statistics workbook | recorded |
| AI spenders’ capital spending against their operating cash flow | five companies’ filings with the Securities and Exchange Commission | recorded |
| Federal debt, deficit and net interest (percent of GDP and of receipts) | the Congressional Budget Office’s historical budget data and the Treasury’s Monthly Treasury Statement (CBO’s website refuses automated downloads) | recorded |

And the series behind the recession signals, all rebuilt:

| signal | rebuilt from |
|:---:|:---:|
| 10-year minus 3-month Treasury yield | Federal Reserve Board H.15 monthly averages (FRED `GS10`, `TB3MS`); the bill is put on a bond-equivalent basis, the New York Fed’s way: 100 × (365 *d* ÷ 100) ÷ (360 − 91 *d* ÷ 100) |
| 10-year minus 2-year Treasury yield | H.15 monthly averages (FRED `GS10`, `GS2`) |
| New York Fed probability of a recession in 12 months | New York Fed, [`allmonth.xls`](https://www.newyorkfed.org/research/capital_markets/ycfaq), each probability moved back 12 months to the month of the yield spread behind it |
| Sahm rule | the Bureau of Labor Statistics’ unemployment rate (FRED `UNRATE`): the three-month average (at least two of the three months, the month itself among them) minus the lowest three-month average of the previous 12 months (at least 11 of them), rounded to two decimals; October 2025, when the household survey was not collected, has no reading |
| Initial jobless claims | the Labor Department’s weekly claims, seasonally adjusted (FRED `ICSA`), averaged by the month of each week’s Saturday |
| Excess bond premium’s recession probability | the Federal Reserve Board file above, in percent |
| Loan officer survey, large and mid-sized firms | Federal Reserve Board [Senior Loan Officer Opinion Survey](https://www.federalreserve.gov/data/sloos.htm) (FRED `DRTSCILM`) |
| Forecasters’ odds that GDP falls next quarter | Federal Reserve Bank of Philadelphia, [`mean_recess_level.xlsx`](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/anxious-index) (`RECESS2`) |

The page reads these from the agencies directly; where FRED is named here it republishes the agency’s numbers unchanged. One exception was found: FRED’s copy of SOFR lacks the rate’s first day (April 2, 2018), so the script reads the New York Fed’s own API.

**How close.** Exact, with some recorded inputs. On November 28, 2026 every number the script rebuilds matched the page’s data file ([data.json](https://econvitals.org/lab/risk-monitor/data.json)) to the six significant digits the file stores, with no tolerance: all 6,498 percentiles and the 32 latest ones; all 888 heat-map cells, 4,137 indicator values by quarter, 32 counts of quarters carried and 222 yearly cells; every one of the 66 alarms (its first and last period, length, kind, peak and lead), the 61 recessions judged, the 72 counts and the last month each signal was on; the 851 readings of the claims and loan officer series; the page’s own sample of 155 percentiles and cells; and 7,929 readings of the 30 rebuilt input series since 1990. The nightly check compares all of them.

Two points the page’s written definitions leave open, settled by the data file:

- **Each average works from rounded numbers.** Every number the page stores is rounded to six significant digits, and each step of the heat map averages the numbers the step before it stored: a quarter’s value is the mean of the rounded monthly percentiles, a cell the mean of the rounded quarterly values, a year the mean of the rounded cells. Averaging unrounded numbers instead moves the sixth digit in about 300 places.
- **A warned recession’s lead runs from the start of the alarm.** The warning is the alarm that was on in the 12 months before the peak; its lead is counted from that alarm’s first on-reading after the previous trough plus 3 months, not from its first reading inside the 12 months. So the 10-year/3-month spread warned of the 1980 recession 14 months ahead (its alarm began in November 1978), and of 1981–82 eight months ahead (counted from November 1980, after the 1980 trough).

The year of quiet between alarms is read as more than 12 months (4 quarters) between two on-readings, so 12 off months in a row start a new alarm. No signal’s record has a gap of exactly 12 months (or 4 quarters), so reading it as “12 or more” would give the same records today.

**What is not rebuilt here.**

- **The ten recorded inputs** in the table above. The Fed posts its forward price-earnings series from a commercial source and restates it whole with each report; the problem bank counts come from workbooks and archived PDFs; the AI spenders’ figures rest on rules for reading five companies’ filings that would be a second builder, not a check; and the budget series rest on CBO files that cannot be downloaded by a script. Positioning and margin debt come from the CFTC’s and FINRA’s public files and could be rebuilt; for now they are recorded too. Each is read from the page’s data file at run time, and its percentiles and heat-map values are rebuilt from those readings like any other.
- **The month in progress** of a daily or weekly series: the page stores the mean of the readings so far, which moves with each new day.
- **The rest of the page**: “Then and now”, what moved, the computed paragraph, the series shown but not scored (other than the eight behind the recession signals), the global indicators, Kalshi’s contracts, the yardsticks for how far stocks could fall and the S&P 500’s fall from its record (its daily closes come from a licensed feed and cannot be passed on), and the dated text kept by hand.

**Caveats** (from the page). A high percentile says where a measure stands against its own past, not that a crisis is coming or when, and a measure can stay high for years. A short history makes a percentile mean less: an indicator that began after 1990 is ranked only against the years it has. Today’s readings are the latest published figures and will be revised; the forecasters’ survey alone is as it was answered at the time. The thresholds for jobless claims and the loan officer survey are Econvitals’ own.
