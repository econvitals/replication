"""Numbers for the online appendix to Part 3 of the AI-bubble series ("Consumers Can Handle a Stock Crash"),
2026-11-16. Adds what the technical note (12_r9_*) did not compute: the 2015-2019 anchor, gaps in percent of
income (the post's unit), the back-of-envelope arithmetic for every base period, the FRB/US marginal
propensities implied by the Simulator runs, and the GDP paths behind the post's Table 1.

Run from a folder holding code/ and output/ (chartbook venv). Needs output/panel.csv (01_build_data.py),
output/r9_cf_results.json and r9_series.csv (12_r9_cf_calc.py), output/r8_table2.csv (11_r8_table2.py) and the
FRB/US Simulator's stored runs (econvitals-site tools/macro-simulator/data/runs, or SIM_RUNS=<dir>).
Writes output/a1_numbers.json."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, "wealth")
import numpy as np, pandas as pd
from common import load, add_basics

OUT = Path("output")
d = load(OUT); x = add_basics(d)
R = json.load(open(OUT / "r9_cf_results.json"))
ser = pd.read_csv(OUT / "r9_series.csv", index_col=0)
END = R["END"]
Y_END = float(d.loc[END, "dpi"]) / 1e3            # $bn, SAAR
C_END = float(d.loc[END, "pce"]) / 1e3
N = {"END": END, "dpi_end_bn": Y_END, "pce_end_bn": C_END}

# ------------------------------------------------------------------ the 1955-2019 model, anchored three ways
b = R["main"]["1955Q1-2019Q4"]
bS = b["Sy"] / 100 if b["Sy"] > 0.5 else b["Sy"]  # stored in cents
bS = R["main"]["1955Q1-2019Q4"]["Sy"] / 100
resid = ser["cy"] - ser["fit19"]
def yr(a, z):
    return resid.loc[f"{a}Q1":f"{z}Q4"].mean()
anchors = {"2019": yr(2019, 2019), "2015–2019": yr(2015, 2019), "2023": yr(2023, 2023), "2024": yr(2024, 2024),
           "2010–2019": yr(2010, 2019)}
cy_end, fit_end, Sy_end = ser.loc[END, "cy"], ser.loc[END, "fit19"], ser.loc[END, "Sy"]
anc = {}
for k, a in anchors.items():
    y0, y1 = (int(k[:4]), int(k[-4:]))
    s0 = ser.loc[f"{y0}Q1":f"{y1}Q4", "Sy"].mean()
    gap_pp = fit_end + a - cy_end                   # predicted minus actual, points of income
    exp_bn = bS * (Sy_end - s0) * Y_END             # what the model expects from stocks above the anchor ratio
    anc[k] = dict(anchor_pp=a, gap_pp=gap_pp, gap_bn=gap_pp / 100 * Y_END, gap_pct_spending=gap_pp / cy_end * 100,
                  s0=s0, stock_exp_bn=exp_bn, stock_visible_bn=exp_bn - gap_pp / 100 * Y_END,
                  visible_cents=(exp_bn - gap_pp / 100 * Y_END) / ((Sy_end - s0) * Y_END) * 100)
N["anchors"] = anc
N["cum2020_bn"] = R["cf_cum2020_bn"]; N["cum2020_pct_income"] = R["cf_cum2020_bn"] / Y_END * 100
N["cum2022_bn"] = R["cf_cum2022_bn"]

# technical-note tables re-expressed in percent of income
N["anchor_sens_income"] = [dict(r, gap_pp_income=r["gap_bn"] / Y_END * 100) for r in R["anchor_sens"]]
N["est_sens_income"] = [dict(r, gap_pp_income=r["gap_bn"] / Y_END * 100) for r in R["est_sens"]]

# ------------------------------------------------------------------ back-of-envelope: every base period
cy = x["cy"] * 100; Sy = x["Sy"]; Hy = x["Hy"]
end_avg = slice("2026Q1", END)
bases = [("2000–2019", 2000, 2019), ("2010–2019", 2010, 2019), ("2015–2019", 2015, 2019), ("2015", 2015, 2015),
         ("2016", 2016, 2016), ("2017", 2017, 2017), ("2018", 2018, 2018), ("2019", 2019, 2019), ("2022", 2022, 2022),
         ("2023", 2023, 2023), ("2024", 2024, 2024)]
bH = R["main"]["1955Q1-2019Q4"]["Hy"] / 100
boe = []
for lab, a, z in bases:
    sl = slice(f"{a}Q1", f"{z}Q4")
    c0, s0, h0 = cy.loc[sl].mean(), Sy.loc[sl].mean(), Hy.loc[sl].mean()
    for which, sel in (("2026Q1–Q3", end_avg), ("2026Q3", slice(END, END))):
        c1, s1, h1 = cy.loc[sel].mean(), Sy.loc[sel].mean(), Hy.loc[sel].mean()
        boe.append(dict(base=lab, end=which, c0=c0, c1=c1, s0=s0, s1=s1, h0=h0, h1=h1,
                        cents=(c1 - c0) / (s1 - s0), cents_net_housing=((c1 - c0) - 100 * bH * (h1 - h0)) / (s1 - s0)))
N["boe"] = boe

# ------------------------------------------------------------------ FRB/US: implied cents per dollar, Table 1 paths
SIM = Path("data/simulator")      # frozen subset of the Econvitals Macroeconomic Simulator's stored runs
cur = json.load(open(SIM / "current.json"))["stock_wealth"]
K = cur["factor"]
def frbus(shock, var):
    r = json.load(open(SIM / f"{shock}_var_no_fixed.json"))["runs"]["3|balanced|perm"][var]
    return [v * K * 25 / 30 for v in r]                    # stored size 3 = a 30 percent fall; scaled to 25 percent, today's wealth
# $bn: household stock wealth at the end of 2026Q2 (Financial Accounts, directly and indirectly held) and nominal GDP
# in 2026Q3 (BEA). (The research run typed 74,005 for the first; the published release says 74,027 — no printed number moves.)
S_NOW = float(d.loc["2026Q2", "eq_all"]) / 1e3
_g = pd.read_csv("data/bea_gdp_quarterly.csv", index_col=0)
GDP_NOW = float(_g.loc["2026Q3", "gdp_nominal [T10105/A191RC]"]) / 1e3
LOST = S_NOW * 0.25
rho = R["dyn"]["1955Q1-2019Q4"]["pa_rho"]
fr = {k: {v: frbus(sh, v) for v in ("xgdp", "ecnia")} for k, sh in (("earn", "stocks_earn"), ("ret", "stocks"))}
N["frbus"] = dict(K=K, stock_share_today=cur["share_today"], stock_share_baseline=cur["share_baseline"],
                  cents_4q={k: -fr[k]["ecnia"][4] / 100 * C_END / LOST * 100 for k in fr},
                  cents_20q={k: -fr[k]["ecnia"][20] / 100 * C_END / LOST * 100 for k in fr},
                  pce_pct={k: {h: fr[k]["ecnia"][h] for h in (1, 4, 8, 12, 20)} for k in fr},
                  gdp_pct={k: {h: fr[k]["xgdp"][h] for h in (1, 4, 8, 12, 20)} for k in fr})
t1 = {}
for pct in (25, 35, 50):
    lost = S_NOW * pct / 100; f = pct / 25
    row = dict(lost_bn=lost)
    for h in (4, 8, 12, 20):
        row[f"frbus_earn_{h}"] = -fr["earn"]["xgdp"][h] * f
        row[f"frbus_ret_{h}"] = -fr["ret"]["xgdp"][h] * f
        row[f"cf_{h}"] = lost * bS / GDP_NOW * 100 * (1 - rho ** h)
    row["r1"] = lost * 0.01 / GDP_NOW * 100; row["r3"] = lost * 0.03 / GDP_NOW * 100; row["cf_all"] = lost * bS / GDP_NOW * 100
    t1[pct] = row
N["table1"] = t1; N["rho19"] = rho; N["share4"] = 1 - rho ** 4; N["S_NOW"] = S_NOW; N["GDP_NOW"] = GDP_NOW

# ------------------------------------------------------------------ the simple rules and FRB/US since 2019 (post Table A1)
t2 = pd.read_csv(OUT / "r8_table2.csv")
N["rules"] = t2.to_dict(orient="records")

# ------------------------------------------------------------------ levels and ratios quoted in the text
N["ratios"] = {q: dict(cy=float(cy.loc[q]), Sy=float(Sy.loc[q]), Hy=float(Hy.loc[q])) for q in ("2000Q1", "2007Q4", "2019Q4", END)}
N["ratios"]["2015–2019"] = dict(cy=float(cy.loc["2015Q1":"2019Q4"].mean()), Sy=float(Sy.loc["2015Q1":"2019Q4"].mean()))
N["ratios"]["2026Q1–Q3"] = dict(cy=float(cy.loc[end_avg].mean()), Sy=float(Sy.loc[end_avg].mean()))
N["saving_rate"] = {str(yy): float(d.loc[f"{yy}Q1":f"{yy}Q4", "saving_rate"].mean()) if "saving_rate" in d else None
                    for yy in (2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024)}

json.dump(N, open(OUT / "a1_numbers.json", "w"), indent=1, default=float)
pr = lambda *a: print(*a)
pr("anchors:"); [pr(" ", k, {kk: round(vv, 3) for kk, vv in v.items()}) for k, v in anc.items()]
pr("cum2020 % income", round(N["cum2020_pct_income"], 1))
pr("boe:"); [pr(" ", r["base"], r["end"], round(r["cents"], 2), "net housing", round(r["cents_net_housing"], 2), round(r["c0"], 2), round(r["c1"], 2), round(r["s0"], 2), round(r["s1"], 2)) for r in boe]
pr("frbus cents", {k: round(v, 2) for k, v in N["frbus"]["cents_4q"].items()}, {k: round(v, 2) for k, v in N["frbus"]["cents_20q"].items()})
pr("table1 25%", {k: round(v, 2) for k, v in t1[25].items()})
pr("anchor_sens % income", [(r["year"], round(r["gap_pp_income"], 2)) for r in N["anchor_sens_income"]])
pr("est_sens % income", [(r["sample"], round(r["gap_pp_income"], 2)) for r in N["est_sens_income"]])
