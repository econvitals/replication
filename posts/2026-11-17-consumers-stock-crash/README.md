# Replication package: “Consumers Can Handle a Stock Crash”

This package reproduces the numbers, the table and the figures in “Consumers Can Handle a Stock Crash,” Part 3 of Jason Furman’s series *The AI Boom and Its Risks* on Econvitals (November 2026), and in its online appendix, written by Claude at his direction. It starts from frozen public data and ends by checking each rebuilt number against the post and the appendix.

**On econvitals.org:** the post, and its online appendix at the post’s address followed by `appendix/`. [Links added at publication.]

**How close.** Exact, with two exceptions described below. `python run_all.py` rebuilds every number in the post and the appendix from the frozen inputs, redraws the figures and ends with `verify.py`, which checks the post’s and the appendix’s numbers and compares every cell of the appendix’s tables with the published page. On November 16, 2026 it ended `verify: 414 PASS, 0 FAIL, 17 SKIPPED, 88 CITED` (519 numbers), and all 1,137 table cells were identical to the published page. The 17 skipped rows are the county check (14) and three numbers that rest on the licensed S&P 500 (3); the 88 cited rows are quotations of other people’s work and the post’s own assumptions (the sizes of the market falls).

**The two exceptions.**
* **The S&P 500 is licensed**, so three numbers that rest on it are skipped unless you supply the index yourself: the correlation of yearly changes in real stock and real house prices (0.16), the market’s rise of “nearly 40 percent” in 1987 before the crash, and the S&P 500’s falls of “just under 20 percent” marked in Figure 1. See `licensed/README.md`.
* **The county check** in the appendix (Section 5.3, Table A17) rests on about 10 GB of public files. Its code and download script are in `county/`, run by hand; its numbers are not rebuilt by `run_all.py`.

**Keys.** None. Nothing in the main run uses the network.

## What the post and the appendix do

The post asks how much a fall in stock prices would cut consumer spending, and so GDP growth, if the AI boom turns out to be a bubble. Its central claim is that households have spent only about 1 cent of each dollar of their recent stock gains, much less than the roughly 3 cents the literature finds historically, so a fall would take less off spending than history suggests. It gets there four ways: a back-of-the-envelope comparison of spending and stock wealth relative to income; the Federal Reserve Board’s FRB/US model, whose consumption equations are run on the data since 2019; a consumption function estimated on 1955–2019, projected forward; and the same consumption function estimated over rolling 20-year windows. Its Table 1 turns each into a hit to GDP growth after falls of 25, 35 and 50 percent.

The appendix reviews the literature, then documents the consumption function in full: the specification and estimates in five samples, diagnostics, the speed of adjustment, sensitivity to the specification, the projection since 2019 and its dependence on the starting point, the method’s out-of-sample record, gains versus losses, change over time (rolling and expanding samples, break tests), the post’s other approaches and how Table 1 is built.

## What is in the package

```
run_all.py                     one entry point: rebuilds everything, then runs verify.py
verify.py                      checks every rebuilt number (expected.csv) and every appendix table cell
expected.csv                   every number in the post and in the appendix's text, typed from them, with its sentence
expected_appendix_tables.csv   every cell of the appendix's tables, read off the published page
metric_map.csv                 which computed number each row of expected.csv is checked against
requirements.txt               exact package versions (Python 3.14)
wealth/                        the code, run in this order by run_all.py
  build_panel.py                 the quarterly panel (output/panel.csv) from the frozen series
  common.py                      variable definitions and the two workhorse regressions
  rolling.py                     fixed periods, rolling windows, break tests, era estimates
  asymmetry.py                   gains versus losses in the changes model
  literature_specs.py            published specifications on today's data (the constant-elasticity model)
  frbus_since_2019.py            FRB/US's consumption equations run from 2019 on the Board's data
  rules_since_2019.py            the simple rules, the consumption function and FRB/US since 2019
  cf_calc.py, cf_extras.py       the consumption function: estimates, diagnostics, projection, out-of-sample record
  expanding_rolling.py           the stock coefficient through each quarter, and over rolling 20-year windows
  appendix_numbers.py            the anchors, the back-of-the-envelope bases, FRB/US's cents and Table 1
  appendix_tables.py             every table in the appendix, rebuilt
  post_numbers.py                the post's descriptive numbers (stock declines, 2001, 1987, stock values, ownership, Forbes)
  collect.py                     every number in one file
  post_figures.py, appendix_figures.py, housestyle.py   the figures (plain matplotlib)
data/                          frozen inputs; data/SOURCES.md documents each one
licensed/README.md             the one licensed input, described but not included
county/                        the county check: code and download script, run by hand (see its README)
```

## How to run it

You need Python 3.14 (tested with 3.14.8 on macOS, Apple silicon); it should run unchanged on Linux.

```
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_all.py
```

It takes under a minute (about 40 seconds on an Apple M1 in a fresh environment). `python run_all.py --no-figures` skips the figures. Every step can also be run on its own from this folder, in the order of `run_all.py` (for example `python wealth/cf_calc.py`); most read the outputs of earlier steps.

## What you should get

Everything is written to `output/`: the panel, every regression output (CSV and JSON, named as in the research code), `numbers.json` (the numbers `verify.py` checks), `all_numbers.json` (everything computed, about 5,000 numbers), `appendix_tables.json`, `figures/` (Table 1 and Figures 1–7 of the post, Figures A1–A5 of the appendix) and `verify_report.csv`.

**What verify checks.**
* `expected.csv`: every number in the post’s text, Table 1 and figure labels, and in the appendix’s prose, each typed from the post or the appendix itself, never from this package’s output, with the sentence or label it comes from. A rounded number passes if the rebuilt value rounds to it (half a unit of the last printed digit). Ranges and qualitative statements are made explicit as bounds, and the `note` column says how. Numbers quoted from other people’s work (the literature, an earlier post in the series, market prices) are marked `CITED:` and listed but not checked.
* `expected_appendix_tables.csv`: every cell of the appendix’s Tables A2–A16 and A18–A20 as published, compared as printed text with the rebuilt table. The literature table (A1) and the county table (A17) are typed from the papers and the county study, so they are not compared.

**Figures.** The figures are drawn with plain matplotlib from the rebuilt numbers. They show the same series as the published images but not their exact look (the house chart style is not part of this package).

## Notes on the method and the data

* **Timing.** Wealth is measured at the end of the previous quarter, so it is known before the quarter’s spending decisions. Spending and income are annual rates; each wealth coefficient times 100 is cents of annual spending per dollar of wealth.
* **The pandemic.** Any regression that reaches 2020 includes one dummy for each quarter from 2020Q1 to 2021Q2. `expanding_rolling.py` also reports estimates that drop 2020–2021 entirely.
* **FRB/US since 2019.** The Board’s equations for spending on nondurables and services (ECO) and durables (ECD) are simulated from 2019Q4 with the actual paths of their inputs from the Board’s November 4, 2026 data package and each equation’s residual held at its 2015–2019 average (the durables residual is persistently negative, so zero would bias it); housing services are taken as given and total spending is aggregated with the model’s own weights.
* **FRB/US scenarios.** Table 1’s FRB/US columns and Figure 7 use the Econvitals Macroeconomic Simulator’s stored run of a permanent 30 percent fall in stock prices, scaled linearly to 25, 35 and 50 percent and by 1.34 to today’s household stock wealth (stocks’ share of household wealth now against the run’s baseline). The runs themselves come from the Simulator’s engine, replicated in this repository’s `simulator/` folder.
* **Table 1’s stock wealth** is households’ directly and indirectly held corporate equities at the end of 2026Q2 in the September 2026 Financial Accounts ($74.0 trillion). The original run typed $74,005 billion; the release says $74,027 billion; no printed number changes.
* **Figure 1.** The whole U.S. market, price only: Ken French’s daily value-weighted return less the S&P 500’s dividend yield. A decline starts at a 20 percent fall from the running peak and ends at the lowest close once the index is 20 percent above it; two legs are one decline when the rally between them lasted under six months and made no new high. A decline goes with a recession when an NBER peak falls between six months before and 13 months after the stock peak.
* **Figure 2.** Each component’s contribution to real GDP growth from the business-cycle peak to the trough, less what its average contribution over the previous ten years would have given; the 1980 and 1981–82 recessions are combined.
* **Business investment in 2001** uses BEA’s quantity index, since BEA’s chained-dollar component series start in 2007.

The FRB/US simulations here were run by the author. They are not the Federal Reserve’s, and the Federal Reserve has not reviewed or endorsed them.
