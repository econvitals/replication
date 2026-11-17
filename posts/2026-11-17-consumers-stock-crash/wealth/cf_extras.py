"""Extra computations for the technical note (2026-11-16): rolling-origin out-of-sample benchmark,
expanding-window path, break tests inside the pre-2020 data. chartbook venv, run beside code/ and output/.
Writes output/r9_oos_rolling_origin.csv, output/r9_expanding_path.csv, output/r9_extras.json."""
import sys, json
sys.path.insert(0, "wealth")
from common import *
import warnings; warnings.filterwarnings("ignore")
OUT = Path("output")
d = load(Path("output")); x = add_basics(d)
END = str(x["cy"].last_valid_index())
CORE = WEALTH3 + CTL
Y, C = d["dpi"], d["pce"]
E = {}

def fit(a, b, extra=None):
    X = x[CORE + list(extra or [])].copy()
    if b >= "2020Q1":
        X[DUMS] = x[DUMS]
    return ols(x["cy"].loc[a:b], X.loc[a:b], lags=8)

def apply_cf(m, yr):
    cols = ["const"] + CORE
    X = sm.add_constant(x[CORE], has_constant="add")
    pred = X[cols] @ m.params[cols]
    W = pd.period_range(f"{yr}Q1", f"{yr}Q4", freq="Q")
    anc = (x["cy"] - pred).loc[W].mean()
    Xs = X.copy(); Xs["Sy"] = x.loc[W, "Sy"].mean()
    return (pred + anc) * Y, (Xs[cols] @ m.params[cols] + anc) * Y, float(anc)

# (a) rolling-origin benchmark: estimate 1955..A, anchor to year A, gap 27 quarters after A's Q4 (as 2019Q4 -> 2026Q3)
rows = []
for A in range(1970, 2020):
    m = fit("1955Q1", f"{A}Q4")
    cf, ns, anc = apply_cf(m, A)
    t = pd.Period(f"{A}Q4", "Q") + 27
    if t > pd.Period(END, "Q"):
        t = pd.Period(END, "Q")
    g = 100 * (cf / C - 1)
    path = g.loc[pd.Period(f"{A+1}Q1", "Q"):t]
    rows.append(dict(anchor=A, target=str(t), S=100 * m.params["Sy"], gap_pct=float(g[t]), max_abs=float(path.abs().max()),
                     stock_part_pct=float(100 * (cf[t] - ns[t]) / C[t]), dSy=float(x.loc[t, "Sy"] - x.loc[pd.period_range(f"{A}Q1", f"{A}Q4", freq="Q"), "Sy"].mean()),
                     path=";".join(f"{v:.3f}" for v in g.loc[pd.Period(f"{A}Q4", "Q"):t].values)))
ro = pd.DataFrame(rows); ro.to_csv(OUT / "r9_oos_rolling_origin.csv", index=False)
full = ro[ro.anchor <= 2012]           # windows that end before the pandemic
E["ro_n"] = int(len(full))
E["ro_abs_median"] = float(full.gap_pct.abs().median()); E["ro_abs_p75"] = float(full.gap_pct.abs().quantile(.75))
E["ro_abs_p90"] = float(full.gap_pct.abs().quantile(.9)); E["ro_abs_max"] = float(full.gap_pct.abs().max())
E["ro_mean"] = float(full.gap_pct.mean()); E["ro_sd"] = float(full.gap_pct.std())
E["ro_share_above_2p3"] = float((full.gap_pct.abs() >= 2.279).mean())
E["ro_share_over_2p3"] = float((full.gap_pct >= 2.279).mean())
E["ro_corr_gap_dSy"] = float(np.corrcoef(full.gap_pct, full.dSy)[0, 1])
b_ = np.polyfit(full.dSy, full.gap_pct, 1); E["ro_slope_gap_on_dSy"] = float(b_[0]); E["ro_int"] = float(b_[1])
E["ro_2019"] = ro[ro.anchor == 2019].drop(columns="path").to_dict(orient="records")[0]
print(ro.drop(columns="path").round(2).to_string())
print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in E.items() if k.startswith("ro_") and k != "ro_2019"})

# (b) expanding window by quarter, 1980Q1..END
ex = []
for b in pd.period_range("1980Q1", END, freq="Q"):
    m = fit("1955Q1", str(b)); ex.append(dict(end=str(b), Sy=100 * m.params["Sy"], Sy_se=100 * m.bse["Sy"]))
pd.DataFrame(ex).to_csv(OUT / "r9_expanding_path.csv", index=False)

# (c) breaks inside the pre-2020 data: all coefficients allowed to change at a given date, 1955-2019
def chow(tau, end="2019Q4", start="1955Q1"):
    post = pd.Series((x.index >= pd.Period(tau, "Q")).astype(float), index=x.index)
    base = x[CORE]
    X = pd.concat([base, base.mul(post, axis=0).add_suffix("_post"), post.rename("post")], axis=1)
    if end >= "2020Q1":
        X = pd.concat([X, x[DUMS]], axis=1)
    m = ols(x["cy"].loc[start:end], X.loc[start:end], lags=8)
    return dict(tau=tau, end=end, before=float(100 * m.params["Sy"]), after=float(100 * (m.params["Sy"] + m.params["Sy_post"])),
                shift=float(100 * m.params["Sy_post"]), shift_se=float(100 * m.bse["Sy_post"]), wald=float((m.params["Sy_post"] / m.bse["Sy_post"]) ** 2),
                n_after=int(((x.index >= pd.Period(tau, "Q")) & (x.index <= pd.Period(end, "Q"))).sum()))
E["chow"] = [chow(t, e) for t in ("2008Q2", "2010Q1", "2013Q4") for e in ("2019Q4", END)]
for r in E["chow"]:
    print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
# regressions on the post-break stretch alone, through 2019
for a in ("2008Q2", "2010Q1", "2013Q4"):
    m = fit(a, "2019Q4"); E[f"sub_{a}_2019"] = dict(S=float(100 * m.params["Sy"]), se=float(100 * m.bse["Sy"]), n=int(m.nobs))
    print(a, "-2019", E[f"sub_{a}_2019"])
json.dump(E, open(OUT / "r9_extras.json", "w"), indent=1, default=float)

# (d) does the gap line up with the model's own stock contribution?
E["ro_corr_gap_stockpart"] = float(np.corrcoef(full.gap_pct, full.stock_part_pct)[0, 1])
b2 = np.polyfit(full.stock_part_pct, full.gap_pct, 1); E["ro_slope_gap_on_stockpart"] = float(b2[0])
big = full[full.stock_part_pct >= 0.8]; E["ro_big_stock_runs"] = big[["anchor", "target", "gap_pct", "stock_part_pct"]].to_dict(orient="records")
json.dump(E, open(OUT / "r9_extras.json", "w"), indent=1, default=float)
print("corr gap vs stock part", round(E["ro_corr_gap_stockpart"], 2), "slope", round(E["ro_slope_gap_on_stockpart"], 2))
print(big[["anchor", "target", "gap_pct", "stock_part_pct"]].round(2).to_string())
