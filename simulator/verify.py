#!/usr/bin/env python3
"""verify.py: rebuild the sample of the Macroeconomic Simulator's stored runs in expected/ with the engine and the
Federal Reserve Board's FRB/US model, and compare them with the page's own numbers.

    python verify.py                     # every run in expected/ (see README)
    python verify.py --shocks tariff,invest --exp var --elb no --fiscal fixed     # a subset of files
    python verify.py --compare data      # no model runs: compare a library rebuilt by engine/build.py with expected/

What it checks, in order:
  1. the two stock-price calibrations (rerun here) against expected/meta.json;
  2. the parts of expected/meta.json the engine writes from its own definitions and the Board's data: the baseline
     values, the menus (shocks, sizes, durations, Fed responses), the variables and the Board's package vintage;
  3. the runs: expected/runs/ holds every stored file (one shock x expectations x lower bound x financing) with a
     sample of its runs, chosen when the folder was exported to rotate through the Fed responses, durations and sizes
     stored for that shock ("stored_runs" says how many the page's file holds); each is solved again by the engine's
     own config_task (the function engine/build.py uses) and every one of its 32 variables x 41 quarters is compared
     with the stored numbers. A run passes when no number differs by more than --tol (default 1e-4). The
     stored numbers are rounded to three decimals and normally come back identical; because pyfrbus stops its Newton
     iterations at a relative tolerance of 0.0005, a floating-point difference (another machine or library build, even
     another process environment) can occasionally move one by 0.001. verify.py says so when that is all it finds,
     and --tol 0.0015 accepts it.
Runs the page lists as not solved (each file's "failed" list) are not attempted: a forward-looking run that does not
converge can take minutes to fail.

Writes output/verify_report.csv (one row per check) and exits 1 if anything fails.
"""
import argparse
import csv
import json
import math
import os
import platform
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = ROOT / "expected"
OUTPUT = ROOT / "output"
sys.path.insert(0, str(ROOT / "engine"))


def parse_key(key):
    size, fed, dur = key.split("|")
    s = float(size)
    return (int(s) if s.is_integer() else s), fed, dur


def worst_diff(got, want):
    """The largest absolute difference between two runs ({var: [values]}) and where it is; inf if they differ in shape
    or in which numbers are missing."""
    if set(got) != set(want):
        return math.inf, f"variables differ: {sorted(set(got) ^ set(want))}"
    worst, where = 0.0, ""
    for v in want:
        a, b = got[v], want[v]
        if len(a) != len(b):
            return math.inf, f"{v}: {len(a)} quarters vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            if x is None or y is None:
                if x is None and y is None:
                    continue
                return math.inf, f"{v}[{i}]: {x} vs {y}"
            d = abs(x - y)
            if d > worst:
                worst, where = d, f"{v}[{i}]"
    return worst, where


def compare_values(got, want, tol, path=""):
    """Recursive comparison of JSON-like values: numbers within tol, everything else exactly. Returns a list of
    differences (empty if equal)."""
    if isinstance(want, bool) or want is None or isinstance(want, str):
        return [] if got == want else [f"{path}: {got!r} vs {want!r}"]
    if isinstance(want, (int, float)):
        if isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want) <= tol:
            return []
        return [f"{path}: {got!r} vs {want!r}"]
    if isinstance(want, dict):
        if not isinstance(got, dict) or set(got) != set(want):
            return [f"{path}: keys {sorted(got) if isinstance(got, dict) else got!r} vs {sorted(want)}"]
        return [d for k in want for d in compare_values(got[k], want[k], tol, f"{path}.{k}")]
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return [f"{path}: length {len(got) if isinstance(got, list) else got!r} vs {len(want)}"]
        return [d for i, (g, w) in enumerate(zip(got, want)) for d in compare_values(g, w, tol, f"{path}[{i}]")]
    return [] if got == want else [f"{path}: {got!r} vs {want!r}"]


META_KEYS = ["model", "vintage", "baseline", "shocks", "sizes", "fed", "exp", "elb", "fiscal", "vars", "top", "unavailable"]


def load_files(args):
    files = {}
    for path in sorted((EXPECTED / "runs").glob("*.json")):
        body = json.loads(path.read_text())
        keep = ((not args.shocks or body["shock"] in args.shocks.split(","))
                and (not args.exp or body["exp"] == args.exp)
                and (not args.elb or body["elb"] == args.elb)
                and (not args.fiscal or body["fiscal"] == args.fiscal))
        if keep:
            files[path.stem] = body
    return files


def tasks_for(files, picks, calib, B, by="rule"):
    """Model tasks for build.config_task: one per file and rule (or per file and Fed response with by="fed", to spread
    a full rebuild over the workers), each carrying the runs it should solve."""
    tasks = []
    for fk, keys in picks.items():
        body = files[fk]
        groups = defaultdict(list)
        for k in keys:
            size, fed, dur = parse_key(k)
            rule = fed if fed in B.RULE_IDS else "inertial"     # a hold runs under the inertial rule once it ends
            groups[rule if by == "rule" else fed].append((size, fed, dur))
        for g, only in groups.items():
            rule = only[0][1] if only[0][1] in B.RULE_IDS else "inertial"
            tasks.append(dict(shock=body["shock"], rule=rule, exp=body["exp"], elb=body["elb"], fiscal=body["fiscal"],
                              sizes=sorted({o[0] for o in only}), durs=sorted({o[2] for o in only}),
                              feds=sorted({o[1] for o in only}), calib=calib, only=only, file=fk))
    cost = {("mce", "yes"): 3, ("mce", "no"): 2}
    tasks.sort(key=lambda t: (-cost.get((t["exp"], t["elb"]), 1), -len(t["only"])))     # the slowest first
    return tasks


def compare_dir(other, tol, files):
    """--compare: a library rebuilt with engine/build.py (other/runs/*.json) against expected/, run by run (the runs
    expected/ holds; a rebuilt run expected/ does not hold is not compared). A stored run with no rebuilt counterpart,
    including every run of a file that was not rebuilt at all, is counted, named and listed in the report as MISSING."""
    rows, nfail, nmissing = [], 0, 0
    for fk, body in files.items():
        path = other / "runs" / f"{fk}.json"
        if not path.exists():
            nmissing += len(body["runs"])
            print(f"MISSING  {fk}: no rebuilt file {path.name}, so its {len(body['runs'])} stored runs are not compared")
            rows += [dict(check="run", file=fk, key=k, status="MISSING", max_abs_diff="", where="no rebuilt file", seconds="")
                     for k in body["runs"]]
            continue
        mine = json.loads(path.read_text())
        for k, want in body["runs"].items():
            if k not in mine["runs"]:
                nmissing += 1
                rows.append(dict(check="run", file=fk, key=k, status="MISSING", max_abs_diff="", where="not in the rebuilt file", seconds=""))
                continue
            d, where = worst_diff(mine["runs"][k], want)
            ok = d <= tol + 1e-9
            nfail += not ok
            rows.append(dict(check="run", file=fk, key=k, status="PASS" if ok else "FAIL", max_abs_diff=d, where=where, seconds=""))
            if not ok:
                print(f"FAIL  {fk}  {k}  max diff {d:.6g} at {where}")
    return rows, nfail, nmissing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=3, help="worker processes (default 3; each forward-looking model needs a few GB)")
    ap.add_argument("--tol", type=float, default=1e-4, help="largest difference allowed in any stored number (default 1e-4)")
    ap.add_argument("--shocks", default="", help="comma-separated shock ids (default: all)")
    ap.add_argument("--exp", default="", choices=["", "var", "mce"])
    ap.add_argument("--elb", default="", choices=["", "no", "yes"])
    ap.add_argument("--fiscal", default="", choices=["", "fixed", "debt"])
    ap.add_argument("--compare", metavar="DIR", help="compare DIR/runs/*.json (a rebuilt library) with expected/ instead of solving")
    args = ap.parse_args()
    try:
        os.nice(10)                      # long CPU-heavy work yields to anything interactive
    except OSError:
        pass
    t0 = time.time()
    import numpy, pandas, scipy
    print(f"verify: Python {platform.python_version()}, numpy {numpy.__version__}, pandas {pandas.__version__}, "
          f"scipy {scipy.__version__}, {platform.platform()}")
    import build as B
    print(f"verify: the Board's packages from {B.FED.relative_to(ROOT) if B.FED.is_relative_to(ROOT) else B.FED}")
    files = load_files(args)
    if not files:
        sys.exit("verify: no stored file matches the selection")
    rows, nfail = [], 0
    OUTPUT.mkdir(exist_ok=True)
    meta = json.loads((EXPECTED / "meta.json").read_text())

    if args.compare:
        other = Path(args.compare)
        if not other.is_absolute():
            other = ROOT / other
        rows, nfail, nmissing = compare_dir(other, args.tol, files)
        if (other / "meta.json").exists():
            built = json.loads((other / "meta.json").read_text())
            diffs = [d for k in META_KEYS + ["calibration"] for d in compare_values(built.get(k), meta.get(k), args.tol, k)]
            nfail += bool(diffs)
            rows.append(dict(check="meta", file="meta.json", key="", status="FAIL" if diffs else "PASS", max_abs_diff="", where="; ".join(diffs[:5]), seconds=""))
            print(f"{'FAIL' if diffs else 'PASS'}  meta.json (menus, baseline, calibration, vintage)" + (f": {diffs[:3]}" if diffs else ""))
        npass = sum(r["status"] == "PASS" for r in rows if r["check"] == "run")
        print(f"\nverify --compare {args.compare}: {npass} runs PASS, {nfail} FAIL; {nmissing} stored runs not in {args.compare} (not rebuilt yet)")
        last_digit_note(rows)
        write_report(rows)
        sys.exit(1 if nfail or not npass else 0)      # nothing compared is not a pass

    # 1. the stock-price calibrations, rerun
    t1 = time.time()
    reqp, drop = B.calibrate_stocks()
    zd, zd_drop, _ = B.calibrate_earnings()
    calib = {"reqp_per_10pct": reqp, "check_drop_at_0.4": drop, "zdivgr_per_10pct": zd, "check_earn_drop": zd_drop}
    diffs = compare_values(calib, meta["calibration"], args.tol, "calibration")
    nfail += bool(diffs)
    print(f"{'FAIL' if diffs else 'PASS'}  calibration: equity premium +{reqp} per 10% fall, expected dividend growth {zd} per 10% fall"
          f" ({time.time() - t1:.0f} s)" + (f": {diffs}" if diffs else ""))
    rows.append(dict(check="calibration", file="meta.json", key="", status="FAIL" if diffs else "PASS", max_abs_diff="", where="; ".join(diffs), seconds=round(time.time() - t1, 1)))

    # 2. the menus, baseline values and vintage the engine writes into meta.json
    vintage = json.loads((B.FED / "VINTAGE.json").read_text())
    built = B.build_meta(calib, vintage, {})
    diffs = [d for k in META_KEYS for d in compare_values(built.get(k), meta.get(k), args.tol, k)]
    nfail += bool(diffs)
    print(f"{'FAIL' if diffs else 'PASS'}  meta.json: baseline values, menus, variables and the Board's package vintage"
          f" (data package {vintage['data']['last_modified']}, history through {vintage['history_ends']})" + (f": {diffs[:5]}" if diffs else ""))
    rows.append(dict(check="meta", file="meta.json", key="", status="FAIL" if diffs else "PASS", max_abs_diff="", where="; ".join(diffs[:5]), seconds=""))

    # 3. the runs
    picks = {fk: sorted(body["runs"]) for fk, body in files.items()}
    tasks = tasks_for(files, picks, calib, B)
    nruns = sum(len(t["only"]) for t in tasks)
    nshocks = len({b["shock"] for b in files.values()})
    print(f"\nverify: rebuilding {nruns} stored runs (the sample in expected/) from {len(files)} files ({nshocks} shocks) in {len(tasks)} model "
          f"configurations on {args.workers} worker processes; forward-looking configurations take a minute or more each")
    if any(B.SHOCKS[t["shock"]].get("model") == "invest" for t in tasks):
        import invest_model
        invest_model.ensure()            # the business-investment shock's model file, written once before the workers start
    try:
        import multiprocess as mp
    except ImportError:
        import multiprocessing as mp
    done = npass = 0
    with mp.Pool(args.workers, maxtasksperchild=1) as pool:
        for r in pool.imap_unordered(B.config_task, tasks):
            done += 1
            t = r["task"]
            fk = t["file"]
            for size, fed, dur in t["only"]:
                key = B.run_key(size, fed, dur, t["exp"], t["elb"], t["fiscal"])
                want = files[fk]["runs"][key]
                if key in r["runs"]:
                    d, where = worst_diff(r["runs"][key], want)
                else:
                    err = dict(r["failed"]).get(key) or "; ".join(f"{k}: {e}" for k, e in r["failed"]) or "no run returned"
                    d, where = math.inf, f"did not solve: {err}"
                ok = d <= args.tol + 1e-9
                npass += ok
                nfail += not ok
                rows.append(dict(check="run", file=fk, key=key, status="PASS" if ok else "FAIL", max_abs_diff=d, where=where, seconds=round(r["secs"], 1)))
                print(f"{'PASS' if ok else 'FAIL'}  [{done}/{len(tasks)}] {fk:<28s} {key:<22s} max diff {d:.2g}"
                      + (f" at {where}" if not ok else "") + f"  ({r['secs']:.0f} s)", flush=True)
    write_report(rows)
    last_digit_note(rows)
    mins = (time.time() - t0) / 60
    print(f"\nverify: {npass} of {nruns} rebuilt runs PASS, {nruns - npass} FAIL (tolerance {args.tol:g}); "
          f"calibration and meta.json {'PASS' if not any(r['status'] == 'FAIL' for r in rows if r['check'] != 'run') else 'FAIL'}; "
          f"{mins:.1f} minutes")
    print("verify: " + ("PASS" if nfail == 0 else "FAIL") + "  (report: output/verify_report.csv)")
    sys.exit(0 if nfail == 0 else 1)


def last_digit_note(rows):
    """When every failing run is off by one unit in the stored third decimal and nothing else failed, say what that is."""
    bad = [r for r in rows if r["status"] == "FAIL"]
    if bad and all(r["check"] == "run" and isinstance(r["max_abs_diff"], float) and r["max_abs_diff"] <= 0.00101 for r in bad):
        print("verify: every difference is one unit in the stored third decimal. pyfrbus stops its Newton iterations at a "
              "relative tolerance of 0.0005, so a floating-point difference too small to matter (another machine, library "
              "build or even process environment) can change the step at which it stops and move a rounded number by "
              "0.001. Rerun with --tol 0.0015 to accept differences of that size.")


def write_report(rows):
    OUTPUT.mkdir(exist_ok=True)
    with open(OUTPUT / "verify_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check", "file", "key", "status", "max_abs_diff", "where", "seconds"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
