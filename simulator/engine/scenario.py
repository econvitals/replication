#!/usr/bin/env python3
"""scenario.py — solve ONE FRB/US scenario live and print it as JSON. The library's model, one run at a time.

    python engine/scenario.py --shock tariff --size 2.5 --fed balanced --duration perm \
        [--exp var|mce] [--elb no|yes] [--fiscal fixed|debt]
    python engine/scenario.py --selftest

Exists for callers that need a run the stored library does not hold — a size other than ±1/±2 (a 25% tariff is
size 2.5), or a combination the page never pre-solved. Its callers read the stored library first and come here only for a run the
library lacks; the page never calls it. It runs build.py's own `config_task`, so a live run and a stored run of the
same scenario are the same computation (checked by --selftest against the library).

Output on stdout, one JSON object: {"ok", "source": "live", "spec", "vars": [ids], "horizon": 40, "series":
{var: [41 deviations from baseline]}, "failed": null | "reason", "seconds", "vintage"}. Exit 0 when the run solved,
2 when the scenario is not a valid one (the reason is in "error"), 3 when the model did not solve it.

Timing on an eight-core Apple M1 (2026-11-08, with other model runs using five of its cores): about 7 seconds
backward-looking, about a minute forward-looking (200 quarters). Niced, as CPU-heavy work should be,
though one run is short.
"""
import argparse, io, json, os, sys, time
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def validate(shock, size, fed, dur, exp, elb, fiscal, B):
    """The reason this scenario is not one the engine builds, or None. Same rules as build.py's library loop."""
    if shock not in B.SHOCKS:
        return f"unknown shock {shock!r}; one of {', '.join(B.SHOCKS)}"
    sp = B.SHOCKS[shock]
    if dur not in sp["durs"]:
        return f"duration {dur!r} is not offered for {shock}; one of {', '.join(sp['durs'])}"
    if fed not in sp["fed_options"]:
        return f"Fed response {fed!r} is not offered for {shock}; one of {', '.join(sp['fed_options'])}"
    if exp not in B.EXPS or elb not in B.ELBS or fiscal not in B.FISCALS:
        return f"exp/elb/fiscal must be one of {B.EXPS} / {B.ELBS} / {B.FISCALS}"
    if (exp, elb, fiscal) in B.DROPPED:
        return "forward-looking + at the lower bound + the Board's debt rule does not solve (build.py DROPPED); use --fiscal fixed"
    if shock == "fed" and exp == "mce" and dur == "perm":
        return ("a permanent Fed peg under forward-looking expectations has no unique answer (indeterminate; "
                "the sign flips with the financing setting) — backward-looking only")
    if not (-10 <= size <= 10) or size == 0:
        return f"size {size} is outside the engine's sane range (nonzero, within ±10 units)"
    return None


def solve_one(shock, size, fed, dur, exp="var", elb="no", fiscal="fixed"):
    import build as B
    why = validate(shock, size, fed, dur, exp, elb, fiscal, B)
    spec = dict(shock=shock, size=size, fed=fed, duration=dur, exp=exp, elb=elb, fiscal=fiscal)
    if why:
        return 2, {"ok": False, "source": "live", "spec": spec, "error": why}
    meta = json.loads((B.OUT / "meta.json").read_text())
    calib = meta.get("calibration") or {}
    if "reqp_per_10pct" not in calib:
        return 2, {"ok": False, "source": "live", "spec": spec, "error": "meta.json carries no stocks calibration"}
    if shock == "stocks_earn" and "zdivgr_per_10pct" not in calib:
        return 2, {"ok": False, "source": "live", "spec": spec, "error": "meta.json carries no expected-earnings calibration (rebuild with build.py)"}
    # holds run under the inertial rule after the hold ends (build.py: rule == "inertial" and f in HOLDS)
    rule = fed if fed in B.RULE_IDS else "inertial"
    t0 = time.time()
    with redirect_stdout(io.StringIO()):          # pyfrbus prints solver chatter; stdout carries only our JSON
        r = B.config_task(dict(shock=shock, rule=rule, exp=exp, elb=elb, fiscal=fiscal, sizes=[size],
                               durs=[dur], feds=[fed], calib=calib, only=[(size, fed, dur)]))
    key = B.run_key(size, fed, dur, exp, elb, fiscal)
    out = {"ok": key in r["runs"], "source": "live", "spec": spec, "vars": B.VAR_IDS, "horizon": B.H,
           "series": r["runs"].get(key, {}), "failed": None, "seconds": round(time.time() - t0, 1),
           "model": meta.get("model"), "vintage": meta.get("vintage", {}), "calibration": calib}
    if not out["ok"]:
        out["failed"] = "; ".join(f"{k}: {v}" for k, v in r["failed"]) or "the model did not return the run"
        return 3, out
    return 0, out


def selftest():
    """A live run must reproduce the stored library run of the same scenario."""
    import build as B
    lib = json.loads((B.OUT / "runs" / "tariff_var_no_debt.json").read_text())["runs"]["1|balanced|q8"]
    rc, out = solve_one("tariff", 1, "balanced", "q8", "var", "no", "debt")
    assert rc == 0, out
    for v in ("xgdp", "lur", "picx4", "rff", "surplus"):
        a, b = out["series"][v], lib[v]
        worst = max(abs((x or 0) - (y or 0)) for x, y in zip(a, b))
        assert worst < 0.002, (v, worst)
    # the expected-earnings stock shock (2026-11-08): engine -1 = a 10% rise, exact on impact backward-looking
    lib = json.loads((B.OUT / "runs" / "stocks_earn_var_no_fixed.json").read_text())["runs"]["-1|balanced|q4"]
    rc, out = solve_one("stocks_earn", -1, "balanced", "q4", "var", "no", "fixed")
    assert rc == 0, out
    assert abs(out["series"]["wpsn"][0] - 10.0) < 0.01, out["series"]["wpsn"][0]
    for v in ("xgdp", "ecnia", "ebfi", "wpsn"):
        worst = max(abs((x or 0) - (y or 0)) for x, y in zip(out["series"][v], lib[v]))
        assert worst < 0.002, (v, worst)
    rc, out = solve_one("fed", 1, "balanced", "perm", "mce", "no", "debt")
    assert rc == 2 and "indeterminate" in out["error"], out
    rc, out = solve_one("tariff", 1, "hold4", "q99", "var", "no", "debt")
    assert rc == 2 and "duration" in out["error"], out
    print("scenario.py selftest: live run matches the stored library; invalid scenarios refused")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shock"); ap.add_argument("--size", type=float, default=1.0)
    ap.add_argument("--fed", default="balanced"); ap.add_argument("--duration", default="perm")
    ap.add_argument("--exp", default="var"); ap.add_argument("--elb", default="no"); ap.add_argument("--fiscal", default="fixed")   # the page's default financing (taxes fixed)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    try:
        os.nice(10)
    except OSError:
        pass
    if a.selftest:
        selftest()
        return 0
    if not a.shock:
        ap.error("--shock is required")
    size = int(a.size) if float(a.size).is_integer() else a.size
    rc, out = solve_one(a.shock, size, a.fed, a.duration, a.exp, a.elb, a.fiscal)
    print(json.dumps(out, separators=(",", ":")))
    return rc


if __name__ == "__main__":
    sys.exit(main())
