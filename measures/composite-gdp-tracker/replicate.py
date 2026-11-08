"""Econvitals Composite GDP Tracker — rebuilds the composite for every day econvitals.org has
published one (econvitals.org/gdp/#gdp and /tools/gdp-trackers/), and the back-test of the two
Fed models shown beside its track record.

    python replicate.py     # no key needed; writes output/composite.csv and output/backtest.csv

The composite blends four trackers of the quarter in progress with weights fixed by how many days
remain until BEA's advance estimate. This script fetches the two public Fed models itself:
  GDPNow             the Atlanta Fed's workbook (TrackingHistory for the quarter in progress,
                     TrackingArchives for earlier quarters, TrackRecord for its record);
  NY Fed Nowcast     the New York Fed Staff Nowcast workbook ("Forecasts By Quarter").
The other two legs are RECORDED inputs, read from Econvitals' published daily history:
  Street median      the median of Wall Street tracking estimates, from bank research notes that
                     are not public; only the value the site published is used;
  Econvitals est.    the Current-Quarter GDP Estimate, as published each day (measures/
                     gdp-estimate explains why the model itself is not rebuilt here).
So are three facts about each day's snapshot: the days left to the advance estimate, which legs
were present, and the date of each Fed model's latest reading when the snapshot was taken.
"""
import io
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import get, published, save  # noqa: E402

GDPNOW = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/"
          "data/gdpnow/GDPTrackingModelDataAndForecasts.xlsx")
NYFED = ("https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/NowCast/Downloads/"
         "New-York-Fed-Staff-Nowcast_download_data.xlsx")

HOUSE_WEIGHT = 0.10        # the Econvitals estimate always takes 10%
PASS_THROUGH = 0.5         # a leg is nudged by half of the Econvitals estimate's move since its reading
BAND = [(61, 1.4), (31, 1.1), (15, 0.9), (8, 0.85), (0, 0.75)]  # GDPNow's average miss, 2014-26


def label(d) -> str:
    """A quarter-end date, or text like '2026q4' / '2026Q4', as 'Q4 2026'."""
    if isinstance(d, str):
        y, q = re.search(r"(\d{4})\s*[qQ]([1-4])", d).groups()
        return f"Q{q} {y}"
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def sheet(book: bytes, name: str) -> list:
    wb = openpyxl.load_workbook(io.BytesIO(book), read_only=True, data_only=True)
    return list(wb[name].iter_rows(values_only=True))


def day(d) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- the two Fed models
atl = get(GDPNOW, binary=True, timeout=180)
gdpnow = {}                                         # {quarter: {reading date: nowcast}}
arch = sheet(atl, "TrackingArchives")
col = arch[0].index("GDP Nowcast")
for r in arch[1:]:
    if r[0] is not None and isinstance(r[col], (int, float)):
        gdpnow.setdefault(label(r[1]), {})[day(r[0])] = float(r[col])
hist = sheet(atl, "TrackingHistory")                # the quarter in progress, dates across
current = label(next(str(r[0]) for r in hist if r[0] and "Evolution of GDP" in str(r[0])))
gdp_row = next(r for r in hist if r[1] == "GDP Nowcast")
for d, v in zip(hist[0][2:], gdp_row[2:]):
    if d is not None and isinstance(v, (int, float)):
        gdpnow.setdefault(current, {})[day(d)] = float(v)

nyfed = {}                                          # {quarter: {forecast date: nowcast}}
by_q = sheet(get(NYFED, binary=True), "Forecasts By Quarter")
head = next(i for i, r in enumerate(by_q) if r[0] == "Forecast Date")
for r in by_q[head + 1:]:
    if r[0] is None:
        continue
    for q, v in zip(by_q[head][1:], r[1:]):
        if q and isinstance(v, (int, float)):
            nyfed.setdefault(label(q), {})[day(r[0])] = float(v)


# ---------------------------------------------------------------- the weighting rule
def weights(days, present: list) -> dict:
    """Fixed by horizon: Econvitals 10%; of the rest, equal more than 45 days out (or with no
    scheduled date), GDPNow 0.5 from 15 to 45 days and 0.6 inside 15, the others sharing the rest."""
    rest = [k for k in present if k != "house"]
    others = [k for k in rest if k != "gdpnow"]
    if len(rest) == 1:
        w = {rest[0]: 1.0}
    elif days is None or days > 45 or "gdpnow" not in rest or not others:
        w = {k: 1 / len(rest) for k in rest}
    else:
        share = 0.5 if days >= 15 else 0.6
        w = {"gdpnow": share, **{k: (1 - share) / len(others) for k in others}}
    if "house" in present:
        w = {k: v * (1 - HOUSE_WEIGHT) for k, v in w.items()} | {"house": HOUSE_WEIGHT}
    return w


def band(days) -> float:
    """No scheduled date yet counts as the farthest horizon."""
    return BAND[0][1] if days is None else next(b for floor, b in BAND if days >= floor)


# ---------------------------------------------------------------- every published day
snaps = published("data/gdp-nowcast-history.json")["snapshots"]
rows = []
for s in snaps:
    q, legs, days = s["quarter"], s["legs"], s.get("days_to_release")
    # The Econvitals estimate as it stood at the end of each earlier day of this quarter.
    path = {x["date"]: x["legs"]["house"]["value"] for x in snaps
            if x["quarter"] == q and "house" in x["legs"]}
    house_now = legs.get("house", {}).get("value")

    def nudge(as_of: str) -> float:
        then = [v for d, v in sorted(path.items()) if d <= as_of]
        return PASS_THROUGH * (house_now - then[-1]) if house_now is not None and then else 0.0

    row = {"key": f"{s['date']} {q}", "date": s["date"], "quarter": q, "days_to_release": days}
    value = {}
    for leg, readings in (("gdpnow", gdpnow), ("nyfed", nyfed)):
        if leg in legs:
            as_of = legs[leg]["as_of"]
            raw = readings.get(q, {}).get(as_of)
            row[f"{leg}_as_of"], row[f"{leg}_raw"] = as_of, raw
            value[leg] = raw + nudge(as_of) if raw is not None else float("nan")
        # A reading the Fed had published by that day that the snapshot did not use.
        newer = [d for d in readings.get(q, {}) if d <= s["date"]]
        row[f"{leg}_latest_published"] = max(newer) if newer else None
    for leg in ("street", "house"):                  # recorded legs
        if leg in legs:
            value[leg] = legs[leg]["value"]
    w = weights(days, list(value))
    for leg in ("gdpnow", "nyfed", "street", "house"):
        row[leg] = value.get(leg)
        row[f"w_{leg}"] = w.get(leg)
    row["composite"] = sum(w[k] * value[k] for k in w)
    row["band"] = band(days)
    rows.append(row)
composite = pd.DataFrame(rows).set_index("key")
save(composite, HERE, "composite")


# ---------------------------------------------------------------- the back-test
# GDPNow and the NY Fed on the NY Fed's last Friday before each advance estimate, 2023 on, and
# their plain average, against the advance estimate. The published back-test takes the advance
# estimates and their dates from Atlanta's TrackRecord sheet, so this does too; where that sheet's
# date disagrees with BEA's actual release date (which the TrackingArchives sheet carries), the
# row says so and gives the average on the right date as well.
release_on = {}
pcol = arch[0].index("Publication Date of Advance Estimate")
for r in arch[1:]:
    if r[1] is not None and r[pcol] is not None:
        release_on[label(r[1])] = day(r[pcol])


def last_friday_readings(q: str, release: str):
    """(NY Fed's last forecast date before `release`, GDPNow then, NY Fed then) or None."""
    ny = {d: v for d, v in nyfed.get(q, {}).items() if d < release}
    g = [v for d, v in sorted(gdpnow.get(q, {}).items()) if ny and d <= max(ny)]
    return (max(ny), g[-1], ny[max(ny)]) if g else None


bt = []
for r in sheet(atl, "TrackRecord")[1:]:
    if r[0] is None or not isinstance(r[2], (int, float)) or r[0].year < 2023:
        continue
    q, advance, release = label(r[0]), float(r[2]), day(r[3])
    got = last_friday_readings(q, release)
    if not got:
        continue
    as_of, g, n = got
    row = {"quarter": q, "advance": advance, "release_date_used": release, "as_of": as_of,
           "gdpnow": g, "nyfed": n, "average": (g + n) / 2, "average_miss": (g + n) / 2 - advance}
    true = release_on.get(q)
    if true and true != release and last_friday_readings(q, true):
        t_as_of, t_g, t_n = last_friday_readings(q, true)
        row.update(note=f"TrackRecord dates the advance estimate {release}; BEA released it {true}",
                   as_of_on_release_date=t_as_of, average_on_release_date=(t_g + t_n) / 2)
        print(f"note: {q}: {row['note']}; on the right date the average is "
              f"{row['average_on_release_date']:.2f}, not {row['average']:.2f}.")
    bt.append(row)
backtest = pd.DataFrame(bt).iloc[::-1].set_index("quarter")
save(backtest, HERE, "backtest")

print(composite[["composite", "gdpnow", "nyfed", "street", "house", "band"]].tail(6).round(2)
      .to_string())
print("\nBack-test, mean absolute miss of the plain average:",
      round(backtest["average_miss"].abs().mean(), 2), f"over {len(backtest)} quarters")
