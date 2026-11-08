# Econvitals Employment Dispersion Index

**On econvitals.org:** [Labor › Employment](https://econvitals.org/labor/#employment), the chart of how spread out job growth is across industries. Method note: [Methods](https://econvitals.org/methods/#employment-dispersion).

**What it is.** How uneven job growth is across the economy. The script takes 12-month employment growth in each of about 89 detailed industries, weights each by its share of jobs, and measures how spread out the growth rates are — a weighted standard deviation, the “Lilien” measure from the economics of sectoral shifts. A high reading means some industries are booming while others shrink; a low one means growth is broad-based. For each month *t*:

> g<sub>i</sub> = ln E<sub>i</sub>(t) − ln E<sub>i</sub>(t − 12), w<sub>i</sub> = E<sub>i</sub>(t − 12) ÷ Σ E(t − 12), σ = 100 × √( Σ w<sub>i</sub> (g<sub>i</sub> − Σ w g)² )

in percentage points. The industries tile all nonfarm payroll jobs, not seasonally adjusted:

- every private 3-digit NAICS industry BLS publishes (73 today);
- for each of the 10 private supersectors, an “everything else” cell — the supersector total minus its published 3-digit industries — kept in any month where it is at least 0.05 thousand (BLS levels are in thousands to one decimal, so anything smaller is zero, not a tiny industry);
- six government cells: federal except the Postal Service, the Postal Service, and state and local government, each split into education and everything else.

The method is standard in the literature, but no agency publishes this series.

**Run it.** `python replicate.py`. No key needed. Writes `output/employment_dispersion.csv` (column `sigma`, monthly from January 1991).

**Data.** BLS Current Employment Statistics, from BLS’s public bulk download (`download.bls.gov/pub/time.series/ce/`, no key and no daily quota):

- `ce.industry`, BLS’s industry list, to find the 3-digit industries;
- the 16 supersector employment files `ce.data.10a.MiningAndLogging.Employment` through `ce.data.90a.Government.Employment` (about 77 MB together), from which the script keeps series `CEU<industry code>01` — all employees, thousands, not seasonally adjusted — from January 1990, when BLS’s 3-digit history becomes complete.

FRED carries most of these series but not eight of the newer NAICS 2022 retail and information industries, so the script reads BLS directly for all of them.

**How close.** Reproduces the published chart exactly: all 430 months within 0.0001 point (the largest difference is 0.00005, the site’s rounding to four decimals). The nightly check compares the whole history at that tolerance.

**One thing to know.** In construction, information, leisure and hospitality, and other services, the published 3-digit industries already add up to the supersector total, so their “everything else” remainder is only rounding in BLS’s published levels — 0.1 to 0.5 thousand jobs, in about half the months. Those crumbs pass the 0.05 threshold and enter as four tiny cells with erratic growth rates. Because their weights are tiny, they move the index by 0.002 point on average and by at most 0.03 point (in late 2013). The script keeps them, as the published series does.
