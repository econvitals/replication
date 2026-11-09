"""reversal.py: what FRB/US says happens if the boom ends in 2027, behind the post's symmetry paragraph (after the
table) and its future section. Written to output/results/reversal_runs.json.

Every run starts from the world in which the boom happened and then holds: the Board's LONGBASE, reproduced by
tracking residuals, with the buildout at its 2026Q4 share of GDP and the stock gain at its share of market value
on November 5, 2026 (the post's dotted lines). Each run then takes part of the boom out of that world, or adds a
second one, with the same pieces engine.counterfactual uses:
  * the buildout: the excess spending (share of nominal GDP) and its imported part, entered as `edc` and `emdc`,
    each times r_B(t), the share of the buildout taken out, and a sign (-1 takes it out, +1 adds it again);
  * stock wealth: household stock wealth `wpsn` pinned to the run's own world before the stock change (its first
    solve, with the buildout change alone: the world in which the buildout has ended, for the bust) times
    (1 - r_S(t) f(t)), or divided by it for sign +1, through the same instrument and step as
    engine.counterfactual (the add factor on expected dividend growth by default; the equity premium with
    --stock-mode premium), fitted 2023Q1-2028Q4 and held after. f(t) is the seven companies' extra gain as a share
    of market value: so the bust takes out exactly the AI stock gain, as the post's runs do (engine.stock_base).
    A flat share is a fall in the whole market, measured as the post means it, from the path with the boom (the
    baseline): household stock wealth 30 percent below it, whatever the buildout's end does to stock prices.
With r = 1 from 2023Q1 this is the post's world without the boom (B_s75 in post_extend.json); facts.py checks
that it is. Backward-looking expectations, the inertial rule and 75 percent imported, as in the post's central runs.

  noboom         r_B = r_S = 1 from 2023Q1: the post's world without the boom (the check, and the growth the boom
                 added in 2024-2026)
  bust           the boom through 2026Q4, then from 2027Q1 no buildout above trend and no stock gain
  build_ends     the buildout above trend gone from 2027Q1; stock wealth left to the model (the stock gain stays)
  bust_market30  the buildout gone and household stock wealth 30 percent lower from 2027Q1: the whole market falls
  mirror         a second boom the size of the first from 2027Q1 (sign +1): the bust's mirror image
The world in which the boom holds is the baseline itself (`holds` in the file).

    python -m dcboom.reversal [--stock-mode earnings|premium]   # about 5 seconds; also run by dcboom.runs
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd

from . import engine as E
from . import paths

T_END = pd.Period("2027Q1", "Q")                              # the boom ends (or a second one starts) here
FIT = pd.period_range(E.START, "2028Q4", freq="Q")            # stock-wealth target fitted here, instrument held after
KEEP = pd.period_range("2022Q1", "2030Q4", freq="Q")          # quarters written (the solve runs to 2030Q4)
VARS = ["xgdp", "lur", "rff", "rg10", "ecnia", "ebfi", "ebfio", "eh", "em", "wpsn", "picxfe", "xgap2", "edc", "emdc",
        "zdivgr", "xgdpt"]
# name: (buildout taken out, stock gain taken out, sign, flat share of stock wealth or None for the AI stock gain)
SCENARIOS = {
    "noboom": ("all", "all", -1, None),
    "bust": ("from2027", "from2027", -1, None),
    "build_ends": ("from2027", "none", -1, None),
    "bust_market30": ("from2027", "from2027", -1, 0.30),
    "mirror": ("from2027", "from2027", +1, None),
}


def ramp(q, kind):
    """r(t), the share taken out in each quarter of q: 'all' = from 2023Q1, 'from2027' = from 2027Q1, 'none'."""
    r = np.zeros(len(q))
    if kind == "all":
        r[:] = 1.0
    elif kind == "from2027":
        r[np.array([p >= T_END for p in q])] = 1.0
    elif kind != "none":
        raise ValueError(kind)
    return r


def solve_scenario(build, stock, sign=-1, share=None, stock_mode="earnings", tol=5e-4, maxit=10):
    """One run. Returns (cf, base, stock iterations): the solved world, the world in which the boom holds, and the
    largest stock-wealth gap after each solve."""
    fit_stock = stock != "none"
    f, wa, end = E.setup("var", "inertial", tuple(E.stock_exog(fit_stock, stock_mode)), False)
    fr = wa.copy()
    q = pd.period_range(E.START, end, freq="Q")
    s = E.PATHS["build"]("build").loc[q].values / 100.0
    mshare = E.import_share_series(0.75, "build")[0].loc[q].values / 100.0
    rB, rS = ramp(q, build), ramp(q, stock)
    ngdp = wa.loc[q, "xgdpn"].values
    fr.loc[q, "edc"] = sign * rB * s * ngdp / (0.01 * wa.loc[q, "pbfir"].values * wa.loc[q, "pxp"].values)
    fr.loc[q, "emdc"] = sign * rB * mshare * ngdp / (0.01 * wa.loc[q, "pmo"].values)
    cf = E.solve(f, end, fr, "var")
    hist = []
    if fit_stock:
        fcut = E.stock_cut().loc[q].values if share is None else np.full(len(q), share)
        lw = np.log(1 - rS * fcut)
        # the AI stock gain comes out of the run's own world (its first solve); a fall in the whole market is
        # measured from the path with the boom
        base_w = E.stock_base(cf, wa, q, stock_mode) if share is None else wa.loc[q, "wpsn"].values
        target = np.log(base_w) + (lw if sign < 0 else -lw)
        nS = len(FIT)
        col = E.STOCK_INSTRUMENT[stock_mode]
        step = E._premium_step if stock_mode == "premium" else E._earnings_step(f, "var", len(q), nS)
        x = np.zeros(len(q))
        for _ in range(maxit):
            gap = target - np.log(cf.loc[q, "wpsn"].values)
            err = float(np.max(np.abs(gap[:nS])))
            hist.append(round(err, 6))
            if err < tol:
                break
            x[:nS] += step(gap[:nS])
            x[nS:] = x[nS - 1]
            fr.loc[q, col] = wa.loc[q, col].values + x
            cf = E.solve(f, end, fr, "var")
        else:                                  # iteration limit reached: measure the last solve too
            gap = target - np.log(cf.loc[q, "wpsn"].values)
            err = float(np.max(np.abs(gap[:nS])))
            hist.append(round(err, 6))
        if err >= tol:
            raise RuntimeError(f"stock-wealth target not reached (gaps {hist}, tolerance {tol})")
    return cf, wa, hist


def _series(df):
    return {v: [float(x) for x in df.loc[KEEP, v].values] for v in VARS}


def run_reversal(spec=None):
    """Every scenario, in one process (they share one model setup). A scenario that fails is recorded, not raised:
    verify.py then fails the rows that need it."""
    mode = (spec or {}).get("stock_mode", "earnings")
    t0 = time.time()
    out = {"index": [str(p) for p in KEEP], "runs": {}, "stock_mode": mode}
    for name, (b, s, sign, share) in SCENARIOS.items():
        t1 = time.time()
        try:
            cf, base, hist = solve_scenario(b, s, sign, share, stock_mode=mode)
        except Exception as ex:
            out["runs"][name] = {"ok": False, "error": repr(ex)[:400], "secs": round(time.time() - t1, 1)}
            print(f"  reversal  {name:14s} did not solve: {repr(ex)[:120]}", flush=True)
            continue
        out.setdefault("holds", _series(base))
        out["runs"][name] = {"ok": True, "build": b, "stock": s, "sign": sign, "share": share, "stock_iterations": hist,
                             "secs": round(time.time() - t1, 1), "cf": _series(cf)}
    return {"name": "reversal", "ok": all(r["ok"] for r in out["runs"].values()), "secs": round(time.time() - t0, 1),
            "result": out}


def write(result):
    (paths.OUT_RESULTS / "reversal_runs.json").write_text(json.dumps(result))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stock-mode", choices=E.STOCK_MODES, default=E.STOCK_MODES[0])
    a = ap.parse_args(argv)
    try:
        if os.nice(0) < 10:
            os.nice(10 - os.nice(0))
    except (OSError, AttributeError):         # AttributeError: no os.nice on Windows
        pass
    paths.ensure()
    r = run_reversal({"stock_mode": a.stock_mode})
    write(r["result"])
    for name, run in r["result"]["runs"].items():
        if run["ok"]:
            print(f"  reversal  {name:14s} stock iterations {run['stock_iterations']} {run['secs']:5.1f}s", flush=True)
    print(f"reversal: {len(SCENARIOS)} scenarios in {r['secs']:.0f} s -> output/results/reversal_runs.json", flush=True)


if __name__ == "__main__":
    main()
