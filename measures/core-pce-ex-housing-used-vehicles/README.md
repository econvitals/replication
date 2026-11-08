# Core PCE ex Housing and Used Vehicles

**On econvitals.org:** [PCE inflation detail](https://econvitals.org/inflation/pcedetail/), the chart “Core PCE Inflation Excluding Housing and Used Autos”, and a row of the PCE-equivalent table on [Inflation › Underlying](https://econvitals.org/inflation/#underlying). Method note: [Methods](https://econvitals.org/methods/#core-pce-ex-housing-used-vehicles).

**What it is.** BEA publishes core PCE excluding housing but not a version that also strips out used vehicles, a notoriously volatile piece. Econvitals removes used motor vehicles from BEA’s core-ex-housing price index month by month using their share of spending — a Törnqvist chain, in which each month’s change is weighted by the average of that month’s and the previous month’s spending shares:

    s_t        = spending on used autos and used light trucks / (core PCE spending − housing spending)
    s̄          = (s_t−1 + s_t) / 2
    Δln(index) = [Δln(core PCE ex housing) − s̄ · Δln(price of used motor vehicles)] / (1 − s̄)

It is rebuilt from current BEA data on every run, so revisions flow through. Only the changes matter; the index starts at core PCE ex housing’s January 1959 level. A house aggregate, not a BEA series.

**Run it.** `python replicate.py` (needs a free `BEA_API_KEY`). Writes `output/core_pce_ex_housing_used.csv`: the index and its 1-month (`chg_1m_ann`, the chart’s bars) and 3-month (`chg_3m_ann`, the chart’s line) changes at an annual rate. The calculation is `core_pce_ex_housing_used_vehicles` in [`common/inflation.py`](../../common/inflation.py), shared with the Ecumenical measure.

**Data.** All monthly, from the BEA API:

- Table 2.8.4, `IA001176` — PCE excluding food, energy, and housing (chain-type price index).
- Table 2.4.4U, `DNPVRG` — price index for net purchases of used motor vehicles.
- Table 2.4.5U, `DNPURC` + `DUTRRC` — spending on used autos and used light trucks; `DPCCRC` — PCE excluding food and energy; `DHSGRC` — housing.

**How close.** Reproduces the published series to the last published digit over its whole history (812 months, February 1959 through September 2026, as of November 2026); the nightly check compares both columns within 0.0001 percentage point (the site rounds to four decimals). The index is rounded to six decimals before taking changes, as Econvitals stores it; without that, a few changes in 1959–61, when the index is near 16, differ by 0.0001. Monthly changes match an earlier Stata build of the same series to about 0.001 pp.
