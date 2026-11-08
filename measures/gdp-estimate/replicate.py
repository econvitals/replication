"""Econvitals Current-Quarter GDP Estimate — the one piece of the estimate that is a single,
checkable number: the first-print adjustment. (The bridge-equation model itself is described in
the README; it is not rebuilt here.)

    python replicate.py      # needs FRED_API_KEY; writes output/first_print_gaps.csv

The model's bridges are fitted on BEA's revised history, so their sum estimates GDP growth as it
will read after revisions. BEA's advance estimate, the target, has on average come in below
today's revised figures; the estimate adds that average gap back. This rebuilds the gap: for every
quarter since 2011 at least four quarters before the one being estimated (so each has been through
an annual update), BEA's advance estimate (from the Atlanta Fed's GDPNow track record) minus
today's BEA figure for the same quarter, leaving out 2020 Q2 and Q3. It then sets the result
beside the adjustment in the estimate econvitals.org currently shows.
"""
import io
import json
import sys
from pathlib import Path

import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, get, save  # noqa: E402

GDPNOW = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/"
          "data/gdpnow/GDPTrackingModelDataAndForecasts.xlsx")
PAGE = "https://econvitals.org/tools/gdp-trackers/data.json"
LAG, SKIP = 4, {"2020Q2", "2020Q3"}

# BEA's advance estimates, unrounded, as the Atlanta Fed records them beside GDPNow's last reading.
book = openpyxl.load_workbook(io.BytesIO(get(GDPNOW, binary=True, timeout=180)), read_only=True,
                              data_only=True)
advance = {pd.Period(r[0], "Q"): float(r[2])
           for r in list(book["TrackRecord"].iter_rows(values_only=True))[1:]
           if r[0] is not None and isinstance(r[2], (int, float))}

# Today's vintage of real GDP growth (BEA table 1.1.1, percent change at an annual rate).
today = fred("A191RL1Q225SBEA")
today.index = today.index.to_period("Q")

gaps = pd.DataFrame({"advance": pd.Series(advance), "today": today}).dropna().sort_index()
gaps = gaps[~gaps.index.astype(str).isin(SKIP)]
gaps["gap"] = gaps["advance"] - gaps["today"]
save(gaps.set_axis(gaps.index.to_timestamp()).rename_axis("date"), HERE, "first_print_gaps")

page = json.loads(get(PAGE))
quarter = pd.Period(page["quarter"], "Q")
used = gaps.loc[: quarter - 1 - LAG, "gap"]
print(f"First-print gap for {page['quarter_label']}: {used.mean():+.4f} pp, the mean over "
      f"{len(used)} quarters ({used.index[0]} to {used.index[-1]}).")
house = page["house"]
print(f"econvitals.org shows: estimate {house['value']} = model sum {house['value_raw']} "
      f"+ first-print adjustment {house['first_print_offset']} (as of {house['as_of']}).")
