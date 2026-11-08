"""The track record of the Econvitals Composite GDP Tracker, as downloadable tables.

    python history.py      # no key needed; writes three CSVs to history/ at the top of this repo

Reads the two files econvitals.org publishes (data/gdp-nowcast-history.json and
data/gdp-nowcast-backtest.json) and lays them out one row per observation:

  history/gdp-tracking.csv           one row per day per quarter: the composite, its band, the days
                                     left to BEA's advance estimate, and each leg's value, the date of
                                     its latest reading and its weight. Recorded live since the
                                     composite began on October 19, 2026.
  history/gdp-tracking-scored.csv    one row per quarter once BEA's advance estimate is out: the
                                     composite and every leg on the last day before the release,
                                     against the advance estimate.
  history/gdp-tracking-backtest.csv  a BACK-TEST, not a live record: GDPNow, the New York Fed Staff
                                     Nowcast and their plain average on the New York Fed's last
                                     Friday before each advance estimate since 2023, from the two
                                     Feds' own archives.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from common.econdata import published  # noqa: E402

LEGS = ["gdpnow", "nyfed", "street", "house"]   # Atlanta Fed, New York Fed, Street median, Econvitals
OUT = ROOT / "history"


def tracking(history: dict) -> pd.DataFrame:
    rows = []
    for s in history["snapshots"]:
        row = {"date": s["date"], "quarter": s["quarter"], "composite": s["composite"],
               "composite_shown": s.get("shown"), "band": s["band"],
               "days_to_release": s.get("days_to_release")}
        for leg in LEGS:
            got = s["legs"].get(leg, {})
            row[f"{leg}_value"] = got.get("value")
            row[f"{leg}_as_of"] = got.get("as_of")
            row[f"{leg}_weight"] = got.get("weight")
        row["street_firms"] = s["legs"].get("street", {}).get("n")
        row["key"] = f"{s['date']} {s['quarter']}"          # unique: one day can carry two quarters
        rows.append(row)
    df = pd.DataFrame(rows)
    df["days_to_release"] = df["days_to_release"].astype("Int64")
    df["street_firms"] = df["street_firms"].astype("Int64")
    return df


def scored(history: dict) -> pd.DataFrame:
    rows = []
    for r in history["scored"]:
        row = {"quarter": r["quarter"], "advance_estimate": r["advance"],
               "release_date": r["release_date"], "scored_from": r["scored_from"],
               "composite": r["composite"], "composite_miss": r["composite_error"]}
        for leg in LEGS:
            got = r["legs"].get(leg, {})
            row[f"{leg}_value"] = got.get("value")
            row[f"{leg}_miss"] = got.get("error")
        rows.append(row)
    return pd.DataFrame(rows)


def backtest(bt: dict) -> pd.DataFrame:
    rows = [{"quarter": r["quarter"], "basis": "back-test from Fed archives (not live)",
             "advance_estimate": r["advance"], "reading_date": r["as_of"],
             "gdpnow": r["gdpnow"], "nyfed": r["nyfed"], "average_of_two": r["average"],
             "gdpnow_miss": r["errors"]["gdpnow"], "nyfed_miss": r["errors"]["nyfed"],
             "average_miss": r["errors"]["average"]} for r in bt["rows"]]
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    history = published("data/gdp-nowcast-history.json")
    tables = {"gdp-tracking": tracking(history), "gdp-tracking-scored": scored(history),
              "gdp-tracking-backtest": backtest(published("data/gdp-nowcast-backtest.json"))}
    for name, df in tables.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"history/{name}.csv: {len(df)} rows")
    t = tables["gdp-tracking"]
    print(f"Live record {t['date'].min()} to {t['date'].max()}, "
          f"quarters {', '.join(dict.fromkeys(t['quarter']))}.")


if __name__ == "__main__":
    main()
