"""Run every replication script and compare what it produces with what econvitals.org shows.

    python tools/check_all.py                 # everything
    python tools/check_all.py --only real-wage-growth
    python tools/check_all.py --list          # what would run, and how each is judged

Each folder's `check.json` says which output column must match which published series, over how
many recent dates, and within what tolerance. A folder whose `status` is "documented" has no
runnable comparison (for example, it needs microdata the reader must request themselves); it is
reported as NOT COMPARED, never as a pass. A `published` path that starts with "repo:" names a
CSV in this repository (a track record under history/) instead of a file on econvitals.org.

Exit code: 0 when every compared series matches; 1 when any series does not match, or a script
has failed on two runs in a row (one failure is retried and remembered, since publishers' servers
do go down for an hour).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import econdata  # noqa: E402

DEFAULT_STATE = Path.home() / ".cache" / "econvitals-replication" / "check-state.json"


def folders() -> list[Path]:
    found = sorted(p.parent for p in ROOT.glob("measures/*/check.json"))
    found += sorted(p.parent for p in ROOT.glob("simulator/check.json"))
    return found


def run_script(folder: Path, timeout: int) -> tuple[bool, str]:
    script = folder / "replicate.py"
    if not script.exists():
        return False, "no replicate.py"
    try:
        p = subprocess.run([sys.executable, str(script)], cwd=folder, capture_output=True,
                           text=True, timeout=timeout, env=os.environ.copy())
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    if p.returncode != 0:
        tail = (p.stderr or p.stdout).strip().splitlines()[-6:]
        return False, "exit %d: %s" % (p.returncode, " | ".join(tail))
    return True, ""


def _norm(v) -> str:
    """Index values compared as text; anything that parses as a date becomes YYYY-MM-DD."""
    s = str(v).strip()
    try:
        if len(s) >= 7 and s[:4].isdigit() and s[4] in "-/":
            return pd.Timestamp(s).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return s


def _dig(obj, dotted: str | None):
    for part in (dotted or "").split("."):
        if part:
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def published_series(spec: dict) -> pd.Series:
    if spec["published"].startswith("repo:"):
        # A CSV kept in this repository, e.g. "repo:history/pce-tracking.csv" (a track record).
        df = pd.read_csv(ROOT / spec["published"][5:], dtype=str)
        index = spec.get("published_index") or df.columns[0]
        s = pd.Series(pd.to_numeric(df[spec["published_column"]], errors="coerce").values,
                      index=df[index].map(_norm))
        return s.dropna()
    d = econdata.published(spec["published"])
    rows = _dig(d, spec.get("published_rows") or "data")
    index = spec.get("published_index") or (d.get("date_col") if isinstance(d, dict) else None) or "date"
    col = spec["published_column"]
    out = {}
    for r in rows:
        if index in r and col in r and r[col] is not None:
            try:
                out[_norm(r[index])] = float(r[col])
            except (TypeError, ValueError):
                continue
    return pd.Series(out, dtype=float)


def output_series(folder: Path, spec: dict) -> pd.Series:
    df = pd.read_csv(folder / spec["output"], dtype=str)
    index = spec.get("output_index") or df.columns[0]
    col = spec["output_column"]
    s = pd.Series(pd.to_numeric(df[col], errors="coerce").values, index=df[index].map(_norm))
    return s.dropna()


def compare(folder: Path, spec: dict) -> dict:
    ours, theirs = output_series(folder, spec), published_series(spec)
    common = [k for k in theirs.index if k in ours.index]
    common.sort()
    n = int(spec.get("last_n", 24))
    tol = float(spec.get("tolerance", 0.01))
    label = f"{spec['output_column']} vs {spec['published']}:{spec['published_column']}"
    if not common:
        return {"series": label, "ok": False, "why": "no dates in common",
                "ours_latest": max(ours.index) if len(ours) else None,
                "published_latest": max(theirs.index) if len(theirs) else None}
    window = common[-n:]
    diff = (ours[window] - theirs[window]).abs()
    worst = diff.idxmax()
    ok = bool(diff.max() <= tol + 1e-12)
    return {"series": label, "ok": ok, "compared": len(window), "tolerance": tol,
            "max_abs_diff": round(float(diff.max()), 6), "worst_at": worst,
            "ours_latest": max(ours.index), "published_latest": max(theirs.index)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", help="folder names to run")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keys-file", help="KEY=value file to take the four API keys from")
    ap.add_argument("--published-dir", help="a local copy of econvitals-data to compare against")
    ap.add_argument("--report", help="write the full result as JSON here")
    ap.add_argument("--state", default=str(DEFAULT_STATE),
                    help="remembers failures between runs (one failure is not an alarm)")
    ap.add_argument("--marker", help="touch this file when the run finishes")
    args = ap.parse_args()

    if args.keys_file:
        os.environ["ECONVITALS_KEYS_FILE"] = os.path.expanduser(args.keys_file)
    if args.published_dir:
        os.environ["ECONVITALS_PUBLISHED_DIR"] = os.path.expanduser(args.published_dir)
    econdata._load_keys_file()

    todo = [f for f in folders() if not args.only or f.name in args.only]
    if args.list:
        for f in todo:
            c = json.loads((f / "check.json").read_text())
            print(f"{f.name:42} {c.get('status', '?'):22} {len(c.get('compare', []))} series")
        return 0

    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    results, alarm = [], False
    for f in todo:
        c = json.loads((f / "check.json").read_text())
        rec = {"folder": f.name, "status": c.get("status")}
        if c.get("status") == "documented" or not c.get("compare"):
            rec["result"] = "NOT COMPARED"
            rec["why"] = c.get("why_not_compared", "no runnable comparison")
            results.append(rec)
            print(f"  --   {f.name}: not compared ({rec['why']})")
            continue
        t0 = time.time()
        ok, err = run_script(f, int(c.get("timeout_seconds", 900)))
        if not ok:
            time.sleep(20)
            ok, err = run_script(f, int(c.get("timeout_seconds", 900)))
        rec["seconds"] = round(time.time() - t0, 1)
        if not ok:
            fails = state.get(f.name, 0) + 1
            state[f.name] = fails
            rec.update(result="SCRIPT FAILED", why=err, failures_in_a_row=fails)
            alarm = alarm or fails >= 2
            results.append(rec)
            print(f"  !!   {f.name}: script failed ({fails} in a row): {err}")
            continue
        state[f.name] = 0
        try:
            rec["series"] = [compare(f, s) for s in c["compare"]]
        except Exception as exc:  # a missing column or file is a mismatch, not a crash
            rec["series"] = [{"ok": False, "why": f"{type(exc).__name__}: {exc}"}]
        good = all(s["ok"] for s in rec["series"])
        rec["result"] = "MATCHES" if good else "DOES NOT MATCH"
        alarm = alarm or not good
        results.append(rec)
        mark = "ok" if good else "XX"
        print(f"  {mark}   {f.name}: {rec['result']}")
        for s in rec["series"]:
            if not s["ok"] or len(rec["series"]) == 1:
                detail = s.get("why") or (f"max diff {s['max_abs_diff']} over {s['compared']} "
                                          f"dates (tolerance {s['tolerance']})")
                print(f"         {s.get('series', '')}: {detail}")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True))
    counts = {}
    for r in results:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    summary = {"ran_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "counts": counts, "alarm": alarm, "results": results}
    print("\n" + ", ".join(f"{v} {k.lower()}" for k, v in sorted(counts.items())))
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=1, default=str))
    if args.marker:
        Path(args.marker).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.marker).expanduser().touch()
    return 1 if alarm else 0


if __name__ == "__main__":
    sys.exit(main())
