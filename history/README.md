# Track records

Every forecast and tracking estimate Econvitals publishes, kept beside the official number it was trying to anticipate. These files are rebuilt every night from Econvitals’ own records and published files, and a month is added only once the official figure for it is out, so nothing here is a forecast of anything still unknown. Download any file directly, or the whole repository with the green **Code › Download ZIP** button on GitHub.

Files marked **back-test** are simulations, not live records: the method run for past months using only the data available at the time. They say how the method would have done; the other files say how it did.

| File | What it holds | Live or back-test | Starts |
|:--:|:--:|:--:|:--:|
| `gdp-tracking.csv` | Composite GDP Tracker, every day, with each leg | Live | October 2026 |
| `gdp-tracking-scored.csv` | Composite and legs against BEA’s advance estimate | Live | Q3 2026 |
| `gdp-tracking-backtest.csv` | GDPNow, the New York Fed nowcast and their average | Back-test | Q1 2023 |
| `pce-tracking.csv` | PCE tracking estimate at each stage, against BEA’s first print | Live | September 2026 |
| `pce-tracking-backtest.csv` | PCE tracking estimate, real-time simulation | Back-test | October 2017 |
| `cpi-tracking.csv` | CPI tracking estimate, twelve cuts, against BLS’s first print | Live | October 2026 |
| `cpi-tracking-backtest.csv` | CPI tracking estimate, every month since 2015 | Back-test | January 2015 |
| `release-day.csv` | Release-morning median and trimmed-mean estimates, against the Fed banks’ figures | Live | July 2026 |

## GDP tracking

`gdp-tracking.csv` has one row per day per quarter of the Econvitals Composite GDP Tracker as published since October 19, 2026: `date`, `quarter`, `composite` (percent, annual rate), `composite_shown` (the one-decimal reading the site prints, from October 28), `band` (± the typical miss at that horizon), `days_to_release` (to BEA’s advance estimate; blank before BEA schedules it), then for each leg (`gdpnow` = Atlanta Fed GDPNow, `nyfed` = New York Fed Staff Nowcast, `street` = median of Wall Street tracking estimates, `house` = the Econvitals Current-Quarter GDP Estimate) its `_value` (after the half-move nudge), `_as_of` (the date of its latest reading) and `_weight`, plus `street_firms` (how many firms the median covers) and `key` (date and quarter, unique).

`gdp-tracking-scored.csv` has one row per quarter once BEA’s advance estimate is out: `advance_estimate`, `release_date`, `scored_from` (the last day before the release), and the composite’s and each leg’s value and `_miss` (value minus the advance estimate, percentage points).

`gdp-tracking-backtest.csv` is a back-test, not a live record: GDPNow, the New York Fed nowcast and their plain average (`average_of_two`) on the New York Fed’s last Friday before each advance estimate since 2023 (`reading_date`), from the two banks’ own archives, with each one’s miss. The live composite’s weighting is not applied.

Rebuild: `python measures/composite-gdp-tracker/history.py`.

## PCE tracking

`pce-tracking.csv`: every Econvitals PCE tracking estimate recorded with the CPI in hand and before BEA’s release, one row per month and stage (`post_cpi`, `post_ppi`, `post_import`), beside BEA’s first print and the miss (estimate minus first print). All values are one-month percent changes, not annualized. `core` is the number shown, including the first-print offset; `core_before_offset` is the sum before it. Columns: `record`, `target_month`, `stage`, `sources_in`, `estimated_at` (Eastern time, with its offset), `bea_release_date`, `known_share_of_core`, `core_offset_bp`, `core_before_offset`, then for each of overall, core, core ex housing, core ex housing and used vehicles, core services ex housing, market-based core, median and trimmed mean: the estimate, `_first_print` and `_miss`. A month appears only after BEA has published it.

`pce-tracking-backtest.csv` (back-test): the method rerun for each month from late 2017 with only the BEA data that existed before that month’s CPI, scored against BEA’s first print. No first-print offset is applied.

## CPI tracking

`cpi-tracking.csv`: every CPI tracking estimate, one row per month per day it was made, for twelve cuts (one-month and 12-month changes), beside BLS’s first print and the miss. `last_before_release` marks the final estimate. The estimate is made a few days before each CPI release and is not shown on the site beforehand; a month appears here only after BLS has published it.

`cpi-tracking-backtest.csv` (back-test): the estimate of every month since 2015, each made only from earlier data (with today’s seasonal factors, since BLS does not keep old ones for the components), beside BLS’s and the Cleveland Fed’s published figures. BLS revises five years of seasonal factors each February, after which this file is regenerated.

## Release-day estimates

`release-day.csv`: for each month, the release-morning Econvitals estimate of median and trimmed-mean CPI and PCE that the site showed before the Cleveland and Dallas Feds posted their own, and the bank’s figure that replaced it, with the times each was shown, in the charts’ units (one-month change, annual rate).

## What is not here

Econvitals does not keep a record of the prediction-market expectations it shows on [What Forecasters Expect](https://econvitals.org/tools/forecasts/): each card is replaced when its release comes out. Forecasts Econvitals reads from private sources are never published.
