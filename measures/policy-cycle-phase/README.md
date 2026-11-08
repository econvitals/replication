# Policy-Cycle Phase

**On econvitals.org:** the Cycle Phase column of the [Global Central Bank Stance Matrix](https://econvitals.org/tools/central-bank-stance/), and the Phase column of the policy-rate table on [International › Global](https://econvitals.org/international/#global). Method note: [Methods](https://econvitals.org/methods/#policy-cycle-phase).

**What it is.** A simple Econvitals rule that says where each of twelve central banks is in its rate cycle:

- the **policy rate** is the Bank for International Settlements’ daily series, topped up from four central banks’ own same-day feeds (the Federal Reserve, the European Central Bank, the Bank of England and the Bank of Canada) when the BIS trails them. A feed is used only after it agrees with the BIS on the BIS’s own last date;
- the **last move** is the most recent day the rate changed, and its size;
- a hike or cut in the **last six months** makes a bank *Hiking* or *Cutting*; a last move **six to twelve months** old makes it *On Hold*; **older than a year**, *Paused* (a month is 30.44 days);
- the **year-to-date change** is today’s rate less the rate on January 1.

It is a heuristic, not a market-implied path, and the BIS series can trail a central bank by a week or more. The matrix’s “next expected move” (a hand-set desk view or a lean read off the phase) is not part of this rule and is not rebuilt here.

**Run it.** `python replicate.py` (needs a free `FRED_API_KEY` for the Fed’s target range; everything else is keyless). It writes:

- `output/stance.csv` — each bank today: rate, the date it is current through, last move, phase, year-to-date change, and whether the last reading came from the BIS or the bank’s own feed;
- `output/stance_check.csv` — the same rule run on the published matrix’s own cut-offs (each bank’s rate as of the date its published row is current through, the phase as of the day the matrix was built), so the nightly comparison is not thrown off by a decision that lands between the two runs;
- `output/site_stance.csv` — the published matrix laid out flat (phases as numbers: Hiking 1, Cutting 2, On Hold 3, Paused 4; dates as 8-digit numbers), for the comparisons the checker cannot read straight from the published file.

**Data.**

- BIS, “Central bank policy rates” (dataset `WS_CBPOL`, daily, end of period), [stats.bis.org](https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.US?format=csv), areas US, XM, JP, GB, CA, AU, CH, SE, NO, NZ, CN, IN. The U.S. number is the midpoint of the target range; the euro-area number is the ECB’s deposit facility rate.
- Federal Reserve: FRED `DFEDTARU` and `DFEDTARL` (the target range; their midpoint).
- ECB: the ECB Data Portal, series `FM.D.U2.EUR.4F.KR.DFR.LEV` (deposit facility rate).
- Bank of England: its statistical database, series `IUDBEDR` (Bank Rate).
- Bank of Canada: Valet series `V39079` (target for the overnight rate).

**How close.** Reproduces the published matrix exactly: the nightly check compares every bank’s rate (within 0.0001), year-to-date change, phase, last-move size and last-move date (all exactly).

**What is not rebuilt, and why.**

- When the BIS stops relaying the Reserve Bank of India, the matrix reads the RBI’s own web pages (its home page and its policy-statement listing, which publish no machine-readable series). This script does not; it uses the BIS series alone for India. A bank is therefore left out of the comparison when the published matrix shows a move dated after this script’s last observation, or when this script’s series ends more than 30 days before the published row.
- A phase the matrix’s editor has set by hand (allowed, dated, and dropped automatically once the bank decides again) is not the rule’s, so a bank with one is not compared on phase.
