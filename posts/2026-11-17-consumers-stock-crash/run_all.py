#!/usr/bin/env python3
"""Rebuild every number and figure in the post and its online appendix from the frozen data, then check them.

    python run_all.py               # everything, then verify.py
    python run_all.py --no-figures  # numbers only (faster), then verify.py

Each step is a script in wealth/ that can also be run on its own from this folder, in this order.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("build_panel.py", [], "the quarterly panel from the frozen Financial Accounts, BEA and FRED series"),
    ("rolling.py", ["output"], "fixed periods, rolling windows, break tests, era estimates (changes model)"),
    ("asymmetry.py", ["output"], "gains versus losses in the changes model"),
    ("literature_specs.py", ["output"], "published specifications on today's data (the constant-elasticity model)"),
    ("frbus_since_2019.py", ["output"], "FRB/US's consumption equations run from 2019 on the Board's data"),
    ("rules_since_2019.py", [], "the simple rules, the consumption function and FRB/US since 2019"),
    ("cf_calc.py", [], "the consumption function: estimates, diagnostics, projection, sensitivity"),
    ("cf_extras.py", [], "the out-of-sample record from every anchor year; breaks at given dates"),
    ("expanding_rolling.py", [], "the stock coefficient through each quarter and over rolling 20-year windows"),
    ("appendix_numbers.py", [], "the anchors, back-of-the-envelope bases, FRB/US cents and Table 1"),
    ("appendix_tables.py", [], "every table in the online appendix, rebuilt"),
    ("post_numbers.py", [], "the post's other numbers: stock values, 2001, 1987, housing, ownership, Forbes"),
    ("collect.py", [], "every number in one file, output/numbers.json"),
]
FIGS = [
    ("post_figures.py", [], "the post's Table 1 and Figures 1-7"),
    ("appendix_figures.py", [], "the appendix's Figures A1-A5"),
]


def step(script, args, what):
    t0 = time.time()
    print(f"\n$ python wealth/{script} {' '.join(args)}   # {what}", flush=True)
    rc = subprocess.call([sys.executable, str(ROOT / "wealth" / script), *args], cwd=ROOT)
    print(f"  ({time.time() - t0:.0f} s)", flush=True)
    return rc


if __name__ == "__main__":
    (ROOT / "output").mkdir(exist_ok=True)
    for s, a, w in STEPS + ([] if "--no-figures" in sys.argv else FIGS):
        if step(s, a, w):
            sys.exit(f"run_all: {s} failed")
    sys.exit(subprocess.call([sys.executable, str(ROOT / "verify.py")], cwd=ROOT))
