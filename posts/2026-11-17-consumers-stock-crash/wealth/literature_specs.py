"""Published specifications re-estimated on current data and extended through 2026.

    python 07_literature.py <out dir>

  A. The log cointegrating regression of consumption on wealth and labor income (dynamic OLS):
     Ludvigson and Steindel (1999), 3 leads and lags, total spending; Lettau and Ludvigson (2001), 8 leads
     and lags, nondurables and services. Implied MPC = elasticity x the consumption-wealth ratio at the end
     of the sample (as Ludvigson and Steindel do).
  B. Carroll, Otsuka and Slacalek (2011): momentum in spending growth (chi, by instrumental variables),
     the next-quarter MPC and the eventual MPC = next-quarter / (chi (1 - chi)).
Writes q6_cointegration.csv, q6_recursive.csv, q6_cos.csv, q6_cos_rolling.csv and fig14.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *

OUT = Path(sys.argv[1])
d = load(OUT)
END = str(d["pce"].last_valid_index())

def dols(y, X, k, a, b, lags=8, dummies=None):
    Z = X.copy()
    for c in X.columns:
        dx = X[c].diff()
        for j in range(-k, k + 1):
            Z[f"d{c}_{j}"] = dx.shift(j)
    if dummies is not None:
        for q in dummies:
            Z[f"D{q}"] = (Z.index == q).astype(float)
    return ols(y.loc[a:b], Z.loc[a:b], lags=lags)

# ---- A. log cointegrating regression -------------------------------------------------------------
lw = np.log(d["r_nw"].shift(1))                 # start-of-quarter net worth, real per person
ly = np.log(d["r_labor_at"])                    # after-tax labor income (compensation + transfers - contributions)
specs = {"Ludvigson–Steindel (total spending, 3 leads and lags)": (np.log(d["r_pce"]), d["pce"], 3),
         "Lettau–Ludvigson (nondurables and services, 8 leads and lags)": (np.log(d["r_pce_nds"]), d["pce_nds"], 8)}
ratio_w = lambda cons, b: (cons / d["nw"].shift(1)).loc[pd.Period(b, "Q") - 3:b].mean()
rows = []
samples = [("1953Q1", "1997Q1"), ("1953Q1", "1967Q4"), ("1968Q1", "1982Q4"), ("1983Q1", "1997Q1"), ("1952Q4", "1998Q3"),
           ("1953Q1", "2007Q4"), ("1953Q1", "2019Q4"), ("1953Q1", END), ("1983Q1", "2019Q4"), ("1983Q1", END), ("1998Q1", END)]
for name, (lc, cons, k) in specs.items():
    for a, b in samples:
        dm = PANDEMIC if b >= "2020Q1" else None
        b_eff = str(pd.Period(b, "Q") - k) if b == END else b     # leads run off the end of the data
        m = dols(lc, pd.DataFrame({"w": lw, "y": ly}), k, a, b_eff, dummies=dm)
        scale = ratio_w(d["pce"], b_eff)     # express per dollar of TOTAL spending for both
        rows.append(dict(spec=name, start=a, end=b, end_used=b_eff, elasticity_w=m.params["w"], se_w=m.bse["w"], elasticity_y=m.params["y"],
                         mpc_cents=100 * m.params["w"] * scale, c_over_w=scale, n=int(m.nobs)))
coint = pd.DataFrame(rows)
coint.to_csv(OUT / "q6_cointegration.csv", index=False)
pd.set_option("display.width", 250)
print(coint.round(3).to_string())

# recursive: fixed start 1953Q1, sample end moving from 1975 to the present
rows = []
lc, cons, k = specs["Ludvigson–Steindel (total spending, 3 leads and lags)"]
ends = pd.period_range("1975Q4", pd.Period(END, "Q") - k, freq="Q")
for b in ends:
    dm = PANDEMIC if str(b) >= "2020Q1" else None
    m = dols(lc, pd.DataFrame({"w": lw, "y": ly}), k, "1953Q1", str(b), dummies=dm)
    rows.append(dict(end=str(b), elasticity_w=m.params["w"], se_w=m.bse["w"], mpc_cents=100 * m.params["w"] * ratio_w(d["pce"], str(b)),
                     mpc_se=100 * m.bse["w"] * ratio_w(d["pce"], str(b))))
rec = pd.DataFrame(rows)
rec.to_csv(OUT / "q6_recursive.csv", index=False)

# ---- B. Carroll, Otsuka and Slacalek ---------------------------------------------------------------
Cc = d["r_pce"]
dC = Cc.diff() / Cc.shift(5)
W = {"S": d["r_S"], "H": d["r_H"], "O": d["r_O"], "NW": d["r_nw"]}
W["N"] = d["r_nw"] - d["r_S"]            # nonstock (working-paper split)
W["F"] = d["r_nw"] - d["r_H"]            # financial = everything but housing (published split)
dW = {k: v.diff() / Cc.shift(4) for k, v in W.items()}            # dated t: (W_t - W_{t-1}) / C_{t-4}
MU = d["sent"]                             # stand-in for Michigan unemployment expectations
FF = d["ffr"].fillna(d["tb3m"])

def iv_chi(a, b, kinds, extra=True, skip=()):
    """dC_{t+1} = c + chi dC_t, instruments dated t-1. Returns chi, its HAC s.e. and the first-stage R2."""
    Z = pd.DataFrame({f"dW{k}": dW[k].shift(1) for k in kinds})
    if extra:
        Z["MU"] = MU.shift(1); Z["FF"] = FF.shift(1)
    df = pd.concat([dC.shift(-1).rename("y"), dC.rename("x"), Z], axis=1).loc[a:b].dropna()
    df = df[[t not in skip for t in df.index]]
    Zc = sm.add_constant(df[Z.columns])
    fs = sm.OLS(df["x"], Zc).fit()
    xhat = fs.fittedvalues
    X2 = sm.add_constant(pd.DataFrame({"x": xhat}))
    b2 = np.linalg.solve(X2.T @ X2, X2.T @ df["y"])
    resid = df["y"] - (b2[0] + b2[1] * df["x"])                    # residuals use the actual regressor
    # Newey-West (4 lags) covariance for two-stage least squares
    Xh = X2.values; u = resid.values; n = len(u)
    S = (Xh * u[:, None]).T @ (Xh * u[:, None])
    for L in range(1, 5):
        wgt = 1 - L / 5
        G = (Xh[L:] * u[L:, None]).T @ (Xh[:-L] * u[:-L, None])
        S += wgt * (G + G.T)
    XtXi = np.linalg.inv(Xh.T @ Xh)
    V = XtXi @ S @ XtXi
    return b2[1], np.sqrt(V[1, 1]), fs.rsquared_adj, len(df)

def cos_fit(a, b, kinds, skip=()):
    chi, chi_se, r2, n = iv_chi(a, b, kinds, skip=skip)
    X = pd.DataFrame(index=d.index)
    for k in kinds:
        num = sum((chi ** j) * W[k].diff().shift(j) for j in range(4))
        X[f"bar{k}"] = (num / Cc.shift(4)).shift(1)                 # weighted change in wealth through t-1, over C_{t-5}
    X["MU"] = MU.shift(1); X["FF"] = FF.shift(1)
    df = pd.concat([dC.rename("y"), X], axis=1).loc[a:b].dropna()
    df = df[[t not in skip for t in df.index]]
    m = sm.OLS(df["y"], sm.add_constant(df.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    out = dict(start=a, end=b, split="+".join(kinds), chi=chi, chi_se=chi_se, first_stage_r2=r2, n=n)
    for k in kinds:
        out[f"next_{k}"] = 100 * m.params[f"bar{k}"]
        out[f"next_se_{k}"] = 100 * m.bse[f"bar{k}"]
        out[f"eventual_{k}"] = 100 * m.params[f"bar{k}"] / (chi * (1 - chi)) if 0 < chi < 1 else np.nan
    return out

skip = set(pd.period_range("2020Q1", "2021Q4", freq="Q"))
rows = []
for a, b in [("1960Q1", "2004Q3"), ("1960Q1", "2007Q4"), ("1960Q1", "2019Q4"), ("1960Q1", END), ("1985Q1", "2019Q4"), ("1985Q1", END)]:
    for kinds in [("NW",), ("S", "N"), ("H", "F"), ("S", "H", "O")]:
        rows.append(cos_fit(a, b, kinds, skip=skip if b >= "2020Q1" else ()))
cos = pd.DataFrame(rows)
cos.to_csv(OUT / "q6_cos.csv", index=False)
print(cos.round(3).to_string())

rows = []
idx = d.loc["1960Q1":END].index
for i in range(79, len(idx)):
    a, b = str(idx[i - 79]), str(idx[i])
    chi, chi_se, r2, n = iv_chi(a, b, ("S", "H", "O"), skip=skip if b >= "2020Q1" else ())
    rows.append(dict(end=b, chi=chi, chi_se=chi_se, first_stage_r2=r2, n=n))
cr = pd.DataFrame(rows)
cr.to_csv(OUT / "q6_cos_rolling.csv", index=False)
print(cr.iloc[::12].round(2).to_string())

# ---- C. Beach, Gamber and Moran (2025, FEDS Notes): spending and income net of transfers ------------
# (C - T)/(Y - T) = alpha + beta W/(Y - T), dynamic OLS, 1964Q3-2011Q4; published beta 0.035, and a
# 2012-2019 out-of-sample mean error of 0.041 (spending below the model). Wealth here is start of quarter
# and the regression carries two leads and lags of the change in the wealth ratio (the note does not say).
yx = d["dpi"] - d["transfers"]
bgm_y = (d["pce"] - d["transfers"]) / yx
bgm_w = d["nw"].shift(1) / yx
bgm3 = pd.DataFrame({"S": d["S"].shift(1) / yx, "H": d["H"].shift(1) / yx, "O": d["O"].shift(1) / yx})
L4 = pd.period_range(pd.Period(END, "Q") - 3, END, freq="Q")
rows = []
def bgm_run(label, X, a, b):
    m = dols(bgm_y, X, 2, a, b)
    core = list(X.columns)
    pred = m.params["const"] + (X[core] * m.params[core]).sum(axis=1)
    err = pred - bgm_y                                   # positive = spending below the model
    r = dict(spec=label, start=a, end=b, n=int(m.nobs), insample_rmse=float(np.sqrt((err.loc[a:b] ** 2).mean())))
    for c in core:
        r[f"beta_{c}"] = 100 * m.params[c]; r[f"se_{c}"] = 100 * m.bse[c]
    for lab, sl in [("2012_2019", slice("2012Q1", "2019Q4")), ("2019", slice("2019Q1", "2019Q4")), ("2022_on", slice("2022Q1", END)), ("latest4", slice(str(L4[0]), END))]:
        r[f"err_{lab}"] = 100 * err.loc[sl].mean()        # percent of income net of transfers
    r["err_latest4_pct_of_dpi"] = 100 * (err * yx / d["dpi"]).loc[str(L4[0]):END].mean()
    rows.append(r)
bgm_run("net worth", pd.DataFrame({"W": bgm_w}), "1964Q3", "2011Q4")
bgm_run("net worth", pd.DataFrame({"W": bgm_w}), "1964Q3", "2019Q4")
bgm_run("by type", bgm3, "1964Q3", "2011Q4")
bgm_run("by type", bgm3, "1964Q3", "2019Q4")
bgm = pd.DataFrame(rows)
bgm.to_csv(OUT / "q6_bgm.csv", index=False)
print(bgm.round(2).to_string())

# ---- D. does a constant-elasticity (log) model estimated through 2019 fit the years since? ----------
rows = []
lc, cons, k = specs["Ludvigson–Steindel (total spending, 3 leads and lags)"]
for a in ["1953Q1", "1983Q1"]:
    m = dols(lc, pd.DataFrame({"w": lw, "y": ly}), k, a, "2019Q4")
    pred = m.params["const"] + m.params["w"] * lw + m.params["y"] * ly
    gap = 100 * (lc - pred)                               # percent; negative = spending below the model
    rows.append(dict(start=a, end="2019Q4", elasticity_w=m.params["w"], elasticity_y=m.params["y"], gap_2019=gap.loc["2019Q1":"2019Q4"].mean(),
                     gap_latest4=gap.loc[str(L4[0]):END].mean(), gap_change=gap.loc[str(L4[0]):END].mean() - gap.loc["2019Q1":"2019Q4"].mean(),
                     insample_sd=gap.loc[a:"2019Q4"].std()))
logoos = pd.DataFrame(rows)
logoos.to_csv(OUT / "q6_log_out_of_sample.csv", index=False)
print(logoos.round(2).to_string())

# ---- chart -----------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 5))
tt = qdates(pd.PeriodIndex(rec.end, freq="Q"))
ax.plot(tt, rec.mpc_cents, color=C["primary"], lw=1.8)
ax.fill_between(tt, rec.mpc_cents - 1.645 * rec.mpc_se, rec.mpc_cents + 1.645 * rec.mpc_se, color=C["primary"], alpha=0.15, lw=0)
ax.axhline(0, color=C["ink"], lw=0.8)
finish(fig, ax, "Spending Response to Total Net Worth From the Log Cointegrating Regression as the Sample Is Extended",
       "Implied cents of annual spending per dollar of net worth; sample starts in 1953 and ends at the date shown",
       OUT / "fig14_recursive_cointegration.png",
       note="Note: Dynamic OLS of log real total spending per person on log net worth and log labor income, in the style of Ludvigson and Steindel (1999), converted to cents per dollar at the consumption-wealth ratio of the sample’s last four quarters. Shaded band is a 90 percent confidence interval.")
print("done")
