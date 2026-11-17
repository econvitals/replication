"""All computations for the consumption-function write-up (2026-11-16). chartbook venv, run from the folder with code/ and output/.
Writes output/r9_cf_results.json (every number), output/r9_*.csv (tables) and the series the charts need."""
import sys, json
sys.path.insert(0, "wealth")
from common import *
import warnings; warnings.filterwarnings("ignore")
from statsmodels.tsa.stattools import adfuller, coint

OUT = Path("output")
d = load(Path("output")); x = add_basics(d)
END = str(x["cy"].last_valid_index())
R = {"END": END, "ZEND": str(d["S"].last_valid_index())}
CORE = WEALTH3 + CTL
LAB = {"const": "Constant", "Sy": "Stock wealth / income", "Hy": "Housing wealth / income", "Oy": "Other net wealth / income",
       "nwy": "Net worth / income", "HEy": "Home equity / income", "O_hey": "Other (with mortgages netted from housing) / income",
       "tr_share": "Transfers / income", "unrate": "Unemployment rate", "rr": "Real 3-month bill rate", "ygap": "Income relative to its 2-year average",
       "sent": "Consumer sentiment", "post09": "Level shift from 2009"}
DROP2022 = pd.period_range("2020Q1", "2022Q4", freq="Q")

def fit(a, b, wealth=WEALTH3, ctl=CTL, dep="cy", dols=0, lags=8, xx=None, drop=None, extra=None):
    xx = x if xx is None else xx
    cols = list(wealth) + list(ctl) + list(extra or [])
    X = xx[cols].copy()
    if dols:
        for k in wealth:
            dk = xx[k].diff()
            for j in range(-dols, dols + 1):
                X[f"d{k}_{j}"] = dk.shift(j)
    if b >= "2020Q1":
        X[DUMS] = xx[DUMS]
    y = xx[dep].loc[a:b]; X = X.loc[a:b]
    if drop is not None:
        keep = ~y.index.isin(drop); y = y[keep]; X = X[keep]
        X = X.drop(columns=[c for c in DUMS if c in X.columns])
    return ols(y, X, lags=lags)

def summ(m, keys):
    r = {"n": int(m.nobs), "r2": m.rsquared, "r2a": m.rsquared_adj, "se_reg": float(np.sqrt(m.scale)) * 100, "dw": float(sm.stats.durbin_watson(m.resid))}
    for k in keys:
        if k in m.params.index:
            scale = 100 if k in ("Sy", "Hy", "Oy", "nwy", "HEy", "O_hey") else 100
            r[k] = float(m.params[k] * scale); r[k + "_se"] = float(m.bse[k] * scale); r[k + "_t"] = float(m.tvalues[k])
    r["adf"] = float(adfuller(m.resid.dropna(), regression="c", autolag="AIC")[0])
    r["adf_p"] = float(adfuller(m.resid.dropna(), regression="c", autolag="AIC")[1])
    return r

# ---------------------------------------------------------------- 1. main regression tables
SAMPLES = [("1955Q1", "2019Q4"), ("1955Q1", END), ("1989Q1", "2015Q4"), ("1990Q1", "2019Q4"), ("2010Q1", "2019Q4")]
main = {}
for a, b in SAMPLES:
    m = fit(a, b)
    s = summ(m, ["const"] + CORE)
    ct = coint(x["cy"].loc[a:b], x[WEALTH3].loc[a:b], trend="c")
    s["eg"] = float(ct[0]); s["eg_p"] = float(ct[1]); s["eg_crit5"] = float(ct[2][1])
    main[f"{a}-{b}"] = s
R["main"] = main
# constant in percent of income: params are in ratio units; summ multiplied by 100 so const is percent, controls are pp of C/Y per unit

# fitted and residuals of the 1955-2019 model, extended to the end (out of sample after 2019)
m19 = fit("1955Q1", "2019Q4")
Xf = sm.add_constant(x[CORE], has_constant="add")
fitted19 = Xf[["const"] + CORE] @ m19.params[["const"] + CORE]
mall = fit("1955Q1", END)
fittedall = Xf[["const"] + CORE] @ mall.params[["const"] + CORE]
for q in DUMS:
    pass
ser = pd.DataFrame({"cy": 100 * x["cy"], "fit19": 100 * fitted19, "fitall": 100 * fittedall,
                    "Sy": x["Sy"], "Hy": x["Hy"], "Oy": x["Oy"], "tr": 100 * x["tr_share"], "unrate": x["unrate"], "rr": x["rr"], "ygap": x["ygap"]}).loc["1955Q1":END]
ser.to_csv(OUT / "r9_series.csv")
R["resid19_2019avg"] = float((ser["cy"] - ser["fit19"]).loc["2019Q1":"2019Q4"].mean())
R["resid19_by_year"] = {str(y): float((ser["cy"] - ser["fit19"]).loc[f"{y}Q1":f"{y}Q4"].mean()) for y in (2000, 2005, 2007, 2010, 2012, 2015, 2017, 2019, 2021, 2023, 2024, 2025)}
R["resid19_2026q3"] = float((ser["cy"] - ser["fit19"]).loc[END])
R["levels"] = {q: {k: float(ser.loc[q, k]) for k in ["cy", "Sy", "Hy", "Oy", "tr", "unrate", "rr", "ygap"]} for q in ["1955Q1", "1990Q1", "2000Q1", "2007Q4", "2019Q4", END]}
R["levels"]["2019avg"] = {k: float(ser.loc["2019Q1":"2019Q4", k].mean()) for k in ["cy", "Sy", "Hy", "Oy", "tr", "unrate", "rr", "ygap"]}

# ---------------------------------------------------------------- 2. rolling and expanding
rows = []
qs = x.index
for W in (40, 60, 80):
    for b in qs:
        a = b - (W - 1)
        if a < pd.Period("1955Q1", "Q") or b > pd.Period(END, "Q"):
            continue
        m = fit(str(a), str(b))
        rows.append(dict(W=W, end=str(b), start=str(a), **{k: 100 * m.params[k] for k in WEALTH3}, **{k + "_se": 100 * m.bse[k] for k in WEALTH3}, r2=m.rsquared, n=int(m.nobs)))
roll = pd.DataFrame(rows); roll.to_csv(OUT / "r9_rolling_all.csv", index=False)
sel = {}
for W in (40, 60, 80):
    r_ = roll[roll.W == W].set_index("end")
    sel[W] = {e: {k: float(r_.loc[e, k]) for k in ["Sy", "Sy_se", "Hy", "Hy_se", "Oy", "Oy_se", "r2", "n"]} | {"start": r_.loc[e, "start"]}
              for e in ["1999Q4", "2003Q4", "2007Q4", "2011Q4", "2015Q4", "2019Q4", "2021Q4", "2023Q4", "2024Q4", "2025Q4", END] if e in r_.index}
    R[f"roll{W}_range_1990_2019"] = [float(r_.loc["1990Q1":"2019Q4", "Sy"].min()), float(r_.loc["1990Q1":"2019Q4", "Sy"].max())]
    R[f"roll{W}_range_2010_2019"] = [float(r_.loc["2010Q1":"2019Q4", "Sy"].min()), float(r_.loc["2010Q1":"2019Q4", "Sy"].max())]
    R[f"roll{W}_range_before1999"] = [float(r_.loc[:"1999Q4", "Sy"].min()), float(r_.loc[:"1999Q4", "Sy"].max())]
R["roll_sel"] = sel
exp = {}
for b in ["1989Q4", "1999Q4", "2007Q4", "2012Q4", "2015Q4", "2019Q4", "2021Q4", "2022Q4", "2023Q4", "2024Q4", "2025Q4", END]:
    m = fit("1955Q1", b); exp[b] = {k: float(100 * m.params[k]) for k in WEALTH3} | {k + "_se": float(100 * m.bse[k]) for k in WEALTH3}
R["expanding"] = exp
# Sup-Wald break results from the November 10 run
R["breaks"] = pd.read_csv("output/q1_breaks.csv").to_dict(orient="records")

# ---------------------------------------------------------------- 3. sensitivity of the stock coefficient
xa = x.copy()                                  # income excluding after-tax interest and dividends
Yx = d["dpi"] - d["prop_income"] * (1 - d["taxes"] / d["pinc"])
xa["cy"] = d["pce"] / Yx
for k in ["S", "H", "O"]:
    xa[f"{k}y"] = d[k].shift(1) / Yx
xa["tr_share"] = d["transfers"] / Yx
x["post09"] = (x.index >= pd.Period("2009Q1", "Q")).astype(float)
SPECS = [
    ("Baseline", dict()),
    ("No controls", dict(ctl=[])),
    ("Without transfers", dict(ctl=[c for c in CTL if c != "tr_share"])),
    ("Without unemployment", dict(ctl=[c for c in CTL if c != "unrate"])),
    ("Without the real interest rate", dict(ctl=[c for c in CTL if c != "rr"])),
    ("Without income relative to its average", dict(ctl=[c for c in CTL if c != "ygap"])),
    ("Adding consumer sentiment", dict(extra=["sent"])),
    ("Adding a level shift from 2009", dict(extra=["post09"])),
    ("Leads and lags of wealth changes (±2)", dict(dols=2)),
    ("Leads and lags of wealth changes (±4)", dict(dols=4)),
    ("Home equity instead of gross housing", dict(wealth=["Sy", "HEy", "O_hey"])),
    ("Total outlays instead of spending", dict(dep="oy")),
    ("Income excluding interest and dividends", dict(xx=xa)),
    ("Starting in 1965", dict(start="1965Q1")),
    ("Starting in 1980", dict(start="1980Q1")),
]
sens = []
for name, kw in SPECS:
    row = {"spec": name}
    for tag, (a, b) in (("2019", ("1955Q1", "2019Q4")), ("2026", ("1955Q1", END))):
        a = kw.get("start", a)
        kk = {k: v for k, v in kw.items() if k != "start"}
        m = fit(a, b, **kk)
        row[f"S_{tag}"] = 100 * m.params["Sy"]; row[f"Sse_{tag}"] = 100 * m.bse["Sy"]
        hk = "HEy" if "HEy" in m.params.index else "Hy"
        row[f"H_{tag}"] = 100 * m.params[hk]; row[f"Hse_{tag}"] = 100 * m.bse[hk]
    sens.append(row)
# HAC lag choices (same coefficient, different standard error)
for L_ in (4, 12):
    row = {"spec": f"Standard errors with {L_} lags instead of 8"}
    for tag, (a, b) in (("2019", ("1955Q1", "2019Q4")), ("2026", ("1955Q1", END))):
        m = fit(a, b, lags=L_); row[f"S_{tag}"] = 100 * m.params["Sy"]; row[f"Sse_{tag}"] = 100 * m.bse["Sy"]
        row[f"H_{tag}"] = 100 * m.params["Hy"]; row[f"Hse_{tag}"] = 100 * m.bse["Hy"]
    sens.append(row)
row = {"spec": "Dropping 2020–2022 entirely"}
m = fit("1955Q1", END, drop=DROP2022)
row["S_2026"] = 100 * m.params["Sy"]; row["Sse_2026"] = 100 * m.bse["Sy"]; row["H_2026"] = 100 * m.params["Hy"]; row["Hse_2026"] = 100 * m.bse["Hy"]
sens.append(row)
row = {"spec": "Total net worth instead of the three types"}
for tag, (a, b) in (("2019", ("1955Q1", "2019Q4")), ("2026", ("1955Q1", END))):
    m = fit(a, b, wealth=["nwy"]); row[f"S_{tag}"] = 100 * m.params["nwy"]; row[f"Sse_{tag}"] = 100 * m.bse["nwy"]
sens.append(row)
R["sens"] = sens

# ---------------------------------------------------------------- 4. the post-COVID application
W19 = pd.period_range("2019Q1", "2019Q4", freq="Q")
Y = d["dpi"]; C = d["pce"]
def apply_cf(m, anchor_years, xx=None, Yser=None, wealth=WEALTH3, ctl=CTL, base_for_freeze=None):
    xx = x if xx is None else xx; Yser = Y if Yser is None else Yser
    cols = ["const"] + list(wealth) + list(ctl)
    X = sm.add_constant(xx[list(wealth) + list(ctl)], has_constant="add")
    pred = X[cols] @ m.params[cols]
    W = pd.period_range(f"{anchor_years}Q1", f"{anchor_years}Q4", freq="Q")
    anc = (xx["cy"] - pred).loc[W].mean()
    Xs = X.copy(); Xs["Sy"] = xx.loc[W, "Sy"].mean()
    pred_ns = Xs[cols] @ m.params[cols]
    return (pred + anc) * Yser, (pred_ns + anc) * Yser, float(anc)
cf, cf_ns, anc = apply_cf(m19, 2019)
R["anchor_pp"] = 100 * anc
path = pd.DataFrame({"actual": C, "cf": cf, "cf_nostock": cf_ns, "noeffect": (C / Y).loc[W19].mean() * Y}).loc["2018Q1":END] / 1e6
path.to_csv(OUT / "r9_cf_path.csv")
e = pd.Period(END, "Q")
R["cf_gap_bn"] = float((cf[e] - C[e]) / 1e3); R["cf_gap_pct"] = float(100 * (cf[e] / C[e] - 1))
R["cf_stock_effect_bn"] = float((cf[e] - cf_ns[e]) / 1e3); R["cf_stock_shown_bn"] = float((C[e] - cf_ns[e]) / 1e3)
R["cf_cum2022_bn"] = float(((cf - C) / 1e3).loc["2022Q1":END].sum() / 4)
R["cf_cum2020_bn"] = float(((cf - C) / 1e3).loc["2020Q1":END].sum() / 4)
R["cf_gap_by_year"] = {str(y): float(100 * (cf / C - 1).loc[f"{y}Q1":f"{y}Q4"].mean()) for y in (2020, 2021, 2022, 2023, 2024, 2025)}
R["cf_gap_by_year"]["2026Q3"] = R["cf_gap_pct"]
# decomposition of the predicted change in the spending share, 2019 average to the latest quarter, $ billions at the latest income
dec = []
for k in CORE:
    v19 = x.loc[W19, k].mean(); vE = x.loc[e, k]
    dec.append(dict(var=k, label=LAB[k], v2019=float(v19), vend=float(vE), coef=float(m19.params[k]), contrib_pp=float(100 * m19.params[k] * (vE - v19)),
                    contrib_bn=float(m19.params[k] * (vE - v19) * Y[e] / 1e3)))
R["decomp"] = dec
R["actual_share_change_pp"] = float(100 * (x.loc[e, "cy"] - x.loc[W19, "cy"].mean()))
R["actual_share_change_bn"] = float((x.loc[e, "cy"] - x.loc[W19, "cy"].mean()) * Y[e] / 1e3)
R["stock_mpc_within_cf"] = float(100 * (C[e] - cf_ns[e]) / ((x.loc[e, "Sy"] - x.loc[W19, "Sy"].mean()) * Y[e]))
R["excess_S_tn"] = float((x.loc[e, "Sy"] - x.loc[W19, "Sy"].mean()) * Y[e] / 1e6)
# anchor-year sensitivity
anch = []
for yr in (2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024):
    c_, ns_, a_ = apply_cf(m19, yr)
    anch.append(dict(year=yr, anchor_pp=100 * a_, saving=float(d["saving_rate"].loc[f"{yr}Q1":f"{yr}Q4"].mean()),
                     gap_bn=float((c_[e] - C[e]) / 1e3), gap_pct=float(100 * (c_[e] / C[e] - 1)),
                     stock_effect_bn=float((c_[e] - ns_[e]) / 1e3), shown_bn=float((C[e] - ns_[e]) / 1e3)))
R["anchor_sens"] = anch
# estimation-sample and specification sensitivity (all anchored to 2019)
est = []
for lab, kw, a, b in [("1955–2007", {}, "1955Q1", "2007Q4"), ("1955–2012", {}, "1955Q1", "2012Q4"), ("1955–2016", {}, "1955Q1", "2016Q4"),
                      ("1955–2019 (baseline)", {}, "1955Q1", "2019Q4"), ("1980–2019", {}, "1980Q1", "2019Q4"), ("1990–2019", {}, "1990Q1", "2019Q4"),
                      ("1955–2019, no controls", {"ctl": []}, "1955Q1", "2019Q4"), ("1955–2019, leads and lags (±2)", {"dols": 2}, "1955Q1", "2019Q4"),
                      ("1955–2019, home equity", {"wealth": ["Sy", "HEy", "O_hey"]}, "1955Q1", "2019Q4")]:
    m = fit(a, b, **kw)
    wl = kw.get("wealth", WEALTH3); cl = kw.get("ctl", CTL)
    c_, ns_, a_ = apply_cf(m, 2019, wealth=wl, ctl=cl)
    est.append(dict(sample=lab, S=100 * m.params["Sy"], gap_bn=float((c_[e] - C[e]) / 1e3), gap_pct=float(100 * (c_[e] / C[e] - 1)),
                    stock_effect_bn=float((c_[e] - ns_[e]) / 1e3), shown_pct=float(100 * (C[e] - ns_[e]) / (c_[e] - ns_[e])), anchor_pp=100 * a_))
R["est_sens"] = est
# out-of-sample benchmark: how far off is a model 7 years after its anchor, in normal times?
oos = []
for b_est, anc_yr, horizon_end in (("1999Q4", 1999, "2006Q4"), ("2007Q4", 2007, "2014Q4"), ("2012Q4", 2012, "2019Q4")):
    m = fit("1955Q1", b_est)
    c_, ns_, a_ = apply_cf(m, anc_yr)
    g = (100 * (c_ / C - 1)).loc[f"{anc_yr + 1}Q1":horizon_end]
    oos.append(dict(est=f"1955–{b_est[:4]}", anchor=anc_yr, window=f"{anc_yr + 1}–{horizon_end[:4]}", gap_end=float(g.iloc[-1]), max_abs=float(g.abs().max()), mean=float(g.mean())))
R["oos"] = oos

# ---------------------------------------------------------------- 5. the simple rules
S0 = d["S"].shift(1)
Yx_ = Yx
rules = []
for inc, YY in (("all", Y), ("exid", Yx_)):
    for yr in (2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024):
        W = pd.period_range(f"{yr}Q1", f"{yr}Q4", freq="Q")
        c0 = (C / YY).loc[W].mean(); s0 = (S0 / YY).loc[W].mean()
        fitm = 100 * (C[e] - c0 * YY[e]) / (S0[e] - s0 * YY[e])
        rules.append(dict(income=inc, base=yr, c0=float(c0), s0=float(s0), mpc_fit=float(fitm), excess_S_tn=float((S0[e] - s0 * YY[e]) / 1e6),
                          extra_spending_bn=float((C[e] - c0 * YY[e]) / 1e3)))
R["rules"] = rules
c0 = (C / Y).loc[W19].mean(); s0 = (S0 / Y).loc[W19].mean()
mq = (100 * (C - c0 * Y) / (S0 - s0 * Y)).loc["2021Q1":END]
pd.DataFrame({"mpc_fit": mq}).to_csv(OUT / "r9_rule_fit_by_quarter.csv")
idx = pd.period_range("2023Q1", END, freq="Q")
exs = (C - c0 * Y).loc[idx]; xs = (S0 - s0 * Y).loc[idx]
R["rule_ls_2023_on"] = float(100 * (exs * xs).sum() / (xs * xs).sum())
idx = pd.period_range("2024Q1", END, freq="Q")
exs = (C - c0 * Y).loc[idx]; xs = (S0 - s0 * Y).loc[idx]
R["rule_ls_2024_on"] = float(100 * (exs * xs).sum() / (xs * xs).sum())
R["table2"] = pd.read_csv("output/r8_table2.csv").query("income=='all' and anchor==2019").to_dict(orient="records")

# ---------------------------------------------------------------- 6. gains and losses
P = d["p_pce"] / 100; rY = Y / P
rg = d["rg_S"].fillna(0).loc["1952Q1":] / P
x["Gy"] = rg.clip(lower=0).cumsum().shift(1) / rY
x["Ly"] = rg.clip(upper=0).cumsum().shift(1) / rY
x["Fy"] = (d["S"] / P - rg.clip(lower=0).cumsum() - rg.clip(upper=0).cumsum()).shift(1) / rY
x["Gpost"] = (rg.clip(lower=0) * (rg.index >= pd.Period("2020Q1", "Q"))).cumsum().shift(1) / rY
asym_full = {}
for tag, (a, b), extra in (("1955–2019", ("1955Q1", "2019Q4"), []), (f"1955–{END[:4]}", ("1955Q1", END), []), ("post", ("1955Q1", END), ["Gpost"])):
    m = fit(a, b, wealth=["Gy", "Ly", "Fy", "Hy", "Oy"], extra=extra)
    r = {k: float(100 * m.params[k]) for k in m.params.index if k in ("Gy", "Ly", "Fy", "Hy", "Oy", "Gpost")}
    r |= {k + "_se": float(100 * m.bse[k]) for k in m.params.index if k in ("Gy", "Ly", "Fy", "Hy", "Oy", "Gpost")}
    dd = lincom(m, ["Gy", "Ly"], [1, -1]); r["diff_t"] = float(dd[0] / dd[1]); r["n"] = int(m.nobs); r["r2"] = float(m.rsquared)
    if extra:
        gp = lincom(m, ["Gy", "Gpost"]); r["gp"] = float(100 * gp[0]); r["gp_se"] = float(100 * gp[1])
    asym_full[tag] = r
R["asym"] = asym_full
# variants: extra effect of losses beyond the average
var = []
x["Ln"] = x["Ly"]
lvl = d["r_S"].shift(1); x["short"] = ((lvl - lvl.cummax()) * d["pop"] * 1000 / 1e6) / rY
for N in (8, 12):
    x[f"L{N}"] = rg.clip(upper=0).rolling(N).sum().shift(1) / rY; x[f"G{N}"] = rg.clip(lower=0).rolling(N).sum().shift(1) / rY
for lab, extra in (("Cumulative losses since 1952 (extra effect)", ["Ln"]), ("Losses and gains over the past 2 years (extra effects)", ["L8", "G8"]),
                   ("Losses and gains over the past 3 years (extra effects)", ["L12", "G12"]), ("Shortfall from the previous peak (extra effect)", ["short"])):
    for tag, (a, b) in (("2019", ("1955Q1", "2019Q4")), ("2026", ("1955Q1", END))):
        m = fit(a, b, extra=extra)
        var.append(dict(variant=lab, sample=tag, S=float(100 * m.params["Sy"]), **{k: float(100 * m.params[k]) for k in extra},
                        **{k + "_t": float(m.tvalues[k]) for k in extra}))
R["asym_variants"] = var
R["asym_changes"] = pd.read_csv("output/q3_asymmetry.csv").query("asset=='gS' and variant=='real gain above or below zero'")[["start", "end", "h", "up", "up_se", "down", "down_se", "t"]].to_dict(orient="records")

# ---------------------------------------------------------------- 7. dynamics
dyn = {}
for a, b in (("1955Q1", "2019Q4"), ("1955Q1", END)):
    m = fit(a, b)
    core = ["const"] + CORE
    res = x["cy"] - sm.add_constant(x[CORE], has_constant="add")[core] @ m.params[core]
    E = pd.DataFrame({"ec": res.shift(1), "dcy1": x["cy"].diff().shift(1)})
    for k in CORE:
        E["d" + k] = x[k].diff()
    if b >= "2020Q1":
        for q in PANDEMIC:
            E[f"D{q}"] = x[f"D{q}"]; E[f"L{q}"] = (x.index == q + 1).astype(float)
    me = ols(x["cy"].diff().loc[a:b], E.loc[a:b], lags=4)
    bS, lam, phi, bd = m.params["Sy"], -me.params["ec"], me.params["dcy1"], me.params["dSy"]
    T = 21; cyp = np.zeros(T); S = np.zeros(T); S[1:] = -1.0
    for t in range(1, T):
        prev_res = cyp[t - 1] - bS * S[t - 1]
        dprev = cyp[t - 1] - cyp[t - 2] if t >= 2 else 0.0
        cyp[t] = cyp[t - 1] - lam * prev_res + phi * dprev + bd * (S[t] - S[t - 1])
    share_ecm = list(cyp / (-bS))
    # partial adjustment (lagged dependent variable)
    Xp = x[CORE].copy(); Xp["cy_lag"] = x["cy"].shift(1)
    if b >= "2020Q1":
        Xp[DUMS] = x[DUMS]
        for q in PANDEMIC: Xp[f"L{q}"] = (x.index == q + 1).astype(float)
    mp = ols(x["cy"].loc[a:b], Xp.loc[a:b], lags=4)
    rho = mp.params["cy_lag"]
    dyn[f"{a}-{b}"] = dict(bS=float(100 * bS), lam=float(lam), lam_se=float(me.bse["ec"]), phi=float(phi), dS_short=float(100 * bd), dS_short_se=float(100 * me.bse["dSy"]),
                           ecm_n=int(me.nobs), ecm_r2=float(me.rsquared), share_ecm=[float(v) for v in share_ecm],
                           pa_rho=float(rho), pa_rho_se=float(mp.bse["cy_lag"]), pa_short=float(100 * mp.params["Sy"]), pa_long=float(100 * mp.params["Sy"] / (1 - rho)),
                           share_pa=[float(1 - rho ** h) if h > 0 else 0.0 for h in range(T)])
R["dyn"] = dyn
# GDP paths for a 25 percent fall: $ billions lost and percent of GDP
S_NOW, GDP_NOW = 74005.4, 33010.0
lost = 0.25 * S_NOW
dd_ = dyn[f"1955Q1-{END}"]
R["gdp25"] = dict(lost_bn=lost, static=-lost * dd_["bS"] / 100 / GDP_NOW * 100,
                  ecm=[-lost * dd_["bS"] / 100 / GDP_NOW * 100 * s for s in dd_["share_ecm"]],
                  hybrid=[-lost * dd_["bS"] / 100 / GDP_NOW * 100 * s for s in dd_["share_pa"]],
                  pa_own=[-lost * dd_["pa_long"] / 100 / GDP_NOW * 100 * s for s in dd_["share_pa"]],
                  r1=-lost * 0.01 / GDP_NOW * 100, r3=-lost * 0.03 / GDP_NOW * 100)
json.dump(R, open(OUT / "r9_cf_results.json", "w"), indent=1, default=float)
print(json.dumps({k: R[k] for k in ["anchor_pp", "cf_gap_bn", "cf_gap_pct", "cf_stock_effect_bn", "cf_stock_shown_bn", "stock_mpc_within_cf", "rule_ls_2023_on", "rule_ls_2024_on", "resid19_2019avg"]}, indent=1))
print("oos", json.dumps(R["oos"], indent=0))
print("dyn", {k: (round(v["lam"], 3), round(v["dS_short"], 2), [round(s, 2) for s in v["share_ecm"][:9]]) for k, v in dyn.items()})
print("gdp25 ecm 4q", round(R["gdp25"]["ecm"][4], 2), "hybrid 4q", round(R["gdp25"]["hybrid"][4], 2), "pa_own 4q", round(R["gdp25"]["pa_own"][4], 2), "static", round(R["gdp25"]["static"], 2))
print(pd.DataFrame(sens).round(2).to_string())
print(pd.DataFrame(est).round(2).to_string())
print(pd.DataFrame(anch).round(2).to_string())
