# Real Net Interest

**On econvitals.org:** the net interest chart on [Fiscal](https://econvitals.org/fiscal/), and the series and its stat card in the [Fiscal Explorer](https://econvitals.org/tools/fiscal-explorer/). Method note: [Methods](https://econvitals.org/methods/#real-net-interest).

**What it is.** Part of every dollar of interest the government pays only compensates lenders for expected inflation, so it is not a real cost. Real net interest strips that part out, fiscal year by fiscal year:

> real net interest in year *t* = net interest in *t* − expected inflation in *t* × debt held by the public at the end of *t* − 1

Expected inflation is proxied by trailing five-year core PCE inflation — a window matched to the debt’s average maturity of roughly five to six years. Concretely, it is the annualized growth of the PCE price index excluding food and energy from the third calendar quarter five years earlier to the third quarter of year *t* (the quarter in which the fiscal year ends; each quarter is the average of its three months). Quarters BEA has published are BEA’s; after the last one, BEA’s level is grown at CBO’s projected quarterly rate, so CBO’s projection supplies the growth and not the level. Everything is on a fiscal-year basis (October–September) and shown as a percent of GDP, 1995–2036.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`; Treasury’s Fiscal Data API needs no key). Writes `output/real_net_interest.csv`: net interest, prior-year debt, expected inflation, real net interest and fiscal-year GDP, plus net interest and real net interest as a percent of GDP.

**Data.**

- Net interest and debt held by the public, 1990–2024: CBO’s historical budget data (`inputs/cbo_historical_budget_data_2026-02.csv`; OMB’s Historical Tables 3.1 and 7.1 give the same net interest figures).
- 2025–2036: CBO’s February 2026 baseline, Table 1-1 (`inputs/cbo_budget_projections_2026-02.csv`, which also carries CBO’s fiscal-year GDP).
- Fiscal 2026, a year Treasury has closed that CBO still projects: Treasury’s final Monthly Treasury Statement — net interest from Table 9, debt from Table 6 (“total borrowing from the public,” CBO’s own measure) — read from Treasury’s Fiscal Data API.
- Core PCE prices: FRED series `PCEPILFE` (BEA), monthly; CBO’s quarterly projection of the same index (2017 = 100) for 2023–2036 (`inputs/cbo_core_pce_projection_2026-02.csv`).
- GDP: FRED series `GDP` (BEA), averaged over the four quarters of each completed fiscal year; CBO’s projection after that.

The three CBO files are cut from CBO, *The Budget and Economic Outlook: 2026 to 2036* (February 2026), [www.cbo.gov/publication/61882](https://www.cbo.gov/publication/61882) — workbooks `51134-2026-02-Historical-Budget-Data.xlsx` (sheets 1 and 3), `51118-2026-02-Budget-Projections.xlsx` (Table 1-1) and `51135-2026-02-Economic-Projections.xlsx` (sheet “1. Quarterly,” row “Price index, PCE, excluding food and energy”). They ship here because CBO’s website refuses scripted downloads; `inputs/cut_inputs.py` shows exactly which cells each column came from. CBO data are U.S. government works and free to redistribute.

BEA revises GDP and core PCE prices, so the script reads both as FRED published them on November 1, 2026, the day the published series was built (`VINTAGE` at the top of `replicate.py`). Move that date when the series is rebuilt.

**How close.** Reproduces the published series exactly. The nightly check compares real net interest and net interest as a percent of GDP, 1995–2036, with the published Federal Debt Service series (the numbers behind the net interest chart on the Fiscal page), within 0.0001 percentage point; that file rounds to four decimals. In dollars the rebuilt series matches the Fiscal Explorer’s to within $1 million, and expected inflation matches to the sixth decimal.

The separate chart comparing CBO’s baseline with a preferred baseline (“Real Net Interest,” 2024–2036) was drawn from an earlier build — before fiscal 2026 closed, before BEA’s September 2026 GDP revision and with fewer quarters of BEA’s core PCE prices in hand: its CBO line differs by up to 0.09 point in 2026 and by 0.04 to 0.06 point in 2027–2030, and is identical from 2031. It is not part of the check.

**Caveat** (from the Methods page). The expected-inflation term is a proxy.
