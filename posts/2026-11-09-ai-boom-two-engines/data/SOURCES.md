# Data sources

Every input the post uses, frozen as it was when the post was written (November 5–8, 2026). All are public data. The main run reads only these files. `refresh/` re-pulls the ones that can be fetched from public sources and explains how to update the rest.

Dates are when the file was retrieved. Where a later retrieval was checked against the values used for the post, that is noted. `inputs.py` rebuilds the post’s derived inputs from these files and stops if they differ from `as_used/` by more than 1e-9.

## `bea_nipa_q.csv`: national accounts, quarterly

Bureau of Economic Analysis, National Income and Product Accounts. The file comes from BEA’s flat file of all quarterly NIPA series, <https://apps.bea.gov/national/Release/TXT/NipaDataQ.txt>. The version used was last modified November 4, 2026, so it includes the advance estimate for 2026Q3. Retrieved November 7, 2026; every value through 2026Q3 matches the values used for the post exactly. Units: millions of dollars at seasonally adjusted annual rates, except DPCCRG (index, 2017 = 100). Chained-dollar series are in millions of chained 2017 dollars.

| Column | Series | Table: line |
|:---:|:---:|:---:|
| A191RC | Gross domestic product | 1.1.5: 1 |
| A191RX | Real gross domestic product | 1.1.6: 1 |
| A007RC | Private fixed investment | 1.1.5: 8 |
| A008RC | Nonresidential fixed investment (“business investment”) | 1.1.5: 9 |
| A008RX | Real nonresidential fixed investment | 1.1.6: 9 |
| A011RC | Residential investment | 1.1.5: 13 |
| A011RX | Real residential investment | 1.1.6: 13 |
| A019RC | Net exports of goods and services | 1.1.5: 15 |
| A020RX | Real exports of goods and services | 1.1.6: 16 |
| A021RX | Real imports of goods and services | 1.1.6: 19 |
| DPCERX | Real personal consumption expenditures | 1.1.6: 2 |
| DPCCRG | PCE price index excluding food and energy | 2.3.4: 25 |
| B935RC | Private fixed investment, computers and peripheral equipment | 5.5.5U: 4 |
| C275RC | Private fixed investment, communication equipment | 5.5.5U: 5 |
| C314RC | Private fixed investment, communication structures | 5.4.5U: 23 |
| LA001282 | Private fixed investment, data centers (from 2020Q1) | 5.4.5U: 5 |

## `census_c30_private_sa_m.csv`: construction spending, monthly

U.S. Census Bureau, Construction Spending (C30), “Value of Private Construction Put in Place, Seasonally Adjusted Annual Rate”. The source is the time-series workbook <https://www.census.gov/construction/c30/xlsx/privsatime.xlsx>. Every column is kept, with the footnote digits dropped from the headers. Units: millions of dollars, seasonally adjusted annual rate, January 1993 to September 2026 (September is preliminary). The “Data center” column (part of “Office”) begins in January 2014. Retrieved November 5, 2026; a retrieval on November 7 was identical.

Used for:

* the data-center construction piece of the shock (quarterly averages of the monthly rates);
* the 2014–2019 data-center line in figure 2;
* figure 4’s construction bars and the construction numbers in the text.

## `fred_series.csv`: rates, prices and trade, monthly, weekly and daily

Retrieved November 7, 2026, from FRED (Federal Reserve Bank of St. Louis). Each series is FRED’s copy of the agency series named below. Every quarterly average through 2026Q3 matches the values used for the post exactly.

| `series` | FRED ID | What it is | Agency and series | Units, frequency |
|:---:|:---:|:---:|:---:|:---:|
| UNRATE | UNRATE | Unemployment rate | BLS, Current Population Survey, LNS14000000 | percent, monthly, SA |
| EFFR | EFFR | Effective federal funds rate | Federal Reserve Board, H.15 | percent, business days |
| DGS10 | DGS10 | 10-year Treasury, constant maturity | Federal Reserve Board, H.15 | percent, business days |
| RTWEXBGS | RTWEXBGS | Real broad dollar index | Federal Reserve Board, H.10 | index, Jan. 2006 = 100, monthly |
| MORTGAGE30US | MORTGAGE30US | 30-year fixed mortgage rate | Freddie Mac, Primary Mortgage Market Survey | percent, weekly |
| WPSFD43 | PPIDCS | PPI, final demand construction | BLS, WPSFD43 | index, Nov. 2009 = 100, monthly, SA |
| BOPGSTB | BOPGSTB | Balance on goods and services, BOP basis | Census Bureau and BEA, FT-900 | millions of dollars, monthly, SA |

Quarterly values are simple means of the observations in each quarter. The unemployment rate for 2025Q4 is the mean of two months: the October 2025 household survey was not conducted.

## `spf_median_ngdp_level.csv`: Survey of Professional Forecasters

Federal Reserve Bank of Philadelphia, Survey of Professional Forecasters: median forecasts of the level of nominal GDP (billions of dollars, annual rate), surveys of 2024Q1 through 2026Q3. Source: <https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/survey-of-professional-forecasters/data-files/files/median_ngdp_level.xlsx>. Retrieved November 7, 2026.

Used once. Nominal GDP for 2026Q4, which had not yet been published, is 2026Q3’s actual level times NGDP3/NGDP2 from the survey of 2026Q3 (August 2026). That is the survey’s growth from 2026Q3 to 2026Q4, and it scales the extrapolated 2026Q4 shock to a share of GDP.

## `trade_dc_goods_m.csv`: trade in data-center goods, monthly

Exports (`_x`) and imports (`_m`) of four end-use categories, seasonally adjusted, millions of dollars per month, 1999 to September 2026:

* computers (end-use 21300);
* computer accessories, peripherals and parts (21301);
* semiconductors (21320);
* telecommunications equipment (21400).

`dc_x` and `dc_m` are the four together. They are the end-use counterparts of HS 8471, 8473, 8541–8542 and 8517. They also include ordinary laptops and network gear, not only data-center equipment.

How it was built:

* Quarters come from BEA International Transactions, Table 2.1, quarterly and seasonally adjusted. The BEA API indicators are ExpGdsComp/ImpGdsComp, ExpGdsCompAccPeriAndParts/ImpGdsCompAccPeriAndParts, ExpGdsSemiconductors/ImpGdsSemiconductors and ExpGdsTelecomEquip/ImpGdsTelecomEquip. Each quarter is split evenly across its three months.
* The months after BEA’s latest quarter (July–September 2026) come from the Census FT-900 for September 2026, released November 4, 2026, exhibits 7 (exports) and 8 (imports). September and August are as printed. July is what the year-to-date total leaves.

This is the file as used for the post (built November 5, 2026). The even split within a quarter is exact for anything summed over whole quarters, which is everything this package uses.

## `stock_gain.csv`: the AI stock gain

Derived series, billions of dollars except `s`. One row per valuation date: the base (November 30, 2022, the day ChatGPT was released), each quarter end from 2022Q4 to 2026Q3, and the latest close used (November 5, 2026, labeled 2026Q4). Built November 5–6, 2026.

* `MV_<ticker>`: market value of each of Nvidia, Microsoft, Alphabet, Amazon, Meta, Broadcom and Oracle. This is shares outstanding times the closing price of the main listed class. Shares are all classes, from the cover pages of 10-K and 10-Q filings (SEC EDGAR, `dei:EntityCommonStockSharesOutstanding`). They are interpolated linearly between cover dates and put on a split-adjusted basis. Prices are official closes, not adjusted for dividends, from Nasdaq’s historical quotes.
* `sum7`: the seven together.
* `M`: total market value of corporate equities issued by U.S. corporations, from Federal Reserve Financial Accounts (Z.1) table L.223. It is LM103164105.Q plus LM793164105.Q, checked against LM883164105.Q. This total includes closely held companies. After the last Z.1 quarter (2026Q2), M is extended with the ratio of closing prices of the Vanguard Total Stock Market ETF (VTI). The base date is Z.1 2022Q4 times VTI’s November 30 to December 30, 2022 ratio. `M_source` says which applies.
* `R` = M − sum7 is the rest of the market.
* `G` = sum7 − sum7(base) × R / R(base) is the extra gain: what the seven are worth minus what they would be worth had they kept pace with the rest of the market. **The model shock is G/M by quarter.**
* `s`: the household share, Z.1 FL153064475.Q / M. FL153064475.Q is equities that households and nonprofits hold directly and indirectly. The 2026Q2 share is carried forward. `H` = s × G is the households’ part.
* `M_alt_public_ex_funds`: U.S. public companies only, LM883164115.Q less shares issued by investment funds (LM693164105.Q). `R_alt`, `G_alt` and `H_alt` follow the same formulas with M_alt. Figure 3 and the “two-fifths” figure use this measure.

Market prices are facts any vendor publishes; the package ships the market values, not the vendor quotes. `refresh/stock_gain_calc.py` recomputes every derived column from the market values. The differences are within $0.5 billion, from rounding.

## `z1_series_used.csv`: Financial Accounts series behind `M` and `s`

Federal Reserve Board, Financial Accounts of the United States (Z.1), release for 2026Q2 (September 2026). Millions of dollars, quarter-end levels, 2021Q4–2026Q2. Read from the Board’s Data Download Program, <https://www.federalreserve.gov/datadownload/>, November 5, 2026.

## `capex_booms_van_nieuwerburgh.csv`: figure 1

Stijn Van Nieuwerburgh, “Financing the AI Buildout,” Brookings Papers on Economic Activity, Fall 2026 conference draft, Table 1: average annual capital expenditure as a percent of GDP over each episode, as printed. The AI buildout figure for 2025–2032 is the paper’s projection. Paper: <https://www.brookings.edu/wp-content/uploads/2026/09/4c_Van-Nieuwerburgh.pdf>. `facts.json` independently recomputes the telecom-and-fiber figure (1.10) from BEA data.

## `as_used/`: the derived inputs exactly as used for the post

* `inv_excess.csv`: the model’s shock.
* `actual.csv` and `actual_extra.csv`: the actual series for the table. The 2026Q4 row of `actual.csv`, filled from the August 2026 SPF and quarter-to-date averages, is not used by the post.
* `fig2_*.csv` to `fig5_*.csv`: the data behind figures 2–5 as drawn.

The main run rebuilds the first three from the raw files above and checks that they match.

## The Federal Reserve Board’s FRB/US files (`../fed/`)

* `fed/data_only_package/LONGBASE.TXT`: the Board’s baseline database. History runs through 2026Q2, with the Board’s projection after that. It came from <https://www.federalreserve.gov/econres/files/data_only_package.zip>, which was last modified November 4, 2026. That copy was retrieved November 8, 2026, and is the one the post’s runs use. SHA-256: `c023c739f4179a70ca0ede84996539f8d2bf72170b9cc301afc89b95d2271a9e`. `fed/VINTAGE.json` records its date, size and history end.

  The Board replaces that download from time to time, and a newer LONGBASE.TXT gives different results, so use the bundled file. Drafts of the post before November 8, 2026 used the file last modified August 7, 2026 (history through 2026Q1; SHA-256 `2c1ac2d78d9c098b9a1e5e5dfa770401cfc6e580272a915138c1c6e2773b79fa`).
* `pyfrbus/` (the package) and `fed/pyfrbus_dist/` (its license, readme, setup file and model file): pyfrbus 1.1.1, from <https://www.federalreserve.gov/econres/files/pyfrbus.zip>, last modified February 26, 2026. The model file `models/model.xml` has SHA-256 `3227f4d2a1d48d6c59e055b11c719a2c40f29e2dfd5094601ec16c24fdd4f24b`. Both are U.S. Government works in the public domain.
