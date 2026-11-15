"""Paths and loaders shared by every step."""
import csv
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"            # public data, shipped with the package
LICENSED = ROOT / "licensed"    # licensed or website data: NOT shipped; see licensed/README.md
OUT = ROOT / "output"
D = dt.date

# The evaluation date of the post: the close of Friday, November 13, 2026.
NOW = D(2026, 11, 13)

# The Shiller ratio on November 13, 2026, as shown by multpl.com (which extends Shiller's monthly series
# day by day with S&P's prices and earnings). One published reading, cited here rather than shipped as a series.
CAPE_NOW = 39.95


def have(name):
    return (LICENSED / name).exists()


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fred(series):
    """A FRED download (fredgraph.csv): {date: value}, missing values dropped."""
    out = {}
    for r in rows(DATA / f"fred_{series.lower()}.csv"):
        v = r[series]
        if v not in ("", "."):
            y, m, d = map(int, r["observation_date"].split("-"))
            out[D(y, m, d)] = float(v)
    return out


def daily_closes(name):
    """A licensed daily-close file: {date: close}."""
    out = {}
    for r in rows(LICENSED / name):
        y, m, d = map(int, r["date"].split("-"))
        out[D(y, m, d)] = float(r["close"])
    return out


def month_key(s):
    y, m = s.split("-")
    return int(y), int(m)


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
