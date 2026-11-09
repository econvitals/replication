# Refreshing the data (optional)

The main run never uses the network. It reads the frozen files in `data/`, which are the data as they stood when the post was written. This folder is for anyone who wants to see how the results move when the agencies revise their numbers.

```
pip install openpyxl==3.1.5                       # only needed here, to read two Excel files
export FRED_API_KEY=...                           # free: https://fred.stlouisfed.org/docs/api/api_key.html
python refresh/fetch_public.py                    # writes data_refreshed/
DCBOOM_DATA=data_refreshed python run_all.py      # rebuild everything on the refreshed data
```

On refreshed data, `inputs.py` skips its comparison with the post’s inputs. `verify.py` will then flag any number that revisions have moved past the post’s rounding, which is the point of the exercise. The analysis window is fixed: data through 2026Q3, with 2026Q4 extrapolated. Newer quarters in a refreshed file are read but not used.

## What `fetch_public.py` refreshes

| File | Source | Key needed |
|:---:|:---:|:---:|
| `bea_nipa_q.csv` | BEA’s flat file of all quarterly NIPA series | no |
| `census_c30_private_sa_m.csv` | Census C30 workbook `privsatime.xlsx` | no |
| `spf_median_ngdp_level.csv` | Philadelphia Fed SPF, median NGDP levels | no |
| `fred_series.csv` | FRED API (copies of BLS, Federal Reserve, Freddie Mac and Census series) | free FRED key |

If a source fails, the script says so and copies the frozen file instead.

## What it does not refresh, and how to do it by hand

**`trade_dc_goods_m.csv`** (exports and imports of computers, computer parts, semiconductors and telecommunications equipment):

1. With a free BEA API key (<https://apps.bea.gov/API/signup/>), request dataset `ITA` with `Frequency=QSA` for these indicators: ExpGdsComp, ImpGdsComp, ExpGdsCompAccPeriAndParts, ImpGdsCompAccPeriAndParts, ExpGdsSemiconductors, ImpGdsSemiconductors, ExpGdsTelecomEquip and ImpGdsTelecomEquip. Split each quarter evenly across its months.
2. For the months after BEA’s latest quarter, download exhibits 7 (exports) and 8 (imports) of the current Census FT-900, <https://www.census.gov/foreign-trade/Press-Release/current_press_release/>. Take the latest month and the month before as printed. Any month left in between gets what the year-to-date total leaves.
3. Write the same columns as the frozen file: `<category>_x`, `<category>_m`, `dc_x`, `dc_m`, in millions of dollars per month.

**`stock_gain.csv` and `z1_series_used.csv`** (the AI stock gain):

1. **Shares outstanding** for each company: the cover-page count in each 10-K and 10-Q, from SEC EDGAR (`https://data.sec.gov/api/xbrl/companyconcept/CIK##########/dei/EntityCommonStockSharesOutstanding.json`). EDGAR asks for a descriptive User-Agent with contact details. For Alphabet and Meta, sum the share classes; their per-class counts appear only in each filing’s own XBRL instance. Interpolate linearly between cover dates, and put earlier counts on a split-adjusted basis (Nvidia 10-for-1 on June 10, 2024; Broadcom 10-for-1 on July 15, 2024).
2. **Closing prices** on each valuation date, from any market-data source: official close, split-adjusted, not dividend-adjusted. Use the main listed class for Alphabet (GOOGL) and Meta (META). You also need the Vanguard Total Stock Market ETF (VTI), which extends the market total past the last Z.1 quarter.
3. **Market totals** from the Federal Reserve Financial Accounts (Z.1) through the Data Download Program, <https://www.federalreserve.gov/datadownload/>: LM103164105.Q, LM793164105.Q, LM883164105.Q, FL153064475.Q, LM883164115.Q and LM693164105.Q.
4. **Compute.** Put the market values (shares × price), `M`, `M_alt_public_ex_funds` and `s` in a CSV laid out like `data/stock_gain.csv`, then run `python refresh/stock_gain_calc.py yours.csv data_refreshed/stock_gain.csv`. Definitions are in `data/SOURCES.md`.

**The FRB/US baseline** (`fed/data_only_package/LONGBASE.TXT`) is deliberately not refreshed. The Board replaces its download from time to time; the bundled file is the one it posted on November 4, 2026. Every effect in the post is measured against the bundled baseline. A newer one changes the experiment itself, not just the data, so swap it in only on purpose.
