"""The track record of the Econvitals PCE Tracking Estimate: every estimate recorded before BEA
published the month, beside BEA's first print and the miss.

    python history.py --state-dir PATH        # needs FRED_API_KEY (ALFRED)
    python history.py --state-dir PATH --backtest-file PATH/backtest_realtime.csv

PATH is the folder where the production tracker keeps its records (nowcast.json, one record per
month per stage, and scores.json, the first prints it scored them against). Writes
history/pce-tracking.csv at the top of this repository, and with --backtest-file also
history/pce-tracking-backtest.csv, the simulated real-time back-test.

What is included, and what never is:
  * Only records made with the CPI in hand (stage post-CPI or later). A record made on producer
    prices alone was never shown and is left out.
  * Only months BEA has published. The test is ALFRED, the archive of what was published when:
    a month ALFRED does not have is not out, and its record is withheld. If ALFRED cannot be
    reached, nothing is written.
  * Only records made before BEA's release (8:30 a.m. Eastern on the release date). A record
    made after the print is not a forecast.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.tracking import first_print, first_release_dates  # noqa: E402

ET = ZoneInfo("America/New_York")
CONCEPTS = ["overall", "core", "core_ex_housing", "core_ex_housing_used",
            "core_services_ex_housing", "market_based_core", "median", "trimmed_mean"]
# First prints read from ALFRED (series, and whether FRED carries an index or a rate already).
ALFRED = {"overall": ("PCEPI", "index"), "core": ("PCEPILFE", "index"),
          "trimmed_mean": ("PCETRIM1M158SFRBDAL", "annualized")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="the production record folder")
    ap.add_argument("--backtest-file", help="the real-time back-test CSV, to write the back-test file")
    ap.add_argument("--out-dir", default=str(ROOT / "history"))
    a = ap.parse_args()
    state = Path(a.state_dir).expanduser()
    records = json.loads((state / "nowcast.json").read_text())
    scores = {r["month"]: r for r in json.loads((state / "scores.json").read_text())} \
        if (state / "scores.json").exists() else {}

    released = first_release_dates("PCEPI")          # month -> date BEA first published it
    rows = []
    for month, stages in sorted(records.items()):
        p = pd.Period(month, "M")
        if p not in released:
            continue                                  # BEA has not published it: withhold
        release_at = dt.datetime.fromisoformat(released[p]).replace(hour=8, minute=30, tzinfo=ET)
        firsts = first_prints(p, released[p], scores.get(month, {}).get("first_print", {}))
        for stage, rec in sorted(stages.items(), key=lambda kv: kv[1]["run_at"]):
            if "cpi" not in rec.get("released", []):
                continue                              # producer prices alone: never shown
            made = dt.datetime.fromisoformat(rec["run_at"])
            if made >= release_at:
                continue                              # made after BEA published: not a forecast
            meas = rec.get("measures") or {}
            est = {c: meas.get(c) for c in CONCEPTS}
            est["overall"] = rec["headline_mom"] if est["overall"] is None else est["overall"]
            est["core"] = rec["core_mom"]
            offset = (rec.get("method") or {}).get("first_print_offset_bp", 0.0)
            row = {"record": f"{month} {stage}", "target_month": month, "stage": stage,
                   "sources_in": "+".join(s for s in ("cpi", "ppi", "import") if s in rec["released"]),
                   "estimated_at": made.astimezone(ET).isoformat(timespec="minutes"),
                   "bea_release_date": released[p],
                   "known_share_of_core": rec.get("known_share_core"),
                   "core_offset_bp": offset,
                   "core_before_offset": rec.get("core_mom_raw", rec["core_mom"])}
            for c in CONCEPTS:
                row[c] = est[c]
                row[f"{c}_first_print"] = firsts.get(c)
                row[f"{c}_miss"] = None if est[c] is None or firsts.get(c) is None \
                    else round(est[c] - firsts[c], 6)
            rows.append(row)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["record", "target_month", "stage", "sources_in", "estimated_at", "bea_release_date",
            "known_share_of_core", "core_offset_bp", "core_before_offset"] + \
        [f"{c}{s}" for c in CONCEPTS for s in ("", "_first_print", "_miss")]
    df = pd.DataFrame(rows, columns=cols)
    write(df, out_dir / "pce-tracking.csv")
    print(f"pce-tracking.csv: {len(df)} records, months {', '.join(sorted(set(df.target_month))) or 'none'}")
    if a.backtest_file:
        bt = backtest(Path(a.backtest_file).expanduser(), set(released))
        write(bt, out_dir / "pce-tracking-backtest.csv")
        print(f"pce-tracking-backtest.csv: {len(bt)} rows, {bt.target_month.min()} to {bt.target_month.max()}")
    return 0


def first_prints(month: pd.Period, released_on: str, recorded: dict) -> dict:
    """BEA's first print of each concept, % change on the month. Overall, core and the Dallas
    Fed's trimmed mean are read from ALFRED; the other concepts (BEA's market-based core, the core
    variants Econvitals sums from BEA's detail, and the Cleveland Fed's median) are the first
    prints the production tracker recorded on the day."""
    out = {c: (round(float(recorded[c]), 6) if recorded.get(c) is not None else None)
           for c in CONCEPTS}
    for c, (sid, kind) in ALFRED.items():
        dates = first_release_dates(sid) if c == "trimmed_mean" else {month: released_on}
        if month not in dates:
            continue
        v = first_print(sid, month, dates[month], kind)
        if pd.notna(v):
            out[c] = round(float(v), 6)
    return out


def backtest(path: Path, released: set) -> pd.DataFrame:
    """The production engine's real-time back-test, relabeled: each month re-run with only the
    BEA data that existed before that month's CPI release, scored against BEA's first print.
    Simulated, not live: the default fill (each unreleased component's 12-month mean), no
    first-print offset (this back-test is what measured it)."""
    d = pd.read_csv(path)
    d = d[d["fill"] == "mean12"].copy()
    d = d[d["month"].map(lambda m: pd.Period(m, "M") in released)]
    stage = d["stage"].replace({"final": "post_import"})
    out = pd.DataFrame({
        "record": d["month"] + " " + stage, "target_month": d["month"], "stage": stage,
        "simulated": "yes",
        "bea_data_as_of": d["vintage_pre"], "bea_first_print_vintage": d["vintage_fp"],
        "cpi_release_date": d["cpi_date"], "ppi_release_date": d["ppi_date"],
        "import_price_release_date": d["imp_date"],
        "known_share_of_core": d["known_share_core"].round(2),
        "overall": d["headline"].round(6), "overall_first_print": d["head_first"].round(6),
        "overall_miss": (d["headline"] - d["head_first"]).round(6),
        "core": d["core"].round(6), "core_first_print": d["core_first"].round(6),
        "core_miss": (d["core"] - d["core_first"]).round(6),
    })
    order = out["stage"].map({"post_cpi": 0, "post_ppi": 1, "post_import": 2})
    return out.assign(_o=order).sort_values(["target_month", "_o"]).drop(columns="_o").reset_index(drop=True)


def write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


if __name__ == "__main__":
    sys.exit(main())
