# Recession Explorer

**On econvitals.org:** the [Recession Explorer](https://econvitals.org/tools/recession-explorer/) tool. Method note: [Methods](https://econvitals.org/methods/#recession-explorer).

**What it is.** Every U.S. recession since 1948, as the National Bureau of Economic Research dates them, measured on some fifty series from the agencies that publish them. Every chart and table on the page is built from three things, and this script rebuilds all three from agency data for each of the twelve recessions:

- **The trend each baseline subtracts.** A baseline is the NBER peak plus the series’ own pace over a window ending at the peak: the 10 years before it (the page’s default), the 5 years before it, or the stretch since the last business-cycle peak at least five years earlier (“peak to peak”; for 1953–54 the 1948 peak, under five years earlier, is all there is), or nothing at all (“actual”). For a level the pace is compound growth per period; for the employment-population and participation rates it is the average change per period. The unemployment rate, the long-term share of the unemployed, jobless claims and the federal funds rate take no trend. A trend needs five years of data before the peak, and nothing before 1947 is used, so 1953–54’s 10-year trend rests on about six years and 1948–49 has no trend at all.
- **The gap from trend**, k months or quarters after the peak: for a level, 100 × ((x<sub>k</sub> ÷ x<sub>0</sub>) ÷ (1 + g)<sup>k</sup> − 1), in percent of trend; for a rate, x<sub>k</sub> − x<sub>0</sub> − k × d, in percentage points. From it, **the low point**: the worst gap within three years of the peak, or before the next recession began, under each baseline. The script also finds the trough, the plain series’ own low and the time until the series was back at its peak level.
- **What slowed GDP.** BEA’s contributions to real GDP growth, each quarter’s pieces scaled to add up to GDP’s growth computed from the level, compounded over the recession. Each piece’s trend contribution is its share of GDP’s growth over the baseline window times what trend growth would have added, and the gap is divided by the trend path at the trough. So consumption, business investment, housing, inventories, government and net exports add up exactly to real GDP’s gap from trend at the trough; the script asserts it for every recession and baseline.

The docstring at the top of `replicate.py` states these definitions in full, as the page’s own builder does.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY` and `BEA_API_KEY`; about five minutes the first time, mostly BLS’s 400 MB household-survey file and BEA’s pace limit, then seconds while the downloads are cached). It writes, to `output/`:

| file | what |
|:---:|:---:|
| `paces.csv` | the trend per month or quarter for every series, recession and baseline, and the periods it was taken over |
| `readings.csv` | the gap from trend for every series, recession and baseline, from two years before the peak to the end of the low-point window (75,000 readings) |
| `scorecard.csv` | for every series and recession: the trough, the plain low, the periods until it was back at its peak level, and the low point under each baseline |
| `low_points.csv` | the low points again, one row each |
| `contributions.csv` | for every recession and baseline: the seventeen contributions (the six and their pieces), their total, GDP’s actual change and the trend growth rate |
| `contributions_long.csv` | the contributions again, one row each |

It prints real GDP’s gap at the trough and its six pieces, against the 10-year trend, for each recession: 2007–09 is −8.0 percent, of which consumption −4.8 and net exports +2.3.

**Data.** All today’s vintage.

- **Bureau of Economic Analysis** (API): real GDP (Table 1.1.6), real gross domestic income and real final sales to private domestic purchasers (1.17.6), the quantity index of each component of GDP (1.1.3), the contributions to growth (1.1.2), monthly real consumer spending (2.8.3), real personal income excluding transfers and real disposable income (2.6), and real manufacturing and trade sales, which come in two underlying-detail tables on different bases (U002AU through 1996, U002BU from 1997) that share no month and are never joined.
- **Bureau of Labor Statistics** (bulk download files): payroll jobs (`CES0000000001`) and aggregate weekly hours of production and nonsupervisory workers (`CES0500000034`); hours worked in the nonfarm business sector (`PRS85006033`); and from the household survey, employment, the unemployment rate, the long-term share, prime-age participation and fifteen employment-population ratios (the `LNS` series listed in `replicate.py`).
- **Federal Reserve Board and Labor Department**, as FRED republishes them unchanged: industrial production (`INDPRO`, G.17), the federal funds rate (`FEDFUNDS`, H.15) and weekly initial claims (`ICSA`), averaged by month and divided by payroll jobs. The page reads these three from the Fed and the Labor Department directly; the numbers are the same.

**How close.** Exact. On November 17, 2026 every number the script rebuilds that the page’s data file ([data.json](https://econvitals.org/tools/recession-explorer/data.json)) also stores matched it: 1,354 trends to 15 significant digits; the 949 sample readings the page’s builder writes for checking (at the trough, the low point and a year before the peak) to the file’s six decimals; all 1,847 low points and every trough, plain low and return to the peak level; and all 765 contributions, 45 totals and 45 changes in real GDP. The nightly check compares all of them.

**What is not rebuilt here.**

- **The S&P 500.** The page’s daily closes come from Financial Modeling Prep under license and cannot be passed on, so stock prices and the largest fall around each recession are left out. Their arithmetic is the same as any other level’s, with no trend.
- **The Today view**, which treats the last 6, 12, 18 or 24 months as if they followed a peak. It is the same arithmetic with a hypothetical peak, and it moves with every release, so a nightly comparison would race the page’s once-a-day rebuild. For the same reason the comparison stops where the readings above stop, three years after each peak.
- **October 2025**, when the household survey was not collected: the page fills the month only so a reading can start from it (the September–November average), and draws nothing there. None of the readings here touch it.
- What the page builds on top: the household survey’s January population-adjustment marks, the quarter-by-quarter contributions, the contributions over the same number of quarters for the Today comparison, the rankings and averages, and every sentence and tile the page writes from the data (the page’s builder asserts each one).

**Caveats** (from the Methods page). Today’s readings are the latest published figures and will be revised. The household survey’s January population adjustments are shown as published.
