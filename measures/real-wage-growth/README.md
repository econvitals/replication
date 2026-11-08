# Real Wage Growth

**On econvitals.org:** [Labor › Wages](https://econvitals.org/labor/#wages), the two real-wage charts. Method note: [Methods](https://econvitals.org/methods/#real-wage-growth).

**What it is.** Two published wage measures adjusted for inflation by the consumer price index (CPI-U, all items, seasonally adjusted).

- **Real average hourly earnings** divides BLS’s average hourly earnings of all private employees by the CPI each month and shows the 1-month and 3-month changes at an annual rate. Econvitals builds it because BLS’s own real series is rounded to the cent, which adds about a point of noise to a monthly annualized change.
- **The real Atlanta Fed Wage Growth Tracker** puts the CPI on the tracker’s own basis (the 12-month change, averaged over 3 months) and deflates by it: (1 + wage growth) / (1 + inflation) − 1.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY`). Writes `output/real_ahe.csv` and `output/real_atlanta.csv`.

**Data.** FRED series `CES0500000003` (BLS average hourly earnings, total private), `CPIAUCSL` (BLS CPI-U, seasonally adjusted) and `FRBATLWGT3MMAUMHWGO` (Atlanta Fed Wage Growth Tracker, overall, 3-month average).

**How close.** Reproduces the published series exactly (checked every night to within 0.002 percentage point; the site rounds to four decimals). October 2025 has no CPI because of the shutdown, so any change that needs it is blank.
