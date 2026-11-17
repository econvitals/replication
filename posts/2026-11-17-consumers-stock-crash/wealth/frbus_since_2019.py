"""Follow-up (2026-11-13): actual real PCE since 2019 against what three wealth models say it should have been.

    python 08_scenarios.py <out dir> [<FRB/US HISTDATA.TXT>]

  1. FRB/US  The Board's own consumption block (model.xml, public package): the target level of spending
             (QEC: expected income by type and total household wealth, elasticity 0.187) and the two dynamic
             equations for nondurables-and-services (ECO) and durables (ECD), simulated from 2019Q4 on the
             model's own data with each equation's residual held at its 2015-2019 average. Housing services
             (ECH) are taken as given. Runs through the last quarter of the Board's historical file.
  2. Estimated  The main model of the November 10 report: PCE/DPI on start-of-quarter stock, housing and other
             wealth over DPI plus controls, estimated 1955Q1-2019Q4.
  3. Three cents  C = a x DPI + 0.03 x net worth at the start of the quarter, no lags, a set so that 2019 fits.
  (For reference) the constant-elasticity log model estimated 1953-2019.

Every model is anchored to actual spending in 2019 (its 2019 average residual is carried forward), and each is
also run with wealth frozen at its 2019 ratio to income, so that "the model's wealth effect" is the difference.
Writes q7_scenarios.csv, q7_summary.csv, q7_frbus_inputs.csv, fig15, fig16.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *

OUT = Path(sys.argv[1])
HIST = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "data/frbus/HISTDATA.TXT"
d = load(OUT)
x = add_basics(d)
END = x["cy"].last_valid_index()
B4 = pd.period_range("2019Q1", "2019Q4", freq="Q")
START = pd.Period("2019Q4", "Q")

# actual real PCE, chained 2017 dollars, annual rate (BEA table 2.3.6), in trillions
_r = pd.read_csv(Path(__file__).resolve().parents[1] / "data/bea_real_pce.csv", index_col=0)   # frozen BEA table 2.3.6
rpce = pd.Series(_r.iloc[:, 0].values, index=pd.PeriodIndex(_r.index, freq="Q")) / 1e6
res = pd.DataFrame({"actual": rpce.loc["2019Q1":str(END)]})

def to_real(ratio):
    """A model's predicted spending as a ratio to actual spending -> trillions of 2017 dollars."""
    return (ratio * rpce).loc["2019Q1":str(END)]

# ---- 2. the estimated model (levels by type, 1955-2019) -----------------------------------------------
m = ols(x["cy"].loc["1955Q1":"2019Q4"], x[WEALTH3 + CTL].loc["1955Q1":"2019Q4"], lags=8)
X = sm.add_constant(x[WEALTH3 + CTL], has_constant="add")
pred = X[m.params.index] @ m.params
anchor = (x["cy"] - pred).loc[B4].mean()
res["estimated"] = to_real((pred + anchor) / x["cy"])
Xf = X.copy()
for k in WEALTH3:
    Xf[k] = x.loc[B4, k].mean()
res["estimated_nowealth"] = to_real((Xf[m.params.index] @ m.params + anchor) / x["cy"])

# ---- 3. three cents per dollar of net worth, no lags --------------------------------------------------
MPC = 0.03
a = (x["cy"] - MPC * x["nwy"]).loc[B4].mean()
res["three_cents"] = to_real((a + MPC * x["nwy"]) / x["cy"])
res["three_cents_nowealth"] = to_real((a + MPC * x.loc[B4, "nwy"].mean()) / x["cy"])

# ---- reference: constant-elasticity log model, 1953-2019 (as in 07_literature.py) ---------------------
lc, lw, ly = np.log(d["r_pce"]), np.log(d["r_nw"].shift(1)), np.log(d["r_labor_at"])
Z = pd.DataFrame({"w": lw, "y": ly})
for c in ["w", "y"]:
    for j in range(-3, 4):
        Z[f"d{c}_{j}"] = Z[c].diff().shift(j)
ml = ols(lc.loc["1953Q1":"2019Q4"], Z.loc["1953Q1":"2019Q4"], lags=8)
lp = ml.params["const"] + ml.params["w"] * lw + ml.params["y"] * ly
la = (lc - lp).loc[B4].mean()
res["log_model"] = to_real(np.exp(lp + la - lc))
lw0 = ly + (lw - ly).loc[B4].mean()
res["log_model_nowealth"] = to_real(np.exp(ml.params["const"] + ml.params["w"] * lw0 + ml.params["y"] * ly + la - lc))

# ---- 1. FRB/US consumption block ------------------------------------------------------------------------
f = pd.read_csv(HIST)
f.columns = [c.lower() for c in f.columns]
f = f.set_index("obs")
f.index = pd.PeriodIndex(f.index, freq="Q")
FEND = f["ecnia"].last_valid_index()
keep = ["ecnia", "eco", "ecd", "ech", "qec", "qeco", "qecd", "zeco", "zecd", "zgapc2", "zyh", "zyht", "zyhp", "wps", "wpo", "yhl", "yht"]
f[keep].loc["2010Q1":].to_csv(OUT / "q7_frbus_inputs.csv")
L = np.log
# coefficients from the Board's model.xml (public package)
E1, E2, E4 = 0.1584215605793791, 0.4118129978512995, 0.3075237404993435      # ECO: error correction, lagged growth, rule-of-thumb share
D1, D2, D4 = 0.1561499403562654, -0.05999277989382532, 11.87185840275941      # ECD: error correction, lagged growth, zgapc2
A_ECO, A_ECD, A_ECH = 0.735, 0.1055, 0.1595                                   # ECNIA aggregation weights
W_ELAST = 0.1873934907158843                                                  # elasticity of the target to total wealth
ZQ = [0.07322397247249938, 0.02932374759217591, 0.00714849213690236, 0.00907784707291976]   # zeco on lags of target growth
rot = L(f.yhl + f.yht).diff()
r_eco = L(f.eco).diff() - ((E1 * L(f.qeco.shift(1) / f.eco.shift(1)) + E2 * L(f.eco).diff().shift(1) + f.zeco) * (1 - E4) + E4 * rot)
r_ecd = L(f.ecd).diff() - (D1 * L(f.qecd.shift(1) / f.ecd.shift(1)) + D2 * L(f.ecd).diff().shift(1) + f.zecd + D4 * f.zgapc2 / 400)
r_agg = L(f.ecnia).diff() - (A_ECO * L(f.eco).diff() + A_ECD * L(f.ecd).diff() + A_ECH * L(f.ech).diff())
RES = slice("2015Q1", "2019Q4")
re_eco, re_ecd = r_eco.loc[RES].mean(), r_ecd.loc[RES].mean()

def frbus_sim(scale, resid_eco, resid_ecd, start=START):
    """scale = counterfactual target / actual target (1 = actual wealth). Returns simulated ECNIA."""
    qeco, qecd = f.qeco * scale, f.qecd * scale
    dz = sum(c * (L(qeco).diff().shift(i + 1) - L(f.qeco).diff().shift(i + 1)) for i, c in enumerate(ZQ))
    zeco = f.zeco + dz.fillna(0)
    eco, ecd, tot = f.eco.copy(), f.ecd.copy(), f.ecnia.copy()
    for t in pd.period_range(start + 1, FEND, freq="Q"):
        g_eco = (E1 * L(qeco[t - 1] / eco[t - 1]) + E2 * L(eco[t - 1] / eco[t - 2]) + zeco[t]) * (1 - E4) + E4 * rot[t] + resid_eco
        g_ecd = D1 * L(qecd[t - 1] / ecd[t - 1]) + D2 * L(ecd[t - 1] / ecd[t - 2]) + f.zecd[t] + D4 * f.zgapc2[t] / 400 + resid_ecd
        eco[t], ecd[t] = eco[t - 1] * np.exp(g_eco), ecd[t - 1] * np.exp(g_ecd)
        tot[t] = tot[t - 1] * np.exp(A_ECO * g_eco + A_ECD * g_ecd + A_ECH * L(f.ech[t] / f.ech[t - 1]) + r_agg[t])
    return tot

W = f.wpo + f.wps
w0 = (W / f.zyh).loc[B4].mean() * f.zyh                 # wealth frozen at its 2019 ratio to expected income
scale0 = pd.Series(1.0, index=f.index)
scale0.loc[str(START + 1):] = ((w0 / W) ** W_ELAST).loc[str(START + 1):]
fr = frbus_sim(pd.Series(1.0, index=f.index), re_eco, re_ecd)
fr0 = frbus_sim(scale0, re_eco, re_ecd)
frz = frbus_sim(pd.Series(1.0, index=f.index), 0.0, re_ecd)        # sensitivity: no carried residual in the ECO equation
res["frbus"] = to_real(fr / f.ecnia)
res["frbus_nowealth"] = to_real(fr0 / f.ecnia)
res["frbus_zero_resid"] = to_real(frz / f.ecnia)
res.loc[res.index > FEND, ["frbus", "frbus_nowealth", "frbus_zero_resid"]] = np.nan
res.to_csv(OUT / "q7_scenarios.csv")

# ---- summary ------------------------------------------------------------------------------------------
rows = []
names = {"frbus": "FRB/US consumption block", "estimated": "Estimated model (wealth by type, 1955–2019)",
         "three_cents": "Three cents per dollar of net worth, no lags", "log_model": "For reference: constant-elasticity model, 1953–2019"}
for k, lab in names.items():
    q = FEND if k == "frbus" else END
    act, mod, now = res.loc[q, "actual"], res.loc[q, k], res.loc[q, k + "_nowealth"]
    base = res.loc["2019Q4", "actual"]
    rows.append(dict(model=lab, key=k, quarter=str(q), actual=act, predicted=mod, gap_bn=1000 * (mod - act), gap_pct=100 * (mod / act - 1),
                     growth_actual=100 * (act / base - 1), growth_model=100 * (mod / base - 1), growth_nowealth=100 * (now / base - 1),
                     wealth_effect_bn=1000 * (mod - now), wealth_effect_pct=100 * (mod - now) / now,
                     share_shown=100 * (act - now) / (mod - now)))
    if k != "frbus":      # the same model at the FRB/US end date, for a like-for-like row
        q = FEND
        act, mod, now = res.loc[q, "actual"], res.loc[q, k], res.loc[q, k + "_nowealth"]
        rows.append(dict(model=lab, key=k + "@frbus_end", quarter=str(q), actual=act, predicted=mod, gap_bn=1000 * (mod - act), gap_pct=100 * (mod / act - 1),
                         growth_actual=100 * (act / base - 1), growth_model=100 * (mod / base - 1), growth_nowealth=100 * (now / base - 1),
                         wealth_effect_bn=1000 * (mod - now), wealth_effect_pct=100 * (mod - now) / now, share_shown=100 * (act - now) / (mod - now)))
summ = pd.DataFrame(rows)
summ.to_csv(OUT / "q7_summary.csv", index=False)
extra = pd.Series({"frbus_end": str(FEND), "end": str(END), "eco_gap_2019": 100 * L(f.eco / f.qeco)["2019Q4"], "eco_gap_end": 100 * L(f.eco / f.qeco)[FEND],
                   "frbus_zero_resid_gap_pct": 100 * (res.loc[FEND, "frbus_zero_resid"] / res.loc[FEND, "actual"] - 1),
                   "resid_eco_mean": 100 * re_eco, "resid_ecd_mean": 100 * re_ecd, "w_real_2019": W["2019Q4"] / 1e3, "w_real_end": W[FEND] / 1e3,
                   "wps_2019": f.wps["2019Q4"] / 1e3, "wps_end": f.wps[FEND] / 1e3, "anchor_estimated_pp": 100 * anchor, "three_cents_a": a,
                   "stock_coef": 100 * m.params["Sy"], "housing_coef": 100 * m.params["Hy"], "log_elasticity": ml.params["w"],
                   "nwy_2019": x.loc[B4, "nwy"].mean(), "nwy_end": x.loc[END, "nwy"],
                   "frbus_cents_2019": 100 * W_ELAST * f.ecnia["2019Q4"] / W["2019Q4"], "frbus_cents_end": 100 * W_ELAST * f.ecnia[FEND] / W[FEND],
                   "w_zyh_2019": (W / f.zyh).loc[B4].mean(), "w_zyh_end": (W / f.zyh)[FEND],
                   "frbus_maxabs_gap_since_2022q3": 100 * (res["actual"] / res["frbus"] - 1).loc["2022Q3":str(FEND)].abs().max(),
                   "target_wealth_effect_pct": 100 * (1 / scale0[FEND] - 1)})
extra.to_csv(OUT / "q7_extra.csv", header=["value"])
pd.set_option("display.width", 250)
print(res.loc[["2019Q4", "2020Q4", "2021Q4", "2022Q4", "2023Q4", "2024Q4", "2025Q4", str(FEND), str(END)]].round(2).to_string())
print(summ.drop(columns="model").round(1).to_string())
print(extra.to_string())

# ---- does the starting point matter? Re-anchor each model at later dates ------------------------------
# Static models: rescale so the model equals actual on average over the four quarters ending at the anchor.
# FRB/US: restart the simulation from actual spending in the anchor quarter (residuals still at 2015-2019 means).
arows = []
one = pd.Series(1.0, index=f.index)
for anchor_q in ["2019Q4", "2022Q4", "2023Q4", "2024Q2", "2024Q4"]:
    aq = pd.Period(anchor_q, "Q")
    win = pd.period_range(aq - 3, aq, freq="Q")
    row = dict(anchor=anchor_q, saving_rate_at_anchor=d.loc[win, "saving_rate"].mean(), pce_share_at_anchor=100 * x.loc[win, "cy"].mean())
    for k in ["estimated", "three_cents", "log_model"]:
        ratio = res[k] / res["actual"]
        adj = ratio / ratio.loc[[str(q) for q in win]].mean()
        for q in [FEND, END]:
            row[f"{k}_{q}"] = 100 * (adj.loc[str(q)] - 1)
    sim = frbus_sim(one, re_eco, re_ecd, start=aq)
    row[f"frbus_{FEND}"] = 100 * (sim[FEND] / f.ecnia[FEND] - 1)
    row["eco_vs_target_at_anchor"] = 100 * L(f.eco / f.qeco)[aq]
    arows.append(row)
anch = pd.DataFrame(arows)
anch.to_csv(OUT / "q7_anchor_sensitivity.csv", index=False)
print(anch.round(2).to_string())
print(d["saving_rate"].groupby(d.index.year).mean().loc[2015:].round(1).to_dict())

# ---- charts -------------------------------------------------------------------------------------------
tt = qdates(res.index)
SRC2 = "Source: Bureau of Economic Analysis; Federal Reserve Board, Financial Accounts and FRB/US model package; author’s calculations."
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(tt, res["actual"], color=C["ink"], lw=2.4, label="Actual")
ax.plot(tt, res["frbus"], color=C["primary"], lw=1.7, label="FRB/US consumption block")
ax.plot(tt, res["estimated"], color=C["secondary"], lw=1.7, label="Estimated model (wealth by type, 1955–2019)")
ax.plot(tt, res["three_cents"], color=C["teal"], lw=1.7, label="Three cents per dollar of net worth, no lags")
ax.legend(loc="lower right", fontsize=8.5)
finish(fig, ax, "Real Personal Consumption Expenditures, Actual and as Implied by Three Wealth Models",
       "Trillions of chained 2017 dollars, annual rate", OUT / "fig15_real_pce_scenarios.png", source=SRC2,
       note=f"Note: Each model is anchored to actual spending in 2019 and then fed actual income and wealth. The FRB/US line ends in {FEND}, the last quarter of the Board’s historical data file.")

fig, ax = plt.subplots(figsize=(8, 5))
w2 = res.loc["2021Q4":]
t2 = qdates(w2.index)
for k, col, lab in [("frbus", "primary", "FRB/US consumption block"), ("estimated", "secondary", "Estimated model (wealth by type, 1955–2019)"),
                    ("three_cents", "teal", "Three cents per dollar of net worth, no lags")]:
    ax.plot(t2, 100 * (w2["actual"] / w2[k] - 1), color=C[col], lw=1.8, label=lab)
ax.axhline(0, color=C["ink"], lw=0.8)
ax.legend(loc="upper right", fontsize=8.5)
finish(fig, ax, "Actual Real Consumer Spending Relative to Each Model",
       "Percent above (+) or below (−) the model’s prediction", OUT / "fig16_gap_to_models.png", source=SRC2,
       note="Note: Each model is anchored to actual spending in 2019, so the lines show the gap that has opened since.")
print("done")
