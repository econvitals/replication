# Real Oil and Mining Investment

**On econvitals.org:** [GDP components detail › Expenditure](https://econvitals.org/gdp/gdpdetail/), the chart of real investment in oil and mining equipment and structures (and, from the same arithmetic, real business investment excluding oil and mining). Method note: [Methods](https://econvitals.org/methods/#real-oil-mining-investment).

**What it is.** BEA publishes real investment in mining structures (exploration, shafts and wells) and, separately, in mining and oilfield machinery, but chained-dollar series cannot simply be added. Econvitals combines the two with a Törnqvist index: each quarter’s growth is a weighted average of the two components’ growth, the weights being their shares of nominal spending in that quarter and the one before. The result is anchored to 2017 dollars (its 2017 average equals 2017 nominal spending) and starts in 2007, when BEA’s machinery detail begins. The chart shows the 1-quarter change at an annual rate and the 4-quarter change.

The companion series strips that piece out of BEA’s published real nonresidential fixed investment: BFI’s real growth less the oil and mining contribution, divided by the rest’s share.

**Run it.** `python replicate.py` (needs free `FRED_API_KEY` and `BEA_API_KEY`). Writes `output/oil_mining.csv` and `output/bfi_ex_oil_mining.csv` (growth rates and the chained-2017-dollar level).

**Data.**
- Structures, mining exploration, shafts and wells: FRED `E318RC1Q027SBEA` (nominal) and `E318RX1Q020SBEA` (real).
- Equipment, mining and oilfield machinery: BEA’s NIPA underlying-detail tables 5.5.5U (`C270RC`, nominal) and 5.5.6U (`C270RX`, real), from the BEA API (not on FRED).
- Nonresidential fixed investment: FRED `PNFI` (nominal) and `PNFIC1` (real).

**How close.** Reproduces the published series exactly: checked every night over the whole history (2007 on) to within 0.002 percentage point. The largest difference, about 0.0003 point, comes from Econvitals rounding the level to four decimals before taking growth rates. As the Methods page says, this is a house aggregate with no official twin to check against.
