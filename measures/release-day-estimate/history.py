"""The track record of the release-day estimates: for each month, the Econvitals estimate the site
showed on release morning, the Fed bank's figure that replaced it, and the difference.

    python history.py --data-repo PATH

PATH is a git clone of Econvitals' public data repository (github.com/econvitals/econvitals-data).
Every chart's data file there is versioned, so its history shows exactly what the site showed
and when: on release morning the newest month carries the estimate, flagged `is_forecast`, and a
later version carries the bank's figure in its place. Reads the four charts' files and writes
history/release-day.csv at the top of this repository. No key needed.

A month is listed only once the bank's own figure has replaced the estimate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ET = ZoneInfo("America/New_York")
CHARTS = {"median-cpi": "Cleveland Fed", "trimmed-mean-cpi": "Cleveland Fed",
          "median-pce": "Cleveland Fed", "trimmed-mean-pce": "Dallas Fed"}


def versions(repo: Path, path: str):
    """(commit time, parsed JSON) for every version of one file, oldest first."""
    log = subprocess.run(["git", "-C", str(repo), "log", "--reverse", "--format=%H %cI", "--", path],
                         capture_output=True, text=True, check=True).stdout.split("\n")
    for line in filter(None, log):
        sha, when = line.split()
        try:
            body = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{path}"],
                                  capture_output=True, text=True, check=True).stdout
            yield dt.datetime.fromisoformat(when).astimezone(ET), json.loads(body)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-repo", required=True, help="a git clone of econvitals-data")
    ap.add_argument("--out-dir", default=str(ROOT / "history"))
    a = ap.parse_args()
    repo = Path(a.data_repo).expanduser()
    rows = []
    for chart, bank in CHARTS.items():
        shown: dict[str, dict] = {}
        for when, doc in versions(repo, f"data/{chart}.json"):
            for r in doc.get("data", []):
                month, v = str(r.get("date", ""))[:7], r.get("chg_1m_ann")
                if not month or v is None:
                    continue
                rec = shown.setdefault(month, {})
                if r.get("is_forecast"):
                    if "estimate" not in rec:
                        rec.update(estimate=float(v), estimate_shown_at=when)
                    rec["last_estimate"] = float(v)
                elif "estimate" in rec and "official" not in rec:
                    rec.update(official=float(v), official_shown_at=when)
        for month, rec in shown.items():
            if "estimate" not in rec or "official" not in rec:
                continue                  # no estimate was shown, or the bank has not posted
            rows.append({
                "record": f"{month} {chart}", "measure": chart, "target_month": month,
                "bank": bank,
                "estimate_1m_ann": rec["estimate"],
                "estimate_shown_at": rec["estimate_shown_at"].isoformat(timespec="minutes"),
                "last_estimate_1m_ann": rec["last_estimate"],
                "official_1m_ann": rec["official"],
                "official_shown_at": rec["official_shown_at"].isoformat(timespec="minutes"),
                "miss_1m_ann": round(rec["last_estimate"] - rec["official"], 4),
            })
    df = pd.DataFrame(rows, columns=["record", "measure", "target_month", "bank", "estimate_1m_ann",
                                     "estimate_shown_at", "last_estimate_1m_ann", "official_1m_ann",
                                     "official_shown_at", "miss_1m_ann"])
    df = df.sort_values(["target_month", "measure"]).reset_index(drop=True)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "release-day.tmp"
    df.to_csv(tmp, index=False)
    tmp.replace(out / "release-day.csv")
    print(f"release-day.csv: {len(df)} estimates, months {', '.join(sorted(set(df.target_month)))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
