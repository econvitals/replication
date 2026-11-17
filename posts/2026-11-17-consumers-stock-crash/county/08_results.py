"""All estimates for the write-up: replication, extension, sub-periods, COVID cuts, asymmetry, rolling windows, robustness.

    python 08_results.py <cns dir>        (paperwright venv; needs out/panel.parquet and out/county_wealth_q.parquet)

Coefficients are reported as in the paper: basis points of the outcome per shock equal to 1 percent of annual labor
income (100 x the regression coefficient). For nontradable payroll at horizon 7 this number is also the implied
household MPC out of stock wealth in cents per dollar per year, because the paper's calibration sets the labor share
(2/3) times the local multiplier (1.5) to one.
Writes out/results_<tag>.csv (one row per coefficient). Sections can run in parallel:
    python 08_results.py <cns dir> table1,periods,interacted,asymmetry A ; ... ; then concatenate into out/results.csv.
With no section argument, runs everything, writes out/results.csv and prints a summary.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); import common as C

D = Path(sys.argv[1]); OUT = D / "out"
P = C.load(OUT); cw = pd.read_parquet(OUT / "county_wealth_q.parquet")
rows = []
def rec(group, spec, dep, h, m, d, extra_tags=None):
    t = m.tidy(); V = pd.DataFrame(m._vcov, index=m._coefnames, columns=m._coefnames)
    mains = [k for k in t.index if not (k.startswith("SR_l") or k.startswith("S_") or k.startswith("bartik"))]
    for k in mains:
        rows.append(dict(group=group, spec=spec, dep=dep, h=h, term=k, b=100 * t.loc[k, "Estimate"], se=100 * t.loc[k, "Std. Error"],
                         n=len(d), counties=d.fips.nunique(), periods=d.q.nunique(), first=d.q.min(), last=d.q.max(), **(extra_tags or {})))
    if len(mains) == 2:
        a, b = mains; diff = t.loc[a, "Estimate"] - t.loc[b, "Estimate"]
        sd = np.sqrt(V.loc[a, a] + V.loc[b, b] - 2 * V.loc[a, b])
        rows.append(dict(group=group, spec=spec, dep=dep, h=h, term=f"{a}-{b}", b=100 * diff, se=100 * sd, n=len(d),
                         counties=d.fips.nunique(), periods=d.q.nunique(), first=d.q.min(), last=d.q.max(), **(extra_tags or {})))
    return rows[-1]

def run(group, spec, x, dep, h=7, main="SR", **kw):
    m, d = C.fit(x, dep, h, main=main, **kw); return rec(group, spec, dep, h, m, d)

COVID = ("2020Q1", "2022Q4")
DEPS = ["pay_nt", "pay_all", "emp_all", "emp_nt"]
ALL6 = ["emp_all", "pay_all", "emp_nt", "pay_nt", "emp_tr", "pay_tr"]

SECT = sys.argv[2].split(",") if len(sys.argv) > 2 else ['table1', 'periods', 'interacted', 'asymmetry', 'paths', 'rolling', 'robust']
TAG = sys.argv[3] if len(sys.argv) > 3 else "all"

# ---- 1. replication and extension, horizon 7, all outcomes
if "table1" in SECT:
    for dep in ALL6:
        run("table1", "paper sample 1992Q1-2014Q4", C.sample(P, "1992Q1", "2014Q4"), dep)
        run("table1", "pre-COVID 1992Q1-2018Q1", C.sample(P, "1992Q1", "2018Q1"), dep)
        run("table1", "everything 1992Q1-2024Q2", C.sample(P, "1992Q1", "2024Q2"), dep)
        run("table1", "everything, shock quarters 2020-22 dropped", C.sample(P, "1992Q1", "2024Q2").query("not (q >= '2020Q1' and q <= '2022Q4')"), dep)
        run("table1", "everything, windows touching 2020-22 dropped", C.sample(P, "1992Q1", "2024Q2", drop=(7, *COVID)), dep)
        run("table1", "everything, windows touching 2020-21 dropped", C.sample(P, "1992Q1", "2024Q2", drop=(7, "2020Q1", "2021Q4")), dep)
    print("table1 done", flush=True)

# ---- 2. separate regressions by sub-period
if "periods" in SECT:
    PERIODS = [("halves", "1992Q1-2004Q4", "1992Q1", "2004Q4"), ("halves", "2005Q1-2018Q1", "2005Q1", "2018Q1"),
               ("paper split", "1992Q1-2003Q1", "1992Q1", "2003Q1"), ("paper split", "2003Q2-2014Q4", "2003Q2", "2014Q4"),
               ("paper split", "2003Q2-2018Q1", "2003Q2", "2018Q1"),
               ("thirds", "1992Q1-2000Q4", "1992Q1", "2000Q4"), ("thirds", "2001Q1-2009Q4", "2001Q1", "2009Q4"),
               ("thirds", "2010Q1-2018Q1", "2010Q1", "2018Q1"),
               ("recent", "2010Q1-2024Q2, windows touching 2020-22 dropped", "2010Q1", "2024Q2"),
               ("recent", "2015Q1-2024Q2, windows touching 2020-22 dropped", "2015Q1", "2024Q2")]
    for fam, name, a, b in PERIODS:
        x = C.sample(P, a, b, drop=(7, *COVID))
        for dep in DEPS:
            run("periods:" + fam, name, x, dep)
    print("periods done", flush=True)

# ---- 3. sub-periods inside one regression (the paper's Figure 5 approach: other coefficients common)
if "interacted" in SECT:
    def interact(x, cuts, labels):
        x = x.copy(); names = []
        for (a, b), lab in zip(cuts, labels):
            c = f"SR_{lab}"; x[c] = x.SR * ((x.q >= a) & (x.q <= b)); names.append(c)
        return x, names
    specs = [("halves", "1992Q1", "2018Q1", [("1992Q1", "2004Q4"), ("2005Q1", "2018Q1")], ["p1992", "p2005"]),
             ("paper split", "1992Q1", "2014Q4", [("1992Q1", "2003Q1"), ("2003Q2", "2014Q4")], ["to2003", "from2003"]),
             ("thirds", "1992Q1", "2018Q1", [("1992Q1", "2000Q4"), ("2001Q1", "2009Q4"), ("2010Q1", "2018Q1")], ["p1992", "p2001", "p2010"]),
             ("pre/post COVID", "1992Q1", "2024Q2", [("1992Q1", "2018Q1"), ("2023Q2", "2024Q2")], ["pre", "post"])]
    for name, a, b, cuts, labs in specs:
        x = C.sample(P, a, b, drop=(7, *COVID)); x, names = interact(x, cuts, labs)
        for dep in ["pay_nt", "pay_all", "emp_all"]:
            run("interacted", name, x, dep, main=names)
    print("interacted done", flush=True)

# ---- 4. asymmetry: positive versus negative returns
if "asymmetry" in SECT:
    def asym(x):
        x = x.copy(); x["SR_pos"] = x.SR * (x.R > 0); x["SR_neg"] = x.SR * (x.R <= 0); return x
    for name, a, b, drop in [("paper sample 1992Q1-2014Q4", "1992Q1", "2014Q4", None),
                             ("pre-COVID 1992Q1-2018Q1", "1992Q1", "2018Q1", None),
                             ("1992Q1-2004Q4", "1992Q1", "2004Q4", None), ("2005Q1-2018Q1", "2005Q1", "2018Q1", None),
                             ("everything, windows touching 2020-22 dropped", "1992Q1", "2024Q2", (7, *COVID)),
                             ("everything 1992Q1-2024Q2", "1992Q1", "2024Q2", None)]:
        x = asym(C.sample(P, a, b, drop=drop))
        for dep in ["pay_nt", "pay_all", "emp_all"]:
            r = run("asymmetry", name, x, dep, main=["SR_pos", "SR_neg"])
        nq = x.drop_duplicates("q"); rows[-1]["neg_quarters"] = int((nq.R <= 0).sum()); rows[-1]["all_quarters"] = len(nq)
    print("asymmetry done", flush=True)

# ---- 5. dynamic paths (horizons -4..10)
if "paths" in SECT:
    keep = [c for c in P.columns if not any(c.startswith(f"d{v}_") for v in ["emp_all", "emp_nt", "emp_tr", "pay_tr", "emp_nt0", "pay_nt0", "emp_ret", "pay_ret", "emp_food", "pay_food"])]
    P = P[keep]                                              # this section needs only two outcomes; saves memory
    for name, a, b, drop in [("1992Q1-2004Q4", "1992Q1", "2004Q4", None), ("2005Q1-2018Q1", "2005Q1", "2018Q1", None)]:
        for h in [-4, -3, -2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            x = C.sample(P, a, b, drop=(h, *COVID))              # no window reaches 2020
            for dep in ["pay_nt", "pay_all"]:
                run("path", name, x, dep, h=h)
    print("paths done", flush=True)

# ---- 6. rolling 12-year windows (48 quarters), horizon 7, stepping a year
if "rolling" in SECT:
    ends = [f"{y}Q4" for y in range(2003, 2018)] + ["2018Q1"]
    for e in ends:
        ep = pd.Period(e, "Q"); s = str(ep - 47)
        x = C.sample(P, s, e)
        for dep in ["pay_nt", "pay_all"]:
            run("rolling", f"{s}-{e}", x, dep)
    print("rolling done", flush=True)

# ---- 7. robustness of the pre-COVID estimate and of the two halves
if "robust" in SECT:
    variants = {"baseline": dict(), "taxable stock wealth only": dict(Scol="S_tax"), "end-of-quarter total return": dict(Rcol="tot"),
                "wealth not revalued within the year": dict(Scol="S_annual")}
    for vname, kw in variants.items():
        Pv = C.swap(P, cw, **kw) if kw else P
        for name, a, b in [("pre-COVID 1992Q1-2018Q1", "1992Q1", "2018Q1"), ("1992Q1-2004Q4", "1992Q1", "2004Q4"), ("2005Q1-2018Q1", "2005Q1", "2018Q1"),
                           ("paper sample 1992Q1-2014Q4", "1992Q1", "2014Q4")]:
            x = C.sample(Pv, a, b)
            for dep in ["pay_nt", "pay_all"]:
                m, d = C.fit(x, dep, 7); rec("robust", name, dep, 7, m, d, dict(variant=vname))
    for name, a, b in [("pre-COVID 1992Q1-2018Q1", "1992Q1", "2018Q1"), ("1992Q1-2004Q4", "1992Q1", "2004Q4"), ("2005Q1-2018Q1", "2005Q1", "2018Q1")]:
        for vname, fn in [("no aggregate controls or Bartik", lambda x, dep: C.fit(x, dep, 7, controls=False, bartik=False)),
                          ("all counties (late filers and large-firm counties kept)", None),
                          ("Florida dropped", None), ("horizon 4", lambda x, dep: C.fit(x, dep, 4)), ("horizon 10", lambda x, dep: C.fit(x, dep, 10))]:
            for dep in ["pay_nt", "pay_all"]:
                if vname.startswith("all counties"):
                    x = C.sample(P, a, b, baseline=False); m, d = C.fit(x, dep, 7); h = 7
                elif vname == "Florida dropped":
                    x = C.sample(P, a, b); x = x[x.state != "12"]; m, d = C.fit(x, dep, 7); h = 7
                else:
                    h = 4 if vname == "horizon 4" else (10 if vname == "horizon 10" else 7)
                    x = C.sample(P, a, b, drop=(h, *COVID))       # same shock quarters; no window reaches 2020
                    m, d = fn(x, dep)
                rec("robust", name, dep, h, m, d, dict(variant=vname))
    print("robust done", flush=True)

R = pd.DataFrame(rows); R.to_csv(OUT / f"results_{TAG}.csv", index=False)
if TAG != "all":
    sys.exit(0)
R.to_csv(OUT / "results.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
show = R[R.group.isin(["table1", "periods:halves", "periods:thirds", "periods:paper split", "periods:recent", "interacted", "asymmetry"]) & R.dep.isin(["pay_nt", "pay_all", "emp_all"])]
print(show[["group", "spec", "dep", "term", "b", "se", "periods", "first", "last"]].round(2).to_string())
print(R[R.group == "robust"][["spec", "variant", "dep", "h", "b", "se", "periods"]].round(2).to_string())
print(R[R.group == "rolling"][["spec", "dep", "b", "se"]].round(2).to_string())
