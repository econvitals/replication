#!/usr/bin/env python3
"""run_all.py: rebuild everything in the post, in order, from the frozen inputs, and check it against the post.

    python run_all.py                  # the post's runs (about 10 minutes with three workers on an eight-core Apple M1)
    python run_all.py --workers 2      # fewer worker processes for the model runs (default 3)
    python run_all.py --all-shares     # also the sensitivity runs (85 and 50 percent imported)
    python run_all.py --skip-runs      # reuse output/results/*.json from an earlier run
    python run_all.py --try-unsolved   # with --stock-mode premium: also attempt the runs known not to solve (adds 30 minutes or more)
    python run_all.py --stock-mode premium   # the stock gain as a lower equity premium (earlier drafts of the post)
                                             # instead of higher expected earnings (the default)

Steps (each is also a module you can run alone with python -m):
  1. dcboom.inputs       the shock and the actual series, rebuilt from data/ and checked against data/as_used/
  2. dcboom.model_setup  the data-center version of the Board's model file -> output/model/model_dc.xml
  3. dcboom.runs         every FRB/US run behind the post, the boom ending in 2027 among them -> output/results/*.json
  4. dcboom.table        the summary table
  5. dcboom.figures      figures 1-10 and appendix figures 1-4
  6. dcboom.facts        every number in the post, recomputed -> output/results/facts.json
  7. verify.py           the rebuilt numbers against the post (expected.csv)
Nothing here uses the network.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--all-shares", action="store_true")
    ap.add_argument("--skip-runs", action="store_true")
    ap.add_argument("--try-unsolved", action="store_true")
    ap.add_argument("--stock-mode", choices=("earnings", "premium"), default="earnings")
    a = ap.parse_args()
    try:
        if os.nice(0) < 10:
            os.nice(10 - os.nice(0))          # be a polite neighbor on a shared machine
    except (OSError, AttributeError):         # AttributeError: no os.nice on Windows
        pass
    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env.setdefault(k, "1")                # one thread per worker process
    steps = [["-m", "dcboom.inputs"], ["-m", "dcboom.model_setup"]]
    if not a.skip_runs:
        steps.append(["-m", "dcboom.runs", "--workers", str(a.workers)] + (["--all-shares"] if a.all_shares else [])
                     + (["--try-unsolved"] if a.try_unsolved else []) + ["--stock-mode", a.stock_mode])
    steps += [["-m", "dcboom.table"], ["-m", "dcboom.figures"], ["-m", "dcboom.facts"], ["verify.py"]]
    t0 = time.time()
    rc = 0
    for s in steps:
        t = time.time()
        print(f"\n### {' '.join(s)}", flush=True)
        r = subprocess.run([sys.executable] + s, cwd=ROOT, env=env)
        print(f"### {' '.join(s)}: {'ok' if r.returncode == 0 else 'exit ' + str(r.returncode)} in {time.time() - t:.0f} s", flush=True)
        if r.returncode != 0:
            rc = r.returncode
            if s[0] != "verify.py":
                sys.exit(f"run_all: stopped at {' '.join(s)}")
    print(f"\nrun_all: finished in {(time.time() - t0) / 60:.1f} minutes; outputs in output/", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
