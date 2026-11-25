# Econvitals replication code

[Econvitals](https://econvitals.org) charts the U.S. economy, mostly with the agencies’ own numbers. Some of what it shows it builds itself: underlying-inflation gauges, tracking estimates of GDP, PCE and CPI before they are released, decompositions, and analytic tools. The [Methods page](https://econvitals.org/methods/) says in words how each one is made. This repository is the code: for each of those measures, a short script that rebuilds it from public data, and a check, run every night, that the script still gives the numbers the site shows.

It also holds the **[track record](history/)** of Econvitals’ forecasts: every GDP, PCE and CPI tracking estimate beside the official number it was anticipating, as files you can download.

Everything here is free to use for any purpose (CC0). Corrections and questions: [feedback@econvitals.org](mailto:feedback@econvitals.org).

## Getting started

1. Download the repository (green **Code › Download ZIP** on GitHub, or `git clone`).
2. Install Python 3.11 or later and the few packages the scripts use: `pip install -r requirements.txt`.
3. Get the free keys the scripts you want need, and set them as environment variables: `FRED_API_KEY` ([FRED](https://fred.stlouisfed.org/docs/api/api_key.html)), `BEA_API_KEY` ([BEA](https://apps.bea.gov/API/signup/)), `EIA_API_KEY` ([EIA](https://www.eia.gov/opendata/register.php)) and, for two scripts, `CENSUS_API_KEY` ([Census](https://api.census.gov/data/key_signup.html)). Each folder’s README says which it needs.
4. Run a measure: `python measures/real-wage-growth/replicate.py`. Results go to that folder’s `output/`.
5. Check everything against the live site: `python tools/check_all.py`.

Most scripts read agency data through FRED, which republishes the Bureau of Labor Statistics’, the Bureau of Economic Analysis’ and the Federal Reserve’s numbers unchanged; Econvitals itself reads the agencies directly, and the numbers are the same. Downloads are cached for a few hours in `~/.cache/econvitals-replication`, so rerunning a script while you read it costs nothing.

## How each folder is laid out

- `README.md`: what the measure is, where it appears on the site, the exact data it uses, and how closely the script matches the site.
- `replicate.py`: the script.
- `check.json`: which of the script’s outputs must match which published series, over how many recent dates, within what tolerance.
- `inputs/` (some folders): files that cannot be downloaded by a script, such as Congressional Budget Office workbooks (its website refuses automated downloads). All are U.S. government works or Econvitals’ own.
- `history.py` (tracking estimates): rebuilds that measure’s track record under `history/`.

Shared readers for the public data sources are in `common/`.

The one exception is [`simulator/`](simulator/): the Macroeconomic Simulator’s own engine, the Federal Reserve Board’s FRB/US model and data as the page’s runs were made from them, and a sample of those stored runs, with its own `requirements.txt` (Python 3.14) and a `verify.py` that rebuilds the sample, in place of `replicate.py`. It needs no network and no keys.

Folders under [`posts/`](posts/) are the same kind of exception: each is the replication package of one of [Jason’s Occasional Posts](https://econvitals.org/posts/), with its own frozen data, `requirements.txt`, `run_all.py` and `verify.py`, which checks the post’s numbers. They need no network and no keys. A post that rests on licensed data gets a partial package: all the code and the public data, with each licensed input described in the folder’s `licensed/README.md` but not included, and `verify.py` skipping the numbers that need one.

## What “matches” means

- **Exact**: the script reproduces the published series to the site’s rounding.
- **Exact, with some recorded inputs**: one input cannot be downloaded by anyone after the fact (a bank research median, a prediction-market price, a hand-assembled foreign figure), so it is read from Econvitals’ published record or shipped in `inputs/`; everything else is rebuilt and matches exactly.
- **Close, within a stated tolerance**: the method is rebuilt step for step but one piece cannot be identical (for example, a model re-estimated on today’s data, or a seasonal adjustment program the script replaces with a stand-in). The README states the tolerance and why.
- **Run by hand**: the script needs something the nightly check cannot have, such as microdata each user must request from IPUMS, or the measure is too large to rerun in full every night. The README says what is checked instead.

## The measures

| Family | Measure | Matches |
|:--:|:--:|:--:|
| Inflation | [Core PCE ex Housing and Used Vehicles](measures/core-pce-ex-housing-used-vehicles/) | Exact |
| Inflation | [Core Services CPI ex Shelter](measures/core-services-cpi-ex-shelter/) | Exact, with some recorded inputs |
| Inflation | [Econvitals Ecumenical Underlying Inflation](measures/ecumenical-underlying-inflation/) | Exact, with some recorded inputs |
| Inflation | [Econvitals Inflation Dispersion Index](measures/inflation-dispersion/) | Exact |
| Inflation | [Econvitals Inflation Skewness Index](measures/inflation-skewness/) | Exact |
| Inflation | [Econvitals PCE-Equivalent Inflation Measures](measures/pce-equivalent-measures/) | Exact, with some recorded inputs |
| Inflation | [Release-Day Estimate](measures/release-day-estimate/) | Close, within a stated tolerance |
| Inflation tracking | [Econvitals CPI Tracking Estimate](measures/cpi-tracking-estimate/) | Exact |
| Inflation tracking | [Econvitals PCE Tracking Estimate](measures/pce-tracking-estimate/) | Close, within a stated tolerance |
| GDP tracking | [Econvitals Composite GDP Tracker](measures/composite-gdp-tracker/) | Exact, with some recorded inputs |
| GDP tracking | [Econvitals Current-Quarter GDP Estimate](measures/gdp-estimate/) | Exact, with some recorded inputs |
| GDP tracking | [Econvitals Productivity Tracker](measures/productivity-tracker/) | Exact, with some recorded inputs |
| Wages | [Real Wage Growth](measures/real-wage-growth/) | Exact |
| Wages | [Econvitals Underlying Unit Labor Costs](measures/wage-tracker/) | Exact |
| Labor market structure | [Econvitals Employment Dispersion Index](measures/employment-dispersion/) | Exact |
| Labor market structure | [Labor Market Tightness Measures](measures/labor-market-tightness/) | Exact |
| Demographics | [Age-Adjusted Labor Market Rates](measures/age-adjusted-labor-rates/) | Exact |
| Demographics | [Aging Counterfactual](measures/aging-counterfactual/) | Exact |
| Demographics | [Labor Market by Group](measures/labor-market-by-group/) | Run by hand |
| Inflation-adjusted series | [Real National Income](measures/real-national-income/) | Exact |
| Inflation-adjusted series | [Real Oil and Mining Investment](measures/real-oil-mining-investment/) | Exact |
| Inflation-adjusted series | [Real Retail Sales](measures/real-retail-sales/) | Exact |
| Household finance | [House Prices Relative to Income and Rent](measures/house-prices-to-income-and-rent/) | Exact |
| Household finance | [Household Leverage by Wealth Group](measures/leverage-by-wealth-group/) | Exact |
| Household finance | [Loans to Lower Credit Scores](measures/loans-to-lower-credit-scores/) | Exact |
| Household finance | [Real Net Worth by Wealth Group](measures/real-net-worth-by-wealth-group/) | Exact |
| Fiscal | [Consolidated Debt Maturity](measures/consolidated-debt-maturity/) | Exact, with some recorded inputs |
| Fiscal | [Econvitals Fiscal Explorer](measures/fiscal-explorer/) | Exact, with some recorded inputs |
| Fiscal | [Real Net Interest](measures/real-net-interest/) | Exact, with some recorded inputs |
| Fiscal | [Treasury Duration Index](measures/treasury-duration/) | Exact |
| Yield decomposition | [Term Premium](measures/term-premium/) | Exact |
| Analytic tools | [CBO-2020 Counterfactual](measures/cbo-2020-counterfactual/) | Exact, with some recorded inputs |
| Analytic tools | [Inequality Explorer](measures/inequality-explorer/) | Run by hand |
| Analytic tools | [Market-Implied Expectations](measures/market-implied-expectations/) | Exact, with some recorded inputs |
| Analytic tools | [Policy-Cycle Phase](measures/policy-cycle-phase/) | Exact |
| Analytic tools | [Policy-Rule Tracker](measures/policy-rule-tracker/) | Exact |
| Analytic tools | [Recession Explorer](measures/recession-explorer/) | Exact |
| Analytic tools | [Trend Gaps](measures/trend-gaps/) | Exact |
| Composite indicators | [Econvitals Composite Activity and Inflation Indicators](measures/composite-indicators/) | Exact |
| International trade | [Econvitals Trade Balance Excluding Data-Center Goods](measures/data-center-trade/) | Exact |
| Analytic tools | [Macroeconomic Simulator](simulator/) | Exact; run by hand |
| Occasional Posts | [The AI Boom’s Two Engines](posts/2026-11-09-ai-boom-two-engines/) (November 9, 2026) | Exact; run by hand |
| Occasional Posts | [How Far Could Stocks Fall?](posts/2026-11-15-how-far-could-stocks-fall/) (November 15, 2026) | Partial: 60 of 155 numbers from public data; the rest need licensed data, described but not included; run by hand |
| Occasional Posts | [Consumers Can Handle a Stock Crash](posts/2026-11-17-consumers-stock-crash/) and its online appendix (November 17, 2026) | Exact for the post and the appendix (414 numbers, every appendix table cell); 3 numbers need the licensed S&P 500 and the county check is run by hand; run by hand |
Not here yet: the [Fedspeak Tracker’s](https://econvitals.org/tools/fedspeak/) hawk–dove score, whose method is described on the Methods page.

## The nightly check

Every night Econvitals reruns `tools/check_all.py`, which runs each script and compares its output with the data behind the live site. A series that stops matching (because a method changed without its script, or a publisher changed a series) is investigated the next morning. Changing how a measure is built on the site means changing its script here at the same time.

A revision alone is not a mismatch. The scripts download today’s numbers, while a page on the site was built from the numbers on the day it was last rebuilt, so when an agency revises its data the two can differ for a day or two with nothing wrong. A measure that stops matching while neither the site’s file nor the measure’s code has changed since the last night it matched is reported as waiting for the site to rebuild, not as a failure. Once the site has rebuilt its file, any difference that remains is a real one; so is a site file that has not caught up within a week (`site_rebuild_days` in a folder’s `check.json` changes that). `python tools/test_check_all.py` tests the rule.
