"""The track record of the Econvitals CPI Tracking Estimate: every estimate recorded before BLS
published the month, beside BLS's (and the Cleveland Fed's) first print and the miss.

    python history.py --state-dir PATH        # needs FRED_API_KEY (ALFRED)

PATH is the folder where the production tracker keeps its records: cpi_nowcast.json (one record
per month per day it ran) and, once months have been scored, cpi_scores.json. Writes
history/cpi-tracking.csv at the top of this repository.

The estimate is never shown before BLS publishes, so this file is strict about it:
  * A month appears only once BLS has published it. The test is ALFRED, the archive of what was
    published when: a month ALFRED does not have is not out, and every record of it is withheld.
    If ALFRED cannot be reached, nothing is written.
  * Only records made before the release (8:30 a.m. Eastern on the release date) are included.
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
CUTS = ["headline", "core", "food", "energy", "core_goods", "core_services", "shelter",
        "core_services_ex_shelter", "core_ex_shelter", "core_ex_shelter_used", "median", "trimmed"]
# First prints read from ALFRED: (series, how FRED carries it). The rest come from the record.
ALFRED = {"headline": ("CPIAUCSL", "index"), "core": ("CPILFESL", "index"),
          "food": ("CPIUFDSL", "index"), "energy": ("CPIENGSL", "index"),
          "core_goods": ("CUSR0000SACL1E", "index"), "core_services": ("CUSR0000SASLE", "index"),
          "shelter": ("CUSR0000SAH1", "index"),
          "median": ("MEDCPIM157SFRBCLE", "rate"), "trimmed": ("TRMMEANCPIM157SFRBCLE", "rate")}
# BLS's 12-month change is on the unadjusted index.
ALFRED_12M = {"headline": "CPIAUCNS", "core": "CPILFENS"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="the production record folder")
    ap.add_argument("--out-dir", default=str(ROOT / "history"))
    a = ap.parse_args()
    state = Path(a.state_dir).expanduser()
    records = json.loads((state / "cpi_nowcast.json").read_text())
    scores = json.loads((state / "cpi_scores.json").read_text()) \
        if (state / "cpi_scores.json").exists() else {}

    released = first_release_dates("CPIAUCSL")        # month -> date BLS first published it
    rows = []
    for month, runs in sorted(records.items()):
        p = pd.Period(month, "M")
        if p not in released:
            continue                                   # not published yet: withhold every record
        release_at = dt.datetime.fromisoformat(released[p]).replace(hour=8, minute=30, tzinfo=ET)
        before = [r for r in runs.values() if dt.datetime.fromisoformat(r["run_at"]) < release_at]
        if not before:
            continue
        before.sort(key=lambda r: r["run_at"])
        recorded = {c: v.get("actual") for c, v in (scores.get(month, {}).get("cuts") or {}).items()}
        firsts = first_prints(p, recorded)
        for rec in before:
            made = dt.datetime.fromisoformat(rec["run_at"]).astimezone(ET)
            row = {"record": f"{month} {made.date()}", "target_month": month,
                   "estimated_at": made.isoformat(timespec="minutes"),
                   "bls_release_date": released[p],
                   "last_before_release": "yes" if rec is before[-1] else "no",
                   "midpoint_12m_base": "yes" if rec.get("midpoint_base") else "no"}
            for c in CUTS:
                est = (rec.get("cuts") or {}).get(c) or {}
                row[c] = est.get("mom")
                row[f"{c}_first_print"] = firsts.get(c)
                row[f"{c}_miss"] = None if est.get("mom") is None or firsts.get(c) is None \
                    else round(est["mom"] - firsts[c], 6)
                row[f"{c}_12m"] = est.get("yoy")
            for c in ALFRED_12M:
                row[f"{c}_12m_first_print"] = firsts.get(f"{c}_12m")
                row[f"{c}_12m_miss"] = None if row[f"{c}_12m"] is None or firsts.get(f"{c}_12m") is None \
                    else round(row[f"{c}_12m"] - firsts[f"{c}_12m"], 6)
            rows.append(row)
    cols = ["record", "target_month", "estimated_at", "bls_release_date", "last_before_release",
            "midpoint_12m_base"] + [f"{c}{s}" for c in CUTS for s in ("", "_first_print", "_miss")] + \
        [f"{c}_12m" for c in CUTS] + [f"{c}_12m{s}" for c in ALFRED_12M for s in ("_first_print", "_miss")]
    df = pd.DataFrame(rows, columns=cols)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "cpi-tracking.tmp"
    df.to_csv(tmp, index=False)
    tmp.replace(out_dir / "cpi-tracking.csv")
    print(f"cpi-tracking.csv: {len(df)} records, months {', '.join(sorted(set(df.target_month))) or 'none yet'}")
    return 0


def first_prints(month: pd.Period, recorded: dict) -> dict:
    """First prints, % change on the month (and over 12 months for all items and core). From
    ALFRED where FRED carries the series; core services ex shelter, core ex shelter and core ex
    shelter and used cars are the values the production tracker recorded on release day."""
    out = {c: (round(float(v), 6) if v is not None else None) for c, v in recorded.items()
           if c in ("core_services_ex_shelter", "core_ex_shelter", "core_ex_shelter_used")}
    for c, (sid, kind) in ALFRED.items():
        dates = first_release_dates(sid)
        if month in dates:
            v = first_print(sid, month, dates[month], kind)
            out[c] = round(float(v), 6) if pd.notna(v) else None
    for c, sid in ALFRED_12M.items():
        dates = first_release_dates(sid)
        if month in dates:
            v = first_print(sid, month, dates[month], "index", lag=12)
            out[f"{c}_12m"] = round(float(v), 6) if pd.notna(v) else None
    return out


if __name__ == "__main__":
    sys.exit(main())
