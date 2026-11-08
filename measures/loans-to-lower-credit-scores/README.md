# Loans to Lower Credit Scores

**On econvitals.org:** [Household finance detail › Housing](https://econvitals.org/other/householdfinancedetail/#housing), the chart “Share of New Loans Going to Borrowers With Credit Scores Below 660.” Method note: [Methods](https://econvitals.org/methods/#loans-to-lower-credit-scores).

**What it is.** The share of new mortgage and auto loan money going to borrowers with credit scores below 660. The New York Fed’s Household Debt and Credit Report publishes origination volumes by credit-score band; Econvitals adds its two bands below 660 (under 620, and 620 to 659) and divides by total originations, separately for mortgages and auto loans.

The New York Fed changed its credit-score model in the first quarter of 2026, which can shift the bands; total originations are unaffected.

**Run it.** `python replicate.py` (no key needed). Writes `output/loans_under_660.csv`.

**Data.** The workbook behind the New York Fed’s [Quarterly Report on Household Debt and Credit](https://www.newyorkfed.org/microeconomics/hhdc), one file per quarter at `https://www.newyorkfed.org/medialibrary/interactives/householdcredit/data/xls/HHD_C_Report_<YYYY>Q<N>.xlsx`. The script takes the newest one published (it tries the current quarter and steps back; an unpublished quarter answers with a web page, not a spreadsheet). Two sheets, both billions of dollars:

- “Page 6 Data” — mortgage origination volume by credit score (from 2003 Q1);
- “Page 8 Data” — auto loan origination volume by credit score (from 2004 Q1).

From each it takes the columns “<620”, “620-659” and “TOTAL”. The source is the New York Fed Consumer Credit Panel/Equifax.

**How close.** Reproduces the published series exactly: checked every night over the last 60 quarters to within 0.001 percentage point (the site rounds to three decimals). For a few days after the New York Fed publishes a new quarter the script may be one quarter ahead of the site; the check compares only the quarters both have.
