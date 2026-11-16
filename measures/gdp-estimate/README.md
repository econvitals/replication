# Econvitals Current-Quarter GDP Estimate

**On econvitals.org:** [Home › GDP](https://econvitals.org/#gdp) (the Econvitals estimate card), [GDP › Current-quarter tracker: track record](https://econvitals.org/gdp/#tracker) (its own column) and the [GDP Trackers tool](https://econvitals.org/tools/gdp-trackers/) (components, path and accuracy). Method note: [Methods](https://econvitals.org/methods/#gdp-estimate).

**What it is.** A mechanical estimate of what BEA’s advance GDP release will say, built the way BEA builds it. Each component (consumer goods and services, equipment, structures, housing, government, inventories and trade) is taken from the same monthly source data BEA uses (monthly PCE, retail sales, factory shipments, construction spending, inventories, the trade report and payrolls), translated into what BEA prints by a regression on BEA’s own history since 2012 (a “bridge”), weighted by its share of GDP and summed. A month BEA will not have on release day is filled by a stated rule: the trailing-12-month trend for the growth lines, the last level for inventories and trade; federal spending and intellectual property, which have no monthly reader, continue at the average of their last four published quarterly growth rates. Because BEA’s first print has on average come in about 0.35 percentage point below today’s revised figures, that gap is added back, spread across the components in proportion to each one’s own average first-print gap. In a real-time back-test over 47 quarters the error on the last day before the release averaged 0.91 point, against 0.75 for GDPNow, and it beat GDPNow one to two weeks out. It has been a leg of the [composite tracker](../composite-gdp-tracker/) since October 19, 2026, at a fixed 10% weight.

**What this folder holds.** Econvitals’ own engine, the code that makes the estimate the site shows, exported from Econvitals’ production code whenever it changes. The code is unchanged except where it fetches data: there, each in-house reader is replaced by a reader of the same public numbers (`engine/public_doors.py`), and the two places that look up an API key read it from the environment. Comments that pointed to Econvitals’ internal systems have been reworded. `replicate.py` runs the engine and sets the result beside the estimate on the site.

```
README.md          this file
replicate.py       reruns the engine on public data and compares it with the published estimate
check.json         how the repository’s nightly check compares it (see “How close”)
engine/
  model.py           the estimate: each component bridged, weighted by its share of GDP and summed; the first-print adjustment
  components.py      each component’s monthly sources turned into the quarter’s indicator, with the fill rules
  bridge.py          the bridges: least squares of what BEA printed on each component’s indicators, 2012 on
  sources.py         every source series by name, where it comes from, and its saved copy
  eits.py            the Census Bureau’s economic-indicators API (retail sales, factory shipments, construction, inventories, trade)
  calendar.py        release calendars: which months of which report a date could see, from FRED and ALFRED
  vintages.py        ALFRED’s archive of past versions: BEA’s first prints of each component
  public_doors.py    where each source is read in this copy: BEA’s API, FRED, the Atlanta Fed’s GDPNow workbook
```

## Run it

You need Python 3.11 or later and the repository’s `requirements.txt` (pandas, numpy, requests, openpyxl), and three free keys as environment variables: `FRED_API_KEY`, `BEA_API_KEY` and `CENSUS_API_KEY` (links in the repository’s README). From this folder:

```
python replicate.py
```

It takes five to seven minutes, most of it downloads (measured 2026-11-15 on an eight-core Apple M1, in a fresh environment): it reads about forty monthly series from the Census Bureau, BEA and FRED, five BEA tables (BEA asks for a pause between downloads), FRED’s release calendars, ALFRED’s archive of BEA’s first prints and the Atlanta Fed’s GDPNow workbook. Downloads are kept for a few hours, so a second run is quick. It prints the estimate for the quarter in progress, the first-print adjustment, each component’s share of GDP, growth rate and contribution beside the site’s, and the difference, and writes:

- `output/estimate.csv`: the estimate, the sum of the components before the first-print adjustment, and the adjustment.
- `output/components.csv`: each component’s share of GDP, growth rate (or, for inventories and net exports, its contribution) and contribution, in percentage points at an annual rate.
- `output/first_print_gaps.csv`: BEA’s advance estimate, as the Atlanta Fed records it beside GDPNow, minus today’s BEA figure, for every quarter since 2011; `used` marks the quarters the adjustment averages (at least four quarters before the one being estimated, so each has been through an annual update; 2020 Q2 and Q3 left out).

`python replicate.py --refit` also fits the bridges afresh on today’s data and writes `output/refit.csv` (below). To look inside, run the engine directly, from this folder: `python -m engine.model 2026Q4` prints the component table for that quarter (with a fit of the bridges on today’s data, which `engine/bridge.py` writes to `data/ref/` the first time).

## What is computed here, and what is recorded

Everything is computed here from public data except the bridge coefficients, which are read from the site’s published data (`house.bridges` in `tools/gdp-trackers/data.json`): every component’s indicator from its sources, the quarter’s shares of GDP, the first-print adjustment (from the Atlanta Fed’s record of BEA’s advance estimates and BEA’s current figures) and how it is spread across the components (from ALFRED’s archive of BEA’s first prints), and the sum.

The coefficients are recorded because Econvitals refits the bridges whenever BEA’s published history changes (an annual update, a second or third estimate, a new quarter), from the source data as they stood that day. Between BEA’s releases the agencies revise their monthly data, and a quarter can become complete in a source after BEA’s release, so a fit made on a later day generally differs. `--refit` shows by how much. On November 15, 2026, a fit on that day’s data put the fourth-quarter estimate 0.06 point lower than the coefficients fit on October 29 (the day of BEA’s advance estimate for the third quarter): September’s construction spending had come out since, so the new fit includes the third quarter for structures, housing and state and local government, and revised imports of capital goods moved the equipment bridge.

## How close

Compared every night (`check.json`) with the estimate the site shows: the headline (the Econvitals estimate in the tool’s tracker table) and each component’s share of GDP, growth rate and contribution, within 0.0001 point, which is the site’s four decimals. The comparison is made only when this run sees the data the published estimate saw: the same quarter in progress, and no report the engine reads printed after the day the site’s estimate was made (the site updates three times each weekday). Otherwise `replicate.py` writes its tables without rows and says why, and the check reports nothing to compare that night rather than a match.

## Data

- **BEA** (API, NIPA tables): T20806, real personal consumption expenditures by month; T10101, T10102, T10105 and T10106, real GDP and its components by quarter: percent changes, contributions, current dollars and chained dollars.
- **Census Bureau** economic-indicators API: retail sales (`marts`), factory shipments and inventories, full and advance (`m3`, `advm3`), construction spending (`vip`), wholesale, retail and total business inventories and the advance reports (`mwts`, `mrts`, `mtis`, `mwtsadv`, `mrtsadv`), and the trade report and the advance goods report (`ftd`, `ftdadv`). Census international-trade API: nonmonetary gold (HS 7108 and 7115) and capital goods except automotive (end use 2).
- **BLS**, through FRED, which republishes its series unchanged (`public_doors.BLS_ON_FRED` lists each): the consumer price indexes for goods less food and energy, food at home and gasoline; the producer price indexes for private capital equipment and finished goods less food and energy; import and export price indexes; state and local government payrolls; and aggregate weekly hours in private service-providing industries.
- **Census Bureau construction-spending spreadsheet** `pubsatime.xlsx` (census.gov/construction/c30): total public construction spending, seasonally adjusted annual rate, which the economic-indicators API does not carry seasonally adjusted.
- **FRED**: the release calendars of each report; ALFRED, the archive of past versions, for the day each month of a report first appeared and for BEA’s first prints of each component; and public construction spending (`TLPBLCONS`, the same series) only if Census’s spreadsheet cannot be read.
- **The Atlanta Fed’s GDPNow workbook** (`GDPTrackingModelDataAndForecasts.xlsx`): BEA’s advance estimates, unrounded, from the `TrackRecord` sheet, dated from the `TrackingArchives` sheet. `TrackRecord`’s own release-date column misdates three quarters: it gives September 30 for BEA’s releases of October 30, 2024 and October 29, 2026, and October 30, 2020 for October 29. Until November 15, 2026 Econvitals’ reader dropped the rows it could not date, so the site’s adjustment for the fourth quarter of 2026 averaged 54 quarters (−0.3556 point); it now keeps them, as this copy does (−0.3560, over 55).

## Caveats

- FRED republishes BLS’s numbers within hours of a release, not at the moment of it; run the same morning as a BLS release and FRED may not have it yet.
- What is not here: the real-time back-test (it needs ALFRED’s version of every input as it stood on each of about 600 release days, and runs for hours); the path of the estimate through the quarter that the GDP Trackers tool draws, which is that back-test’s engine run on each day of the quarter; and Econvitals’ tracking of BEA’s second and third estimates of the quarter it last published.
