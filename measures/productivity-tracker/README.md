# Econvitals Productivity Tracker

**On econvitals.org:** the [GDP Trackers tool](https://econvitals.org/tools/gdp-trackers/), the Productivity section and its tiles. Method note: [Methods](https://econvitals.org/methods/#productivity-tracker).

**What it is.** What BLS will print for output per hour in the nonfarm business sector, built the way BLS builds it. Output is BEA’s nonfarm business value added: GDP less general government, nonprofits, households including owner-occupied housing, and farms. It is the number BLS uses, so once BEA has published a quarter nothing is estimated; before that it comes from the Econvitals Composite through a regression on its history. Hours rebuild BLS’s recipe from public monthly data (all private employees times production and nonsupervisory average weekly hours, less an approximate nonprofit share of education, health and other services, plus the self-employed at work from the household survey), through a regression on BLS’s first prints. The tracker starts with two months of a quarter’s jobs data. Once BLS has printed a quarter, the tracker follows BLS’s revised estimate: BEA’s output plus Econvitals’ tracked revision to it, over the hours BLS printed. It is an Econvitals estimate, not BLS’s.

**What this folder rebuilds.** `python replicate.py` (needs free `FRED_API_KEY` and `BEA_API_KEY`):

1. **Output is BEA’s nonfarm business value added.** It rebuilds the growth of BEA’s quantity index for nonfarm business (NIPA table 1.3.3, line “Nonfarm”) and sets it beside BLS’s output index. On today’s data they agree to 0.004 point at most over the last ten years, and exactly for recent quarters. Writes `output/output_check.csv`.
2. **The quarters BLS has printed**, as the tracker’s chart draws them: productivity growth at an annual rate and over four quarters, from BLS’s index. These agree with the chart’s rows to their two published decimals. Writes `output/printed.csv`.
3. **The tracked quarter, once BLS has printed it:** BEA’s output growth, plus 1.381 times Econvitals’ tracked revision to BEA’s GDP growth (BEA has revised nonfarm business by about 1.38 times its revisions to GDP), over the hours BLS printed. The tracked GDP revision is a recorded input, read from the tool’s published data. For the third quarter of 2026, as published on November 13: 3.666 + 1.381 × 0.1795 = 3.913 percent output growth over 0.110 percent hours growth gives 3.7997 percent (the page shows 3.8). Writes `output/tracker.csv`.

   Until November 16, 2026, Econvitals rounded the hours growth and the revision to two decimals inside its calculation, before dividing, so its record could differ from this rebuild by a few thousandths of a point: on November 8 its inputs gave 3.746 percent and the record read 3.74, and on November 13, 3.7997 against 3.80. This folder found it. Since then the calculation carries full precision and stores four decimals, and records dated before November 16 are rebuilt and printed but not compared.

Not rebuilt: the hours estimate used before BLS prints a quarter, which is a regression on BLS’s first prints from archived data vintages, and the output bridge from the composite used before BEA prints. Neither is long, but both are fitted on ALFRED vintages and their coefficients are refitted leaving out each quarter, which belongs in a research script rather than this one.

**Data.** BEA NIPA table 1.3.3 (`B358RA`) from the BEA API; FRED `OUTNFB` (BLS output, nonfarm business, PRS85006043), `OPHNFB` (output per hour, PRS85006093) and `HOANBS` (hours worked, PRS85006033); `econvitals.org/tools/gdp-trackers/data.json` for the tracked revision and the published figures.

**How close.** Compared every night with the tool’s published data (`check.json`), with one recorded input, the tracked GDP revision:

- The chart’s quarters as BLS printed them, at an annual rate and over four quarters: within 0.0051 point over the eleven quarters drawn, because the page stored them to two decimals until November 16, 2026.
- The tracked quarter, once BLS has printed it: within 0.0001 point. For most of each quarter no quarter on the page is at that stage, and the check then reports nothing to compare rather than a match.
