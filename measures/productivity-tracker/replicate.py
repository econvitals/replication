"""Econvitals Productivity Tracker — rebuilds the parts of the tracker on
econvitals.org/tools/gdp-trackers/ (the Productivity section) that are arithmetic on public data.

    python replicate.py      # needs FRED_API_KEY and BEA_API_KEY; writes output/output_check.csv,
                             # output/printed.csv and output/tracker.csv

1. Output. BLS's output for the nonfarm business sector is BEA's real value added of nonfarm
   business (NIPA table 1.3.3, line "Nonfarm"). This rebuilds its growth from BEA and sets it
   beside BLS's own output index.
2. The quarters BLS has printed. The tracker's chart draws them as BLS printed them: productivity
   growth at an annual rate and over four quarters, from BLS's index.
3. The quarter being tracked, once BLS has printed it: BEA's output growth, plus 1.381 times
   Econvitals' tracked revision to BEA's GDP growth (BEA has revised nonfarm business by that
   multiple of its GDP revisions), over the hours BLS printed. The tracked revision is a RECORDED
   input, read from the tracker's published data. Before BLS prints a quarter, the tracker's hours
   come from a regression of BLS's first prints on payroll-survey and household-survey data,
   which this script does not rebuild (see the README).

The nightly check compares 2 with the page's chart and 3 with the page's tracked value. Records
dated before FULL_PRECISION_FROM are rebuilt and printed but not compared: until then Econvitals
rounded hours and the revision to two decimals inside its calculation (see the README).
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_wide, fred, get, save  # noqa: E402

OUTPUT_ON_GDP_REVISION = 1.381     # Econvitals' fitted multiple: nonfarm business revision / GDP's
PAGE = "https://econvitals.org/tools/gdp-trackers/data.json"
FULL_PRECISION_FROM = "2026-11-16"  # the first record worked at full precision and stored to 4 decimals


def annualized(level: pd.Series) -> pd.Series:
    return 100 * ((level / level.shift(1)) ** 4 - 1)


def as_quarters(s: pd.Series) -> pd.Series:
    return pd.Series(s.values, index=s.index.to_period("Q"))


# 1. Output: BEA's nonfarm business quantity index against BLS's output index.
bea_nfb = as_quarters(bea_wide("T10303", "Q", year="ALL", by="code")["B358RA"])
bls_output = as_quarters(fred("OUTNFB"))                 # BLS PRS85006043, 2017 = 100
check = pd.DataFrame({"bea_nonfarm_business": annualized(bea_nfb),
                      "bls_output": annualized(bls_output)}).dropna()
check["difference"] = check["bea_nonfarm_business"] - check["bls_output"]
save(check.set_axis(check.index.to_timestamp()).rename_axis("date"), HERE, "output_check")

# 2. Productivity as BLS printed it (BLS PRS85006093, output per hour, 2017 = 100).
index = as_quarters(fred("OPHNFB"))
printed = pd.DataFrame({"printed": annualized(index), "four_quarter": 100 * (index / index.shift(4) - 1)})
save(printed.set_axis(printed.index.to_timestamp()).rename_axis("date").dropna(), HERE, "printed")

# 3. The tracked quarter, if BLS has printed it.
hours = as_quarters(fred("HOANBS"))                      # BLS PRS85006033, hours worked, 2017 = 100
page = json.loads(get(PAGE))["productivity"]
rows = []
for rec in page["quarters"]:
    q = pd.Period(rec["quarter"], "Q")
    row = {"quarter": rec["quarter"], "label": rec["quarter_label"], "as_of": rec["as_of"],
           "stage": rec["stage"], "published": rec["value"]}
    if rec["stage"] == "bls_printed" and q in hours.index and q in bea_nfb.index:
        tracked = (rec.get("gdp_revision_tracked") or {}).get("change_in_gdp", 0.0)
        out_g = annualized(bea_nfb)[q] + OUTPUT_ON_GDP_REVISION * tracked
        hours_g = annualized(hours)[q]
        rebuilt = 100 * ((1 + out_g / 100) / (1 + hours_g / 100) - 1)
        row.update(bea_output=annualized(bea_nfb)[q], tracked_gdp_revision=tracked,
                   output=out_g, bls_hours=hours_g, rebuilt=rebuilt,
                   compared=rebuilt if rec["as_of"] >= FULL_PRECISION_FROM else None)
    rows.append(row)
# Written every run with every column (empty when nothing is standing), so the nightly check reads
# "nothing to compare today" rather than a stale or missing file.
COLUMNS = ["quarter", "label", "as_of", "stage", "published", "bea_output", "tracked_gdp_revision",
           "output", "bls_hours", "rebuilt", "compared"]
tracker = pd.DataFrame(rows, columns=COLUMNS)
save(tracker.set_index("quarter"), HERE, "tracker")

print("Output growth, BEA nonfarm business vs BLS (percent, annual rate):")
print(check.tail(4).round(3).to_string())
print(f"Largest gap over the last 40 quarters: {check['difference'].tail(40).abs().max():.4f} pt\n")
print("Productivity as BLS printed it:")
print(printed.tail(4).round(2).to_string(), "\n")
print("The tracked quarter on the page:")
print(tracker.round(4).to_string(index=False) if len(tracker) else "(none standing)")
if len(tracker) and tracker["rebuilt"].isna().all():
    print("This stage takes its hours from the payroll/household-survey regression (not rebuilt).")
elif len(tracker) and tracker["compared"].isna().any():
    print(f"A record dated before {FULL_PRECISION_FROM} rounded inside its calculation: printed, not compared.")
