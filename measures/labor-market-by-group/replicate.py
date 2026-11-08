"""Labor Market by Group — rebuilds the data behind the interactive table on
econvitals.org/labor/demographicdetail/#bygroup.

    python replicate.py cps_00001.csv.gz      # an IPUMS CPS extract you request yourself

writes output/cells.csv (the collapsed cells) and output/labor-by-group.json (the file the page
reads). IPUMS's terms do not allow the survey responses to be passed on, so this folder contains
no microdata: request the extract described in README.md (free, with an IPUMS account) and point
this script at it. Nothing here is compared with the live site every night.

What it does:
  1. Keeps people 16 and over with a positive final weight who are in or out of the labor force
     (the civilian noninstitutional population), and puts each in a cell by month, sex, single
     year of age (80 = 80 and over), five race and ethnicity groups (Hispanic of any race, then
     non-Hispanic White, Black, Asian and everyone else) and four education groups (less than
     high school, high school, some college, bachelor's degree or more).
  2. Adds up, in each cell, the weighted population, labor force and employment, and the
     unweighted counts (the page uses those to flag small samples).
  3. Pools the cells over the windows the page offers: the latest 12 or 3 months, and the same
     months at each business-cycle peak (the 12 months ending March 2001, December 2007 or
     February 2020; for 3 months, the same season in 2000, 2007 or 2019) or a year earlier. A
     calendar month missing on either side of a comparison is dropped from both, which today
     drops October because October 2025 was not collected.
The page then computes participation, employment and unemployment rates for any combination of
groups from those pooled totals. The rates are raw, not seasonally or otherwise adjusted.
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
COLUMNS = ["YEAR", "MONTH", "AGE", "SEX", "RACE", "HISPAN", "EDUC", "EMPSTAT", "LABFORCE", "WTFINL"]


# ------------------------------------------------------------------ 1-2. microdata -> cells
def collapse(d: pd.DataFrame) -> pd.DataFrame:
    """Person records -> weighted and unweighted totals by month x sex x age x race x education."""
    d = d[(d.AGE >= 16) & d.SEX.isin([1, 2]) & (d.WTFINL > 0) & d.LABFORCE.isin([1, 2])].copy()
    d["age"] = d.AGE.clip(upper=80)
    d["sex"] = d.SEX.map({1: "m", 2: "f"})
    hispanic = d.HISPAN.between(100, 612)
    d["race_eth"] = np.select(
        [hispanic, d.RACE == 100, d.RACE == 200, d.RACE.isin([650, 651, 652])],
        ["hispanic", "white_nh", "black_nh", "asian_nh"], "other_nh")
    d["educ"] = np.select([d.EDUC < 73, d.EDUC < 81, d.EDUC < 111],
                          ["lths", "hs", "somecoll"], "ba")    # 73 = high school diploma or GED
    in_lf = d.LABFORCE == 2
    employed = d.EMPSTAT.isin([10, 12])                        # at work, or has a job not at work
    d["POP"], d["LF"], d["EM"] = d.WTFINL, d.WTFINL * in_lf, d.WTFINL * employed
    d["NPOP"], d["NLF"], d["NEM"] = 1, in_lf.astype(int), employed.astype(int)
    return (d.groupby(["YEAR", "MONTH", "sex", "age", "race_eth", "educ"], observed=True)
             [["LF", "EM", "POP", "NPOP", "NLF", "NEM"]].sum().reset_index()
             .rename(columns={"YEAR": "year", "MONTH": "month"}))


def cells_from_extract(paths) -> pd.DataFrame:
    """Read IPUMS CSV extracts in pieces (a 2000-to-date extract is tens of millions of rows)."""
    parts = []
    for path in paths:
        for chunk in pd.read_csv(path, usecols=lambda c: c.upper() in COLUMNS, chunksize=2_000_000):
            chunk.columns = [c.upper() for c in chunk.columns]
            parts.append(collapse(chunk))
    keys = ["year", "month", "sex", "age", "race_eth", "educ"]
    cells = pd.concat(parts).groupby(keys, observed=True).sum().reset_index()
    # IPUMS applies WTFINL's four implied decimals in its CSV files; if a file arrived without
    # them, a month's weights would add up to ~2.7 trillion people instead of ~270 million.
    if cells.groupby(["year", "month"]).POP.sum().median() > 1e10:
        cells[["LF", "EM", "POP"]] /= 10_000
    return cells


# ------------------------------------------------------------------ 3. pooled windows
AGES = ["a1624", "a2554", "a55p"]
FROM_OPTIONS = ["p2000", "p2007", "p2019", "yearago"]          # always compared with the latest
LABELS = {"p2000": ("the 2000–01 peak", "2000–01"), "p2007": ("the 2007 peak", "2007"),
          "p2019": ("the 2019–20 peak", "2019–20"), "yearago": ("a year earlier", "Year ago"),
          "latest": ("the latest data", "Latest")}
PEAK_END = {"p2000": (2001, 3), "p2007": (2007, 12), "p2019": (2020, 2)}   # 12-month window ends
PEAK_YEAR = {"p2000": 2000, "p2007": 2007, "p2019": 2019}                  # 3-month season year


def index(y, m): return y * 12 + (m - 1)
def ym(i): return (i // 12, i % 12 + 1)
def trailing(end, n): return [ym(index(*end) - k) for k in range(n - 1, -1, -1)]
def back(months, years): return [(y - years, m) for (y, m) in months]


def from_window(p, n, latest, latest_year, first):
    """The comparison window: the latest window a year back, the 12 months ending at a peak, or
    the latest 3-month season in the peak year (moved a year later if that would reach before
    the data start, as a December-February season does for the 2000-01 peak)."""
    if p == "yearago":
        return back(latest[n], 1)
    if n == 12:
        return trailing(PEAK_END[p], 12)
    months = back(latest[n], latest_year - PEAK_YEAR[p])
    return back(months, -1) if months[0] < first else months


def align(fromm, tom, present):
    """Keep only the calendar months present on BOTH sides, so a missing month is dropped from
    both and cannot tilt the comparison."""
    f = {m: (y, m) for (y, m) in fromm}
    t = {m: (y, m) for (y, m) in tom}
    keep = [m for m in f if m in t and f[m] in present and t[m] in present]
    return [f[m] for m in keep], [t[m] for m in keep]


def build(cells: pd.DataFrame) -> dict:
    df = cells.copy()
    df["ab"] = pd.cut(df.age, [15, 24, 54, 200], labels=AGES).astype(str)
    df["ym"] = df.year * 100 + df.month
    present = set(map(tuple, df[["year", "month"]].drop_duplicates().to_numpy()))
    last = max(index(y, m) for (y, m) in present)
    latest = {12: trailing(ym(last), 12), 3: trailing(ym(last), 3)}

    def pooled(months):
        sub = df[df.ym.isin({y * 100 + m for (y, m) in months})]
        g = sub.groupby(["sex", "ab", "race_eth", "educ"], observed=True)[
            ["LF", "EM", "POP", "NLF", "NPOP"]].sum()
        return {f"{s}|{a}|{r}|{e}": [round(x.LF), round(x.EM), round(x.POP), int(x.NLF), int(x.NPOP)]
                for (s, a, r, e), x in g.iterrows()}

    def label(months): return [f"{y}-{m:02d}" for (y, m) in sorted(months)]

    cmp = {}
    for p in FROM_OPTIONS:
        cmp[p] = {}
        for n in (12, 3):
            f, t = align(from_window(p, n, latest, ym(last)[0], min(present)), latest[n], present)
            cmp[p][str(n)] = {"from": pooled(f), "to": pooled(t), "fm": label(f), "tm": label(t)}
    level = {}
    for n in (12, 3):
        keep = [m for m in latest[n] if m in present]
        level[str(n)] = {"cells": pooled(keep), "m": label(keep)}
    return {"generated": date.today().isoformat(), "through": "%d-%02d" % ym(last),
            "sexes": ["m", "f"], "ages": AGES,
            "races": ["white_nh", "black_nh", "hispanic", "asian_nh", "other_nh"],
            "educs": ["lths", "hs", "somecoll", "ba"], "from_options": FROM_OPTIONS,
            "periods": {k: v[0] for k, v in LABELS.items()},
            "periods_short": {k: v[1] for k, v in LABELS.items()},
            "cmp": cmp, "level": level}


def national(pooled: dict) -> dict:
    lf, em, pop = (sum(v[i] for v in pooled.values()) for i in range(3))
    return {"UR": 100 * (lf - em) / lf, "LFPR": 100 * lf / pop, "EPOP": 100 * em / pop}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python replicate.py <IPUMS CPS extract .csv or .csv.gz> [more ...]"
                         "\nSee README.md for the extract to request.")
    cells = cells_from_extract(sys.argv[1:])
    (HERE / "output").mkdir(exist_ok=True)
    cells.to_csv(HERE / "output" / "cells.csv", index=False)
    data = build(cells)
    (HERE / "output" / "labor-by-group.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"{len(cells):,} cell-months, through {data['through']}")
    for p in ("p2019", "yearago"):
        c = data["cmp"][p]["12"]
        if not c["from"]:
            continue                                  # the extract does not reach back that far
        a, b = national(c["from"]), national(c["to"])
        print(f"  {LABELS[p][1]:>8} -> latest, 12-month windows: "
              + ", ".join(f"{k} {b[k] - a[k]:+.2f} pp" for k in a))
