# Real National Income

**On econvitals.org:** [GDP components detail › Other measures](https://econvitals.org/gdp/gdpdetail/#sec-other), the real national income chart. Method note: [Methods](https://econvitals.org/methods/#real-national-income).

**What it is.** BEA publishes national income (the incomes earned in producing output: compensation, profits, rents, interest and proprietors’ income, net of depreciation) only in current dollars. Econvitals deflates it by the GDP price index to get a real series and shows its 1-quarter growth at an annual rate and its 4-quarter growth, so it can be read beside real GDP and real gross domestic income. BEA publishes no official real national income, and the GDP price index is one reasonable deflator among several.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). Writes `output/real_national_income.csv`.

**Data.** FRED series `NICUR` (national income, BEA table 1.7.5) and `GDPCTPI` (GDP chain-type price index, BEA table 1.1.4). BEA publishes national income only with its second GDP estimate, so on the morning of an advance estimate the latest quarter is the one before.

**How close.** Reproduces the published series exactly (checked every night over the whole published history, 2015 on, to within 0.002 percentage point; the site rounds to four decimals).
