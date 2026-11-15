#!/usr/bin/env python3
"""Rebuild everything this package can rebuild, then check it against the post.

    python run_all.py              # numbers, figures, then verify.py
    python run_all.py --no-figures

Steps (each can be run on its own): python -m howfar.numbers ; python -m howfar.figures ; python verify.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def step(args):
    print(f"\n$ python {' '.join(args)}", flush=True)
    return subprocess.call([sys.executable, *args], cwd=ROOT)


if __name__ == "__main__":
    if step(["-m", "howfar.numbers"]):
        sys.exit("run_all: the numbers step failed")
    if "--no-figures" not in sys.argv and step(["-m", "howfar.figures"]):
        sys.exit("run_all: the figures step failed")
    sys.exit(step(["verify.py"]))
