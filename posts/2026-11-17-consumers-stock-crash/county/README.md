# The county check (appendix Section 5.3, Table A17): code only, run by hand

This folder rebuilds Chodorow-Reich, Nenov and Simsek’s county design (*American Economic Review*, 2021) from public data and extends it through mid-2024. It is not run by `run_all.py`, for one reason: its inputs are about 10 GB of public files (mostly the BLS Quarterly Census of Employment and Wages), too large to freeze in a repository. The appendix’s Table A17 numbers were typed from this code’s output (`results.csv`), so `verify.py` does not rebuild them.

**To run it:**

```
export CENSUS_API_KEY=...          # free: api.census.gov/data/key_signup.html
bash 00_download.sh <work dir>     # every public input into <work dir>/raw/ (about 10 GB)
bash run_all.sh <work dir>         # about an hour; writes <work dir>/out/results.csv
```

You need pandas, numpy, pyarrow and pyfixest beyond this package’s `requirements.txt`.

**One private dependency.** `03_aggregates.py` reads three national series through the author’s own data library (`macrolib`), which is not public: FRED’s `CSUSHPISA` (Case-Shiller national house prices) and `CPIAUCSL` (CPI), and BEA NIPA Table 2.1’s compensation (`A033RC`) and proprietors’ income (`A041RC`), quarterly. Replace the three calls at lines 69–80 with your own FRED and BEA readers; everything else comes from the files `00_download.sh` fetches.

**What it does.**
1. `01_qcew_extract.py`: county and national payroll and employment by industry from the QCEW, 1990–2026Q1.
2. `02_irs_build.py`, `02b_irs_clean.py`: IRS Statistics of Income county dividends and wages, 1989–2023, with a fixed late-filer factor per county (the paper splices ZIP-code files year by year, which no longer works with today’s ZIP files).
3. `03_aggregates.py`: national returns (Ken French), the Shiller price-dividend ratio, the Gürkaynak–Sack–Wright yield curve, house prices, CPI and BEA income.
4. `04_census_api.sh`, `05_demog_scf.py`: county college shares and firm size (Census API), age structure (SEER) and the Survey of Consumer Finances relationships used to add stock held in retirement accounts.
5. `06_wealth.py`: county stock wealth relative to labor income, by quarter (dividends capitalized, adjusted for each county’s age mix).
6. `07_panel.py`, `08_results.py`, `common.py`: the regression panel and every estimate (local projections at horizons −4 to 10; county and state-by-quarter effects; the paper’s controls).

**The result the appendix uses:** payroll in retail, restaurants and hotels seven quarters after a stock-market gain equal to 1 percent of a county’s labor income, which in the paper’s calibration reads as cents of household spending per dollar of stock wealth. The rebuild gives 1.9 (paper 3.24) on the paper’s years; 0.6 for moves in 1992–2004 and 2.5 for 2005–2018; and 1.6 with standard error 1.6 for the five clean quarters since COVID (2023Q2–2024Q2).
