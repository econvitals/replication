"""The baseline the page draws levels on: the Federal Reserve Board's own projection in its FRB/US data package,
from the current quarter, for every stored variable. Written to <FRBUS_OUT>/current.json.

  python engine/current_baseline.py        (build.py also calls write() after every build)

Why this path (2026-11-11: levels off the 2040 steady state showed inflation slowing below 2 percent when it is
well above that today; "off the SEP?"). The data package's README says its baseline "follows the median projections in
FOMC's Summary of Economic Projections (SEP) where they are available. Beyond the horizon of the SEP, the baseline
projection is a model-guided extrapolation. Variables that are available in the SEP gradually converge to the median of
the SEP's longer-run projections." Checked 2026-11-11 against the September 2026 SEP's published medians: Q4 core PCE
3.40 / 2.50 / 2.20 / 2.00 for 2026-29, Q4/Q4 real GDP 2.30 / 2.40 / 2.20 / 2.10, unemployment 4.10, headline PCE 3.70 /
2.30 — every one equal to the printed median. So this is the SEP path for the SEP's five variables and the Board's
consistent extension of it for everything else.

The runs themselves are still changes from the 2040Q1 steady state (build.py). The page adds them to this path; FRB/US
is close to linear in normal times, so that is close to what a run from this path would give (not at the lower bound,
where the page says so). Units match the page's levels: an index with the quarter before the shock = 100 for
percent-kind variables, percent for rates (lfpr and the tax rate scaled like their changes), percent of GDP for the
fiscal ratios, dollars a barrel for oil.
"""
import json
import time

import pandas as pd

from build import FED, H, OUT, VARS, data

PRE = 4                          # quarters stored before the shock (growth over a year needs four)
SEP_MONTHS = (3, 6, 9, 12)       # the SEP rounds; each is published around the 17th of its month
# The page's variables whose baseline IS the SEP median (Q4/Q4 real GDP growth, Q4 unemployment, Q4/Q4 PCE and core PCE
# inflation, the year-end funds rate) through the SEP's last year; every other line is the Board's model extension of
# it. The page labels each chart's baseline with this (2026-11-11: "I like your label"), because some extensions
# look like forecasts nobody made — stock and house prices drift down for three years as the model pulls them back.
SEP_VARS = ["xgdp", "lur", "pic4", "picx4", "rff"]


def start_quarter(history_ends):
    """The quarter the shock hits: the current calendar quarter, and never one the package holds history for."""
    now = pd.Period(time.strftime("%Y-%m-%d"), freq="Q")
    first = pd.Period(history_ends, freq="Q") + 1 if history_ends else now
    return max(now, first)


def sep_round(package_date):
    """The SEP round the package's baseline follows (the last one published before the package's date), as
    (its name, the last calendar year it projects: three years on in September and December, two in March and June)."""
    d = pd.Timestamp(package_date)
    rounds = [pd.Timestamp(y, m, 20) for y in (d.year - 1, d.year) for m in SEP_MONTHS]
    last = max(r for r in rounds if r < d)
    return last.strftime("%B %Y"), last.year + (3 if last.month >= 9 else 2)


def paths(start):
    idx = pd.period_range(start - PRE, periods=PRE + H + 1)
    d = data().loc[idx]
    ratio = lambda num: 100 * d[num] / d["xgdpn"]
    out = {}
    for v, _, kind, _ in VARS:
        if v == "realwage": x = d["pl"] / d["pcnia"]
        elif v == "gov": x = ratio("egfen")
        elif v == "transfers": x = ratio("gtn")
        elif v == "surplus": x = ratio("gfsrpn")
        elif v == "debt": x = ratio("gfdbtnp")
        elif v == "curacct": x = ratio("fcbn")
        elif v == "taxrate": x = 100 * d["trp"]
        elif v == "lfpr": x = 100 * d["lfpr"]
        else: x = d[v]
        if kind == "pct": x = 100 * x / x.iloc[PRE - 1]
        out[v] = [round(float(t), 4) for t in x.values]
    return out


def write(out_dir=OUT):
    vintage = json.loads((FED / "VINTAGE.json").read_text()) if (FED / "VINTAGE.json").exists() else {}
    package_date = (vintage.get("data") or {}).get("last_modified")
    start = start_quarter(vintage.get("history_ends"))
    body = {"start": str(start), "first": str(start - PRE), "pre": PRE, "horizon": H,
            "package_date": package_date, "history_ends": vintage.get("history_ends"),
            "sep": sep_round(package_date)[0] if package_date else None,
            "sep_through": sep_round(package_date)[1] if package_date else None, "sep_vars": SEP_VARS,
            "written": time.strftime("%Y-%m-%d"), "values": paths(start)}
    (out_dir / "current.json").write_text(json.dumps(body, separators=(",", ":")) + "\n")
    return body


if __name__ == "__main__":
    import os
    from pathlib import Path
    b = write(Path(os.environ["FRBUS_OUT"]) if os.environ.get("FRBUS_OUT") else OUT)
    v = b["values"]
    print(f"current.json: shock hits {b['start']}, package {b['package_date']} (follows the {b['sep']} SEP); "
          f"core PCE {v['picx4'][PRE]}, unemployment {v['lur'][PRE]}, funds rate {v['rff'][PRE]}")
