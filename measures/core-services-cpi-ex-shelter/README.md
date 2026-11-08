# Core Services CPI ex Shelter

**On econvitals.org:** a row of the CPI PCE-equivalent table on [Inflation › Underlying](https://econvitals.org/inflation/#underlying), and one of the seven measures in the CPI-based [Ecumenical Underlying Inflation](../ecumenical-underlying-inflation/). The full series is published as `data/core-services-ex-shelter.json` in the [Econvitals data repository](https://github.com/econvitals/econvitals-data). Method note: [Methods](https://econvitals.org/methods/#core-services-cpi-ex-shelter).

**What it is.** BLS’s published “services less rent of shelter” still contains energy services, which is not what economists mean by core services ex shelter. Econvitals strips the full shelter index out of core services (services less energy services) using BLS’s relative-importance weights, as a chained removal:

    growth_t = [H · (B_t / B_t−1 − 1) − I · (C_t / C_t−1 − 1)] / (H − I)

where B is core services, C is shelter, and H and I are their relative-importance weights in the previous month. A month for which BLS published no weight (October and November 2025, around the shutdown) uses the last weight it did; BLS collected no prices for October 2025, so that month has no index and November’s change is measured from September.

BLS publishes those weights monthly only from March 2012, so the series is rebuilt from 2012 on with a pinned earlier history: January 1990 to March 2012 is Econvitals’ recorded index (`inputs/cses_index_1990_2012.csv`), and the rebuilt part is joined to its March 2012 level. That history is safe to fix, since CPI data that old no longer revise.

It does not match the official “supercore” series and is not meant to. The chart titled “Services CPI Inflation Excluding Rent of Shelter” on the [Inflation › CPI](https://econvitals.org/inflation/#cpi) page and the CPI detail page is BLS’s own published series (`CUSR0000SASL2RS`), not this one.

**Run it.** `python replicate.py` (no key needed). Writes `output/core_services_cpi_ex_shelter.csv`: the index and its 1-month (`chg_1m_ann`) and 3-month (`chg_3m_ann`) changes at an annual rate, plus the 12-month change (`chg_12m`). The calculation is `core_services_cpi_ex_shelter` in [`common/inflation.py`](../../common/inflation.py), shared with the Ecumenical and PCE-equivalent folders.

**Data.** From BLS’s public bulk files at download.bls.gov (`cu.data.20.USCommoditiesServicesSpecial`, `cu.data.12.USHousing` and `cu.aspect`):

- `CUSR0000SASLE` — services less energy services, seasonally adjusted index.
- `CUSR0000SAH1` — shelter, seasonally adjusted index.
- Relative importance (the “I” aspect) of `CUUR0000SASLE` and `CUUR0000SAH1`; BLS publishes it on the not-seasonally-adjusted series, monthly from March 2012.

**How close.** Reproduces the published series to the last published digit over its whole history (438 months, February 1990 through September 2026, as of November 2026), including both sides of the March 2012 join; the nightly check compares both columns within 0.0001 percentage point (the site rounds to four decimals). Marked “recorded inputs” because the history before March 2012 is a recorded file rather than something a script can fetch: BLS’s public files do not carry the monthly weights for those years.
