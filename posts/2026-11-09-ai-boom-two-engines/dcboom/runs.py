"""runs.py: every FRB/US run behind the post, written to output/results/.

  post_runs.json    A_s75  the buildout alone (backward-looking expectations, 75 percent imported)
                    B_s75  the buildout plus the AI stock gain (backward-looking)
                    C_s75  B with forward-looking expectations (mcap+wp, r* learning) and a believed
                           productivity payoff of +0.5 a year from 2027; solved by homotopy from +0.3
  post_extend.json  A_s75, B_s75 with effects through 2028Q4: the buildout held at its 2026Q4 share of GDP
                    and the stock gain held at its early-November share of market value (the dotted lines), and *_grows: the buildout rising another
                    0.5 percent of GDP a year through 2028
  news2026.json     expectations that switch on in 2026: B backward-looking through 2025Q4, forward-looking
                    from 2026Q1 with the news that the buildout continues through 2031, and a believed
                    productivity payoff of 0, 0.1, ..., 0.5 a year from 2027 (with the premium construction 0.5
                    does not solve, so there it is attempted only with --try-unsolved, which takes a long time to fail).
                    Each run's stock-wealth target is its own world without the stock gain, times (1 - f): the same
                    switch in 2026 from A's backward-looking world through 2025, with the same belief (one more
                    solve per belief; engine.stock_base)
  reversal_runs.json the boom ending in 2027, for the post's symmetry paragraph and its future section
                    (reversal.py): the bust, the buildout ending alone, the buildout ending with a 30 percent fall
                    in the whole stock market, and a second boom of the same size as the bust's mirror image

With --all-shares, also the sensitivity grid (import shares 85 and 50 percent, and the
forward-looking runs C0 = no productivity belief, P and M = forward-looking without the stock gain).
With the premium construction C_s50 does not solve, and it is attempted only with --try-unsolved; with the
earnings construction it solves and runs with the rest. None of these appear in the post.

The stock gain is removed as lower expected earnings by default (--stock-mode earnings); --stock-mode premium
removes it as a higher equity premium instead, the construction in earlier drafts of the post, and writes
exactly the files that construction wrote (engine.counterfactual explains both).

    python -m dcboom.runs [--workers 3] [--all-shares] [--try-unsolved] [--stock-mode earnings|premium]
"""
import argparse
import io
import json
import os
import time
from contextlib import redirect_stdout
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import engine as E
from . import paths
from . import reversal as R

EXT_IDX = pd.period_range("2023Q1", "2028Q4", freq="Q")
T1 = pd.Period("2026Q1", "Q")                                # news2026: expectations switch on here
HIST = pd.period_range(E.START, T1 - 1, freq="Q")


def post_tasks(all_shares=False, try_unsolved=False, stock_mode="earnings"):
    shares = ((0.75, "s75"), (0.85, "s85"), (0.50, "s50")) if all_shares else ((0.75, "s75"),)
    T = []
    for tgt, tag in shares:
        T += [dict(kind="post", name=f"A_{tag}", exp="var", target=tgt),
              dict(kind="post", name=f"B_{tag}", exp="var", target=tgt, stock=True)]
        if tag != "s50" or stock_mode != "premium":      # (C_s50 solves with the earnings construction)
            T.append(dict(kind="post", name=f"C_{tag}", exp="mcap", target=tgt, stock=True, rstar=True, prod=0.5, chain=[0.3]))
        elif try_unsolved:     # premium construction: does not solve, even in smaller homotopy steps
            T.append(dict(kind="post", name=f"C_{tag}", exp="mcap", target=tgt, stock=True, rstar=True, prod=0.5, chain=[0.15, 0.3, 0.4]))
        if all_shares:
            T += [dict(kind="post", name=f"C0_{tag}", exp="mcap", target=tgt, stock=True, rstar=True),
                  dict(kind="post", name=f"P_{tag}", exp="mcap", target=tgt, stock=False, rstar=True, prod=0.5),
                  dict(kind="post", name=f"M_{tag}", exp="mcap", target=tgt, stock=False, rstar=True)]
        for stock in (False, True):
            for grows in (False, True):
                T.append(dict(kind="extend", name=("B_" if stock else "A_") + tag + ("_grows" if grows else ""),
                              target=tgt, stock=stock, grows=grows))
    T.append(dict(kind="news2026", name="news2026", try_unsolved=try_unsolved))
    T.append(dict(kind="reversal", name="reversal"))
    for t in T:
        t["stock_mode"] = stock_mode          # passed to the workers in the task, and not recorded in its spec
    return T


def run_post(spec):
    spec = dict(spec); name = spec.pop("name"); spec.pop("kind"); chain = spec.pop("chain", None)
    mode = spec.pop("stock_mode", "earnings")
    t0 = time.time()
    try:
        warm = None
        if chain:      # homotopy: solve the easier case first and start from it
            for p in chain:
                warm, _, _ = E.counterfactual(**{**spec, "prod": p}, warm=warm, stock_mode=mode)
        cf, base, info = E.counterfactual(**spec, warm=warm, stock_mode=mode)
        e = E.effects(cf, base)
        ok = bool(np.isfinite(e.values).all()) and info.get("stock_converged", True)
        return dict(name=name, spec=spec, ok=ok, secs=round(time.time() - t0, 1), info=info, eff=E.pack(e))
    except Exception as ex:
        return dict(name=name, spec=spec, ok=False, secs=round(time.time() - t0, 1), error=repr(ex)[:400])


def run_extend(spec):
    """Backward-looking runs with effects through 2028Q4; the stock-wealth target (the gain's share of market
    value, held at its latest value after 2026Q4) is fitted over the whole window, so the gain is held."""
    path = "grows" if spec["grows"] else "build"
    t0 = time.time()
    cf, base, info = E.counterfactual(exp="var", target=spec["target"], stock=spec["stock"], path=path, fit=EXT_IDX,
                                      stock_mode=spec.get("stock_mode", "earnings"))
    e = E.effects(cf, base, idx=EXT_IDX)
    return {"name": spec["name"], "ok": bool(np.isfinite(e.values).all()) and info.get("stock_converged", True), "info": info, "secs": round(time.time() - t0, 1),
            "eff": E.pack(e), "dc_share": [round(float(x), 4) for x in E.PATHS[path]("build").reindex(EXT_IDX).values]}


# ------------------------------------------------------------------ expectations that switch on in 2026
def _solve_from(f, start, end, fr):
    with redirect_stdout(io.StringIO()):
        try:
            return f.solve(start, end, fr, {"maxiter": 60})
        except Exception:
            return f.solve(start, end, fr, {"newton": "trust", "maxiter": 60})


def _news_stage2(cfv, prod, warm=None, tol=5e-4, maxit=8, stock_mode="earnings", stock=True, own=None):
    """From 2026Q1, forward-looking, starting from the backward-looking without-world `cfv` through 2025. With
    stock=False, a single solve with no stock gain to take out (from A's world, this is the world `own` that the
    run with the stock gain scales: its stock-wealth target is own's wealth times 1 - f, engine.stock_base)."""
    exog = tuple(["hmfpt"] + E.stock_exog(True, stock_mode))
    f, wa, end = E.setup("mcap", "inertial", tuple(sorted(exog)), True)
    fr = wa.copy()
    cols = [c for c in cfv.columns if c in fr.columns]
    fr.loc[HIST, cols] = cfv.loc[HIST, cols].values          # the backward-looking without-world through 2025
    q = pd.period_range(T1, end, freq="Q")
    s = E.shock_build("build").loc[q].values / 100.0
    mshare = E.import_share_series(0.75)[0]
    ngdp = wa.loc[q, "xgdpn"].values
    fr.loc[q, "edc"] = -s * ngdp / (0.01 * wa.loc[q, "pbfir"].values * wa.loc[q, "pxp"].values)
    fr.loc[q, "emdc"] = -(mshare.loc[q].values / 100.0) * ngdp / (0.01 * wa.loc[q, "pmo"].values)
    if prod:
        q2 = pd.period_range("2027Q1", end, freq="Q")
        fr.loc[q2, "hmfpt"] = wa.loc[q2, "hmfpt"].values - prod
    endo = [v for v in f.endo_names if v in fr.columns and v not in exog]
    if warm is not None:
        fr.loc[q, endo] = warm.loc[q, endo].values
    if not stock:
        return _solve_from(f, T1, end, fr), wa, []
    # stock gain: hit the without-world stock-wealth target for 2026Q1-2026Q4, the instrument's gap held after
    fcut = E.stock_cut().loc[q]
    if own is None and stock_mode != "premium":
        raise ValueError("the earnings construction needs the run's own world without the stock gain (own=)")
    target = np.log(E.stock_base(own, wa, q, stock_mode) * (1 - fcut.values))
    n4 = 4
    col = E.STOCK_INSTRUMENT[stock_mode]
    if stock_mode == "premium":
        x = cfv.loc[T1 - 1, "reqp"] - wa.loc[T1 - 1, "reqp"]  # start from the 2025Q4 premium gap
        xs = np.full(len(q), float(x))
        step = E._premium_step
    else:
        # start from the 2025Q4 shift in expected dividend growth: in the backward-looking stage it equals the add
        # factor's gap; here a flat add factor da moves zdivgr in 2026Q1 by da * (1 + b + ... + b^(n-1))
        d0 = float(cfv.loc[T1 - 1, "zdivgr_aerr"] - E.setup("var", "inertial", (), False)[1].loc[T1 - 1, "zdivgr_aerr"])
        b = float(f.constants["y_zdivgr_2"])
        xs = np.full(len(q), d0 * (1.0 - b) / (1.0 - b ** len(q)))
        step = E._earnings_step(f, "mcap", len(q), n4)
    fr.loc[q, col] = wa.loc[q, col].values + xs
    cf = _solve_from(f, T1, end, fr)
    hist = []
    for it in range(maxit):
        gap = target - np.log(cf.loc[q, "wpsn"].values)
        err = float(np.max(np.abs(gap[:n4])))
        hist.append(round(err, 5))
        if err < tol:
            break
        xs[:n4] = xs[:n4] + step(gap[:n4])
        xs[n4:] = xs[n4 - 1]
        fr.loc[q, col] = wa.loc[q, col].values + xs
        fr.loc[q, endo] = cf.loc[q, endo].values
        cf = _solve_from(f, T1, end, fr)
    else:                                      # iteration limit reached: measure the last solve too
        gap = target - np.log(cf.loc[q, "wpsn"].values)
        err = float(np.max(np.abs(gap[:n4])))
        hist.append(round(err, 5))
    if err >= tol:                             # the unrounded gap: one just under the tolerance rounds up to it
        raise RuntimeError(f"stock-wealth target not reached (max gap {err:.6f}, tolerance {tol})")
    return cf, wa, hist


class _Log(list):
    def append(self, line):                    # print as we go (from the worker process) and keep for the summary
        print(f"  news2026  {line}", flush=True)
        super().append(line)


def run_news2026(spec=None):
    t0 = time.time()
    out, log = {}, _Log()
    mode = (spec or {}).get("stock_mode", "earnings")
    cfv, _, _ = E.counterfactual(exp="var", target=0.75, stock=True, stock_mode=mode)           # = B_s75
    _, basev, _ = E.setup("var", "inertial", tuple(E.stock_exog(True, mode)), False)
    e1 = E.effects(cfv, basev, idx=HIST)

    def eff(cf, base):
        e2 = E.effects(cf, base, idx=pd.period_range(T1, "2028Q4", freq="Q"))
        e = pd.concat([e1, e2])
        return {"index": [str(x) for x in e.index], "eff": E.pack(e)}
    # each run's own world without the stock gain: the same switch in 2026 from A's world, with the same belief
    own = {}
    if mode != "premium":                      # (the premium construction scales the baseline, as the earlier drafts did)
        cfa, _, _ = E.counterfactual(exp="var", target=0.75, stock=False, stock_mode=mode)       # = A_s75
        w = None
        for p in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5):
            try:
                w, _, _ = _news_stage2(cfa, p, warm=w, stock_mode=mode, stock=False)
            except Exception as ex:
                log.append(f"without the stock gain, productivity {p}: did not solve ({str(ex)[:120]})")
                break
            own[p] = w
        log.append(f"worlds without the stock gain: beliefs {sorted(own)} ({time.time() - t0:.0f} s)")
    cf0, base, h0 = _news_stage2(cfv, 0.0, stock_mode=mode, own=own.get(0.0))
    out["news_noprod"] = eff(cf0, base)
    log.append(f"no productivity belief: stock iterations {h0} ({time.time() - t0:.0f} s)")
    warm = cf0
    # a 0.5 belief solves with the earnings construction; with the premium one it does not, so it is attempted only
    # with --try-unsolved (it takes a long time to fail)
    beliefs = (0.1, 0.2, 0.3, 0.4, 0.5) if ((spec or {}).get("try_unsolved") or mode != "premium") else (0.1, 0.2, 0.3, 0.4)
    for p in beliefs:
        try:
            if mode != "premium" and p not in own:
                raise RuntimeError(f"its world without the stock gain did not solve at productivity {p}")
            cfp, base, hp = _news_stage2(cfv, p, warm=warm, stock_mode=mode, own=own.get(p))
        except Exception as ex:
            log.append(f"productivity {p}: did not solve ({str(ex)[:120]}) ({time.time() - t0:.0f} s)")
            out["_did_not_solve"] = {"prod": p, "error": str(ex)[:400]}
            break
        warm = cfp
        out[f"news_prod_{p}"] = eff(cfp, base)
        log.append(f"productivity {p}: stock iterations {hp} ({time.time() - t0:.0f} s)")
    if 0.5 not in beliefs:
        out["_not_attempted"] = {"prod": 0.5, "why": "does not solve (trust-region solver, 60 iterations); run with --try-unsolved"}
    out["_log"] = list(log)
    if mode != "premium":                      # (the premium version writes exactly what it always wrote)
        out["_stock_mode"] = mode
    return {"name": "news2026", "ok": True, "secs": round(time.time() - t0, 1), "result": out}


def run_task(spec):
    return {"post": run_post, "extend": run_extend, "news2026": run_news2026, "reversal": R.run_reversal}[spec["kind"]](spec)


def _order(t):           # slowest first, so three workers finish together
    if t["kind"] == "news2026":
        return 0
    if t["kind"] == "post" and t.get("exp") == "mcap":
        return 1 if t.get("prod") else 2
    return 3


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--all-shares", action="store_true")
    ap.add_argument("--try-unsolved", action="store_true", help="also attempt the runs known not to solve (slow to fail)")
    ap.add_argument("--stock-mode", choices=E.STOCK_MODES, default=E.STOCK_MODES[0],
                    help="how the stock gain is removed: lower expected earnings (default) or a higher equity premium (earlier drafts)")
    a = ap.parse_args(argv)
    try:
        if os.nice(0) < 10:
            os.nice(10 - os.nice(0))
    except (OSError, AttributeError):         # AttributeError: no os.nice on Windows
        pass
    paths.ensure()
    (paths.OUT_RESULTS / "reversal_runs.json").unlink(missing_ok=True)   # written whole when its task finishes
    T = sorted(post_tasks(a.all_shares, a.try_unsolved, a.stock_mode), key=_order)
    res = {"post": {}, "extend": {}, "news": {}, "reversal": None}
    t0 = time.time()
    print(f"runs: {len(T)} tasks on {a.workers} worker processes (the forward-looking ones take minutes each); "
          f"stock gain removed as {'higher expected earnings' if a.stock_mode == 'earnings' else 'a higher equity premium'}", flush=True)
    tag = {} if a.stock_mode == "premium" else {"stock_mode": a.stock_mode}   # premium: exactly the files it always wrote

    def save():
        (paths.OUT_RESULTS / "post_runs.json").write_text(json.dumps({"index": [str(x) for x in E.SHOW], "runs": res["post"], **tag}))
        (paths.OUT_RESULTS / "post_extend.json").write_text(json.dumps({"index": [str(q) for q in EXT_IDX], "runs": res["extend"], **tag}))
        (paths.OUT_RESULTS / "news2026.json").write_text(json.dumps(res["news"]))
        if res["reversal"] is not None:
            R.write(res["reversal"])
    # a fresh process per task: a forward-looking model setup holds about 4 GB, and a worker that kept several would
    # hold several times that
    with Pool(max(1, min(a.workers, len(T))), maxtasksperchild=1) as p:
        for r in p.imap_unordered(run_task, T):
            if r["name"] == "news2026":
                res["news"] = r["result"]
                print(f"  news2026  done in {r['secs']:.0f}s", flush=True)
            elif r["name"] == "reversal":
                res["reversal"] = r["result"]
                print(f"  reversal  {len(r['result']['runs'])} scenarios ok={r['ok']} {r['secs']:6.1f}s", flush=True)
            elif "dc_share" in r:
                res["extend"][r["name"]] = r
                print(f"  extend    {r['name']:12s} ok={r['ok']} {r['secs']:6.1f}s", flush=True)
            else:
                res["post"][r["name"]] = r
                print(f"  post      {r['name']:12s} ok={r['ok']} {r['secs']:6.1f}s {r.get('info', {}).get('stock_iterations', '')} "
                      f"{r.get('error', '')[:120]}", flush=True)
            save()
    print(f"runs: done in {(time.time() - t0) / 60:.1f} minutes", flush=True)


if __name__ == "__main__":
    main()
