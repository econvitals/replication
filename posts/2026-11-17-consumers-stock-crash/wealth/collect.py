"""Gather every computed number into one place and name them as expected.csv does.

Step 1 flattens every output into output/all_numbers.json, with a prefix for its source: r9. (cf_calc), x9.
(cf_extras), a1. (appendix_numbers), pn. (post_numbers), t2. (the rules table), q1p. (era estimates), q6log.
(the constant-elasticity model), roll. (rolling windows), exp. / r20. (expanding and rolling 20-year, with and
without 2020-21), oos. (the out-of-sample record), q7. (FRB/US since 2019) and d. (derived below).
Step 2 reads metric_map.csv (metric in expected.csv -> key in all_numbers.json, times a scale, optionally as an
absolute value) and writes output/numbers.json, which verify.py reads.

    python wealth/collect.py          (run from the package folder after the numbers steps)
"""
import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "output"
pool = {}


def flat(x, pre):
    if isinstance(x, dict):
        for k, v in x.items():
            flat(v, f"{pre}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            flat(v, f"{pre}[{i}]")
    elif isinstance(x, (int, float, str)) or x is None:
        pool[pre] = x


for f, pre in (("r9_cf_results.json", "r9"), ("r9_extras.json", "x9"), ("a1_numbers.json", "a1"), ("post_numbers.json", "pn")):
    flat(json.load(open(O / f)), pre)

t2 = pd.read_csv(O / "r8_table2.csv")
for _, r in t2.iterrows():
    for c in t2.columns[3:]:
        pool[f"t2.{r['income']}.{r['anchor']}.{r['end']}.{c}"] = r[c]
for _, r in pd.read_csv(O / "q1_periods.csv").iterrows():
    pool[f"q1p.{r['start']}.{r['end']}.{r['spec']}.{r['asset']}.{r['horizon']}"] = r["coef"]
    pool[f"q1p.{r['start']}.{r['end']}.{r['spec']}.{r['asset']}.{r['horizon']}.se"] = r["se"]
for _, r in pd.read_csv(O / "q6_log_out_of_sample.csv").iterrows():
    for c in ("gap_2019", "gap_latest4", "elasticity_w"):
        pool[f"q6log.{r['start']}.{c}"] = r[c]
for _, r in pd.read_csv(O / "r9_rolling_all.csv").iterrows():
    pool[f"roll.{r['W']}.{r['end']}.Sy"] = r["Sy"]
for f, pre in (("part3_r10_expanding.csv", "exp"), ("part3_r11_rolling20.csv", "r20")):
    for q, r in pd.read_csv(O / f, index_col=0).iterrows():
        for c in ("S", "Sx"):
            if c in r and pd.notna(r[c]):
                pool[f"{pre}.{q}.{c}"] = r[c]
for _, r in pd.read_csv(O / "r9_oos_rolling_origin.csv").iterrows():
    pool[f"oos.{r['anchor']}.gap_pct"] = r["gap_pct"]
    pool[f"oos.{r['anchor']}.stock_part_pct"] = r["stock_part_pct"]

# ---- derived numbers the post states as ranges, maxima or conversions
ro = pd.read_csv(O / "part3_r11_rolling20.csv", index_col=0)
pool["d.rolling20_min_2012_2019"] = ro.loc["2012Q1":"2019Q4", "S"].min()
pool["d.rolling20_max_2012_2019"] = ro.loc["2012Q1":"2019Q4", "S"].max()
ex = pd.read_csv(O / "part3_r10_expanding.csv", index_col=0)
pool["d.expanding_min_2000_2019"] = ex.loc["2000Q1":"2019Q4", "S"].min()
pool["d.expanding_max_2000_2019"] = ex.loc["2000Q1":"2019Q4", "S"].max()
rall = pd.read_csv(O / "r9_rolling_all.csv")
for W_, lab in ((80, "20"), (60, "15"), (40, "10")):
    s = rall[rall["W"] == W_].set_index("end")["Sy"]
    pool[f"d.rolling{lab}_min_from_2021q3"] = s.loc["2021Q3":].min()
    pool[f"d.rolling{lab}_max_from_2021q3"] = s.loc["2021Q3":].max()
    pool[f"d.rolling{lab}_min_2010_2019"] = s.loc["2010Q1":"2019Q4"].min()
    pool[f"d.rolling{lab}_max_2010_2019"] = s.loc["2010Q1":"2019Q4"].max()
    pool[f"d.rolling{lab}_min_before_1999"] = s.loc[:"1998Q4"].min()
    pool[f"d.rolling{lab}_max_before_1999"] = s.loc[:"1998Q4"].max()
rq = pd.read_csv(O / "r9_rule_fit_by_quarter.csv", index_col=0)["mpc_fit"]
pool["d.rule_fit_min_2024q4_on"] = rq.loc["2024Q4":].min()
pool["d.rule_fit_max_2024q4_on"] = rq.loc["2024Q4":].max()
q7 = pd.read_csv(O / "q7_scenarios.csv", index_col=0)
if {"actual", "frbus"} <= set(q7.columns):
    g = (q7["frbus"] / q7["actual"] - 1).abs() * 100
    pool["d.frbus_max_abs_gap_pct_since_2022q3"] = g.loc["2022Q3":].max()
a1 = json.load(open(O / "a1_numbers.json"))
pool["d.frbus_cons_4q_earn_pct"] = -a1["frbus"]["pce_pct"]["earn"]["4"]
pool["d.frbus_cons_4q_ret_pct"] = -a1["frbus"]["pce_pct"]["ret"]["4"]
pool["d.frbus_cons_20q_earn_pct"] = -a1["frbus"]["pce_pct"]["earn"]["20"]
pool["d.frbus_cons_20q_ret_pct"] = -a1["frbus"]["pce_pct"]["ret"]["20"]
pce_end = a1["pce_end_bn"]; lost = a1["table1"]["25"]["lost_bn"]
pool["d.rule1_cons_pct"] = 100 * 0.01 * lost / pce_end
pool["d.rule3_cons_pct"] = 100 * 0.03 * lost / pce_end
pool["d.frbus_cons_4q_earn_bn"] = -a1["frbus"]["pce_pct"]["earn"]["4"] / 100 * pce_end
pool["d.frbus_cons_20q_earn_bn"] = -a1["frbus"]["pce_pct"]["earn"]["20"] / 100 * pce_end
pool["d.rule1_cut_bn"] = 0.01 * lost

# ---- more derived numbers stated in the text
pan = pd.read_csv(O / "panel.csv", index_col=0)
pool["d.annuity_40y_3pct_cents"] = 100 * 0.03 / (1 - 1.03 ** -40)
for q, lab in (("1990Q4", "1990"), ("2019Q4", "2019"), ("2026Q2", "today")):
    pool[f"d.frbus_static_cents_{lab}"] = 18.74 * pan.loc[q, "pce"] / pan.loc[q, "nw"]   # 0.1874 x PCE / net worth, x 100
for y in (2019, 2022):
    pool[f"d.saving_rate_{y}"] = pan.loc[f"{y}Q1":f"{y}Q4", "saving_rate"].mean()
pool["d.pce_share_2020q2"] = 100 * pan.loc["2020Q2", "pce"] / pan.loc["2020Q2", "dpi"]
pool["d.dpi_2026q3_tn"] = pan.loc[a1["END"], "dpi"] / 1e6
pool["d.hh_stock_2026q2_tn"] = pan.loc["2026Q2", "eq_all"] / 1e6
pool["d.gdp_2026q3_tn"] = a1["GDP_NOW"] / 1e3
r9 = json.load(open(O / "r9_cf_results.json"))
pool["d.excess_stock_tn"] = r9["excess_S_tn"]
pool["d.cf_cum2020_tn"] = r9["cf_cum2020_bn"] / 1e3
pool["d.cf_cum2022_tn"] = r9["cf_cum2022_bn"] / 1e3
pool["d.cf_visible_share_2019_pct"] = 100 * r9["cf_stock_shown_bn"] / r9["cf_stock_effect_bn"]
pool["d.cf_pred_share_2026q3"] = 100 * pan.loc[a1["END"], "pce"] / pan.loc[a1["END"], "dpi"] + a1["anchors"]["2019"]["gap_pp"]
pool["d.cf_pred_change_pp"] = sum(r["contrib_pp"] for r in r9["decomp"])
pool["d.cf_pred_change_bn"] = sum(r["contrib_bn"] for r in r9["decomp"])
t2r = t2[(t2["income"] == "all") & (t2["anchor"] == 2019)].set_index("end")
pool["d.frbus_cum2020_tn"] = t2r.loc["2026Q2", "frbus_cum2020_bn"] / 1e3
pool["d.frbus_cum2022_tn"] = t2r.loc["2026Q2", "frbus_cum_bn"] / 1e3
sens = pd.DataFrame(r9["sens"]).set_index("spec")
s19 = sens["S_2019"].dropna(); s26 = sens["S_2026"].dropna()
odd = ["Home equity instead of gross housing", "Total net worth instead of the three types", "Income excluding interest and dividends"]
pool["d.a5_s19_min_ex3"] = s19.drop(odd).min(); pool["d.a5_s19_max_ex3"] = s19.drop(odd).max()
pool["d.a5_s19_outside_count"] = int(((s19 < 1.5) | (s19 > 2.5)).sum())
s26x = s26.drop("Income excluding interest and dividends")
pool["d.a5_s26_min"] = s26x.min(); pool["d.a5_s26_max"] = s26x.max()
both = sens.dropna(subset=["S_2019", "S_2026"]).drop("Income excluding interest and dividends")
cut = 100 * (1 - both["S_2026"] / both["S_2019"])
pool["d.a5_cut_min_pct"] = cut.min(); pool["d.a5_cut_max_pct"] = cut.max()
es = pd.DataFrame(a1["est_sens_income"])
pool["d.a9_gap_min"] = es["gap_pp_income"].min(); pool["d.a9_gap_max"] = es["gap_pp_income"].max()
pool["d.a9_shown_min"] = es["shown_pct"].min(); pool["d.a9_shown_max"] = es["shown_pct"].max()
an = pd.DataFrame(a1["anchor_sens_income"]).set_index("year")["gap_pp_income"]
pool["d.anchor_gap_min_2015_2017"] = an.loc[2015:2017].min(); pool["d.anchor_gap_max_2015_2017"] = an.loc[2015:2017].max()
oo = pd.read_csv(O / "r9_oos_rolling_origin.csv").set_index("anchor")["gap_pct"]
pool["d.oos_min_2009_2012"] = oo.loc[2009:2012].min(); pool["d.oos_max_2009_2012"] = oo.loc[2009:2012].max()
for i, b in enumerate(r9["breaks"]):
    pool[f"d.break{i}_date"] = int(b["break_date"][:4]) + int(b["break_date"][-1]) / 10
chow = json.load(open(O / "r9_extras.json"))["chow"]
for c in chow:
    pool[f"d.chow_{c['tau']}_{c['end']}_after"] = c["after"]; pool[f"d.chow_{c['tau']}_{c['end']}_wald"] = c["wald"]
pool["d.dpi_growth_2019_2026q3"] = t2r.loc[a1["END"], "y_growth"]
ser = pd.read_csv(O / "r9_series.csv", index_col=0)
pool["d.resid_2013"] = (ser["cy"] - ser["fit19"]).loc["2013Q1":"2013Q4"].mean()
rho = r9["dyn"]["1955Q1-2019Q4"]["pa_rho"]
pool["d.pa_speed_1955_2019"] = 1 - rho
pool["d.pa_share8"] = 1 - rho ** 8
b4 = a1["boe"][4]
pool["d.boe_dc_2015_19"] = b4["c1"] - b4["c0"]
pool["d.boe_ds_2015_19"] = b4["s1"] - b4["s0"]
# the whole market's rise from the end of 1986 to its August 1987 peak (the post's “nearly 40 percent” used the S&P 500)
wm = {}
for line in open(ROOT / "data" / "french_factors_daily.csv", encoding="utf-8", errors="ignore"):
    q_ = [x.strip() for x in line.split(",")]
    if len(q_) >= 5 and q_[0].isdigit() and len(q_[0]) == 8 and "19861231" <= q_[0] <= "19870825":
        wm[q_[0]] = (float(q_[1]) + float(q_[4])) / 100
dyv = {r["month"]: float(r["dividend_yield"]) for r in csv.DictReader(open(ROOT / "data" / "shiller_dividend_yield_as_used.csv"))}
lvl = 1.0
for k in sorted(wm):
    if k > "19861231":
        lvl *= 1 + wm[k] - dyv[f"{k[:4]}-{k[4:6]}"] / 252
pool["d.whole_market_rise_1987_to_aug_peak_pct"] = 100 * (lvl - 1)

json.dump(pool, open(O / "all_numbers.json", "w"), indent=0, default=float)

# ---- step 2: the names expected.csv uses
nums, missing = {}, []
for r in csv.DictReader(open(ROOT / "metric_map.csv", encoding="utf-8")):
    k = r["key"]
    if k not in pool:
        missing.append(k)
        continue
    v = pool[k]
    if isinstance(v, str):
        nums[r["metric"]] = v
        continue
    v = float(v) * float(r["scale"] or 1)
    nums[r["metric"]] = abs(v) if r.get("abs") == "1" else v
json.dump(nums, open(O / "numbers.json", "w"), indent=1, default=float)
print(f"collect: {len(pool)} numbers computed, {len(nums)} named for expected.csv" + (f"; MISSING KEYS {missing}" if missing else ""))
