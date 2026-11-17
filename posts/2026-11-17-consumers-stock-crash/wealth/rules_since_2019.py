"""Table 2 for R8: spending since 2019 against FRB/US, the consumption function and 1/3/5-cent rules on stock wealth.
Two income concepts: all disposable income, and disposable income excluding after-tax interest and dividends."""
import sys; sys.path.insert(0, "wealth")
from common import *
import warnings; warnings.filterwarnings("ignore")
OUT = Path("output"); d = load(OUT); x = add_basics(d)
HIST = Path("data/frbus/HISTDATA.TXT")   # the Board's public FRB/US data package, history through 2026Q2
L = np.log
# ---------------- FRB/US consumption block (copied from 08_scenarios.py) ----------------
f = pd.read_csv(HIST); f.columns = [c.lower() for c in f.columns]; f = f.set_index("obs"); f.index = pd.PeriodIndex(f.index, freq="Q")
FEND = f["ecnia"].last_valid_index()
E1, E2, E4 = 0.1584215605793791, 0.4118129978512995, 0.3075237404993435
D1, D2, D4 = 0.1561499403562654, -0.05999277989382532, 11.87185840275941
A_ECO, A_ECD, A_ECH = 0.735, 0.1055, 0.1595
ZQ = [0.07322397247249938, 0.02932374759217591, 0.00714849213690236, 0.00907784707291976]
rot = L(f.yhl + f.yht).diff()
r_eco = L(f.eco).diff() - ((E1 * L(f.qeco.shift(1) / f.eco.shift(1)) + E2 * L(f.eco).diff().shift(1) + f.zeco) * (1 - E4) + E4 * rot)
r_ecd = L(f.ecd).diff() - (D1 * L(f.qecd.shift(1) / f.ecd.shift(1)) + D2 * L(f.ecd).diff().shift(1) + f.zecd + D4 * f.zgapc2 / 400)
r_agg = L(f.ecnia).diff() - (A_ECO * L(f.eco).diff() + A_ECD * L(f.ecd).diff() + A_ECH * L(f.ech).diff())
re_eco, re_ecd = r_eco.loc["2015Q1":"2019Q4"].mean(), r_ecd.loc["2015Q1":"2019Q4"].mean()
def frbus_sim(start):
    eco, ecd, tot = f.eco.copy(), f.ecd.copy(), f.ecnia.copy()
    for t in pd.period_range(start + 1, FEND, freq="Q"):
        g_eco = (E1 * L(f.qeco[t - 1] / eco[t - 1]) + E2 * L(eco[t - 1] / eco[t - 2]) + f.zeco[t]) * (1 - E4) + E4 * rot[t] + re_eco
        g_ecd = D1 * L(f.qecd[t - 1] / ecd[t - 1]) + D2 * L(ecd[t - 1] / ecd[t - 2]) + f.zecd[t] + D4 * f.zgapc2[t] / 400 + re_ecd
        eco[t], ecd[t] = eco[t - 1] * np.exp(g_eco), ecd[t - 1] * np.exp(g_ecd)
        tot[t] = tot[t - 1] * np.exp(A_ECO * g_eco + A_ECD * g_ecd + A_ECH * L(f.ech[t] / f.ech[t - 1]) + r_agg[t])
    return tot / f.ecnia      # predicted / actual (real = nominal ratio)

# ---------------- income concepts ----------------
tax = d["taxes"] / d["pinc"]
inc = {"all": d["dpi"], "exid": d["dpi"] - d["prop_income"] * (1 - tax)}
C = d["pce"]; S0 = d["S"].shift(1)      # stock wealth at the start of the quarter ($ millions)

def anchor_window(anchor):
    return pd.period_range(f"{anchor}Q1", f"{anchor}Q4", freq="Q")

def models(incname, anchor="2019", end=FEND):
    Y = inc[incname]; W = anchor_window(anchor)
    out = pd.DataFrame(index=x.index); out["actual"] = C
    # rules on stock wealth: C = c0*Y + m*(S0 - s0*Y)
    c0 = (C / Y).loc[W].mean(); s0 = (S0 / Y).loc[W].mean()
    for m in (0.01, 0.03, 0.05):
        out[f"rule{int(m*100)}"] = c0 * Y + m * (S0 - s0 * Y)
    out["noeffect"] = c0 * Y
    # consumption function (levels), re-estimated on this income concept, 1955-2019
    xx = x.copy()
    xx["cy"] = C / Y
    for k in ["S", "H", "O"]:
        xx[f"{k}y"] = d[k].shift(1) / Y
    xx["tr_share"] = d["transfers"] / Y
    mfit = ols(xx["cy"].loc["1955Q1":"2019Q4"], xx[WEALTH3 + CTL].loc["1955Q1":"2019Q4"], lags=8)
    X = sm.add_constant(xx[WEALTH3 + CTL], has_constant="add")
    pred = X[mfit.params.index] @ mfit.params
    anc = (xx["cy"] - pred).loc[W].mean()
    out["cf"] = (pred + anc) * Y
    # consumption function, stocks frozen at anchor ratio (its stock wealth effect)
    Xf = X.copy(); Xf["Sy"] = xx.loc[W, "Sy"].mean()
    out["cf_nostock"] = (Xf[mfit.params.index] @ mfit.params + anc) * Y
    # FRB/US
    st = pd.Period(f"{anchor}Q4", "Q")
    ratio = frbus_sim(st)
    out["frbus"] = (ratio.reindex(out.index)) * C
    return out, dict(c0=c0, s0=s0, cf_S=100 * mfit.params["Sy"], cf_H=100 * mfit.params["Hy"])

rows = []
for incname in ("all", "exid"):
    for anchor in ("2019", "2022"):
        o, par = models(incname, anchor)
        W = anchor_window(anchor)
        Y = inc[incname]
        for endq in [str(FEND), "2026Q3"]:
            e = pd.Period(endq, "Q")
            base = lambda s: s.loc[W].mean()
            r = dict(income=incname, anchor=anchor, end=endq,
                     y_growth=100 * (Y[e] / base(Y) - 1), c_growth=100 * (C[e] / base(C) - 1),
                     s_ratio_anchor=base(S0 / Y), s_ratio_end=(S0 / Y)[e],
                     s_up_pct_y=100 * ((S0 / Y)[e] - base(S0 / Y)),          # rise in stock wealth relative to income, pct of income
                     s_up_dollars=(S0[e] - base(S0)) / 1e6, s_excess=(S0[e] - base(S0 / Y) * Y[e]) / 1e6,
                     cf_S=par["cf_S"], c0=par["c0"])
            # implied MPC that fits exactly
            r["mpc_fit"] = 100 * (C[e] - par["c0"] * Y[e]) / (S0[e] - base(S0 / Y) * Y[e])
            for k in ["frbus", "cf", "rule1", "rule3", "rule5", "noeffect"]:
                if pd.isna(o.loc[e, k]):
                    continue
                gap = (o.loc[e, k] - C[e]) / 1e3          # $ billions, annual rate
                cum_from = pd.Period("2022Q1", "Q") if anchor == "2019" else pd.Period("2023Q1", "Q")
                g = ((o[k] - C) / 1e3).loc[cum_from:e]
                g20 = ((o[k] - C) / 1e3).loc[pd.Period("2020Q1","Q"):e]
                r[f"{k}_growth"] = 100 * (o.loc[e, k] / base(C) - 1)
                r[f"{k}_gap_bn"] = gap; r[f"{k}_gap_pct"] = 100 * gap * 1e3 / C[e]
                r[f"{k}_cum_bn"] = g.sum() / 4; r[f"{k}_cum2020_bn"] = g20.sum() / 4
            rows.append(r)
        o.to_csv(f"output/r8_t2_paths_{incname}_{anchor}.csv")
res = pd.DataFrame(rows); res.to_csv("output/r8_table2.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 80)
for _, r in res.iterrows():
    print(f"\n== income={r.income} anchor={r.anchor} end={r.end}: Y +{r.y_growth:.1f}%  C +{r.c_growth:.1f}%  S/Y {r.s_ratio_anchor:.2f}->{r.s_ratio_end:.2f} (+{r.s_up_pct_y:.0f}% of income); dS ${r.s_up_dollars:.1f}T excess ${r.s_excess:.1f}T; MPC that fits {r.mpc_fit:.2f} cents; CF stock coef {r.cf_S:.2f}")
    for k in ["frbus", "cf", "rule1", "rule3", "rule5", "noeffect"]:
        if f"{k}_gap_bn" in r and not pd.isna(r.get(f"{k}_gap_bn")):
            print(f"   {k:9s} growth {r[f'{k}_growth']:5.1f}%  gap ${r[f'{k}_gap_bn']:7.0f}bn ({r[f'{k}_gap_pct']:4.1f}%)  cum ${r[f'{k}_cum_bn']:7.0f}bn  cum-from-2020 ${r[f'{k}_cum2020_bn']:7.0f}bn")
