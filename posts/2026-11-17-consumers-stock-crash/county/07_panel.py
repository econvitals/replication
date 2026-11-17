"""Regression panel for equation (1) of Chodorow-Reich, Nenov and Simsek (2021): county x quarter.

    python 07_panel.py <cns dir>        (paperwright venv; needs out/qcew, out/county_wealth_q.parquet, out/agg_quarterly.csv)

Outcomes (QCEW, not seasonally adjusted, suppressed cells missing):
  emp_all, pay_all   county total covered (all ownerships)
  emp_nt,  pay_nt    private NAICS 44-45 + 72 (retail; accommodation and food services)
  emp_tr,  pay_tr    private NAICS 11 + 21 + 31-33
  A sector absent from a county counts as zero; a suppressed sector makes the sum missing.
For each outcome y and horizon h: d{y}_h = ln y(t+h) - ln y(t-1).
Regressors (t = quarter of the return):
  SR      = S(t-1) x R(t), R = change in the quarter-average S&P Composite price (Shiller monthly), which matches the
          moments of the return in the paper's Table A.4 (mean 0.019, s.d. 0.067; end-of-quarter CRSP total returns
          have s.d. 0.083); portfolio betas = 1. SRtot uses the end-of-quarter CRSP value-weighted total return
          (Ken French Mkt-RF + RF) instead.
  SR_l1..SR_l8 = SR(t-j)
  S_bond, S_hpi, S_lab, S_bus = S(t-1) x [5-year zero holding return, d ln Case-Shiller national,
          ln(sum_{j=0..11} beta^-j A(t+j)) - ln A(t-1) for BEA compensation and nonfarm proprietors' income;
          where t+11 is beyond the data the sum is truncated and scaled up by the missing discount weights]
  bartik_h = sum_i [E(a,i,t-1)/E(a,t-1)] x [E(i,t+h) - E(i,t-1)]/E(i,t-1), private NAICS 3-digit; national
          industry employment seasonally adjusted by ratio to a centered moving average
Writes out/panel.parquet.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

D = Path(sys.argv[1]); OUT = D / "out"
H = list(range(-4, 11)); H.remove(-1)
QS = pd.period_range("1989Q1", "2026Q1", freq="Q")

# ---------------------------------------------------------------- QCEW
parts3, nat3, cty = [], [], []
for y in range(1990, 2027):
    x = pd.read_parquet(OUT / "qcew" / f"qcew_{y}.parquet")
    x["q"] = pd.PeriodIndex.from_fields(year=x.year.values, quarter=x.qtr.values, freq="Q")
    cty.append(x[x.agglvl_code.isin([70, 74])])
    parts3.append(x[x.agglvl_code == 75][["area_fips", "industry_code", "q", "emp"]])
    nat3.append(x[x.agglvl_code == 15][["industry_code", "q", "emp"]])
cty = pd.concat(cty)
tot = cty[(cty.agglvl_code == 70) & (cty.own_code == "0")].set_index(["area_fips", "q"])[["emp", "wages"]]
tot.columns = ["emp_all", "pay_all"]
sec = cty[(cty.agglvl_code == 74) & (cty.own_code == "5")]
# faster NaN-propagating sums
def group_fast(inds, tag):
    g = sec[sec.industry_code.isin(inds)].copy()
    g["emp_na"] = g.emp.isna(); g["pay_na"] = g.wages.isna()
    s = g.groupby(["area_fips", "q"]).agg(emp=("emp", "sum"), pay=("wages", "sum"), emp_na=("emp_na", "any"), pay_na=("pay_na", "any"))
    s.loc[s.emp_na, "emp"] = np.nan; s.loc[s.pay_na, "pay"] = np.nan
    return s[["emp", "pay"]].rename(columns={"emp": f"emp_{tag}", "pay": f"pay_{tag}"})
nt = group_fast(["44-45", "72"], "nt"); tr = group_fast(["11", "21", "31-33"], "tr")
g0 = sec[sec.industry_code.isin(["44-45", "72"])].groupby(["area_fips", "q"])[["emp", "wages"]].sum()
g0.columns = ["emp_nt0", "pay_nt0"]                          # suppressed sectors counted as zero (diagnostic)
r0 = sec[sec.industry_code == "44-45"].set_index(["area_fips", "q"])[["emp", "wages"]]; r0.columns = ["emp_ret", "pay_ret"]
f0 = sec[sec.industry_code == "72"].set_index(["area_fips", "q"])[["emp", "wages"]]; f0.columns = ["emp_food", "pay_food"]
out = tot.join(nt, how="left").join(tr, how="left").join(g0, how="left").join(r0, how="left").join(f0, how="left").reset_index().rename(columns={"area_fips": "fips"})
out = out[out.fips.str[2:] != "000"]
out = out[out.fips.str[:2].astype(int) <= 56]
fips = sorted(out.fips.unique())
idx = pd.MultiIndex.from_product([fips, QS], names=["fips", "q"])
Y = out.set_index(["fips", "q"]).reindex(idx)
ycols = ["emp_all", "pay_all", "emp_nt", "pay_nt", "emp_tr", "pay_tr", "emp_nt0", "pay_nt0", "emp_ret", "pay_ret", "emp_food", "pay_food"]
L = np.log(Y[ycols].where(Y[ycols] > 0))
print("QCEW county-quarters:", len(Y), "counties:", len(fips), flush=True)

# ---------------------------------------------------------------- Bartik
n3 = pd.concat(nat3).pivot_table(index="q", columns="industry_code", values="emp").reindex(QS)
ln = np.log(n3)
ma = ln.rolling(4, center=True).mean().rolling(2).mean().shift(-1)        # centered 2x4 moving average
seas = (ln - ma).groupby(ln.index.quarter).transform("mean")
n3sa = np.exp(ln - seas)
c3 = pd.concat(parts3)
c3 = c3[c3.area_fips.str[2:] != "000"]
c3 = c3[c3.industry_code.isin(n3sa.columns)]
c3["emp"] = c3.emp.fillna(0.0)
c3["sh"] = c3.emp / c3.groupby(["area_fips", "q"]).emp.transform("sum")
inds = list(n3sa.columns)
pos = {q: i for i, q in enumerate(QS)}
bparts = []
for qprev, g in c3.groupby("q"):
    i0 = pos.get(qprev)
    if i0 is None or i0 + 1 >= len(QS): continue
    M = g.pivot_table(index="area_fips", columns="industry_code", values="sh", fill_value=0.0).reindex(columns=inds, fill_value=0.0)
    res = pd.DataFrame(index=M.index)
    for h in H:
        j = i0 + 1 + h
        if j < 0 or j >= len(QS): continue
        gr = (n3sa.iloc[j] / n3sa.iloc[i0] - 1).fillna(0.0)
        res[f"bartik_h{h}"] = M.values @ gr.values
    res["q"] = QS[i0 + 1]
    bparts.append(res.reset_index().rename(columns={"area_fips": "fips"}))
bart = pd.concat(bparts).set_index(["fips", "q"]).reindex(idx)
print("Bartik done", flush=True)

# ---------------------------------------------------------------- national series
agg = pd.read_csv(OUT / "agg_quarterly.csv", index_col=0); agg.index = pd.PeriodIndex(agg.index, freq="Q")
beta = 1.03 ** 0.25
def fwd(a):
    a = a.dropna(); last = a.index.max(); full = sum(beta ** -j for j in range(12))
    out = pd.Series(np.nan, index=a.index)
    for i, t in enumerate(a.index):
        if i == 0: continue
        J = min(11, (last - t).n)
        w = sum(beta ** -j for j in range(J + 1))
        s = sum(a.iloc[i + j] / beta ** j for j in range(J + 1)) * full / w
        out.iloc[i] = np.log(s) - np.log(a.iloc[i - 1])
    return out
shl = pd.read_excel(D / "raw" / "agg" / "ie_data_new.xls", sheet_name="Data", header=None, skiprows=8).iloc[:, :2]
shl.columns = ["date", "P"]; shl = shl[pd.to_numeric(shl.date, errors="coerce").notna()].copy()
yy = shl.date.astype(float).astype(int); mm = ((shl.date.astype(float) - yy) * 100).round().astype(int)
shl["q"] = pd.PeriodIndex.from_fields(year=yy.values, quarter=((mm - 1) // 3 + 1).values, freq="Q")
pq = shl.groupby("q").P.apply(lambda v: pd.to_numeric(v, errors="coerce").mean())
R_avg = (pq / pq.shift(1) - 1)
nat = pd.DataFrame(dict(R=R_avg.reindex(agg.index), R_tot=agg.rm, bond=agg.bond5, hpi=agg.dhpi, lab=fwd(agg.lab), bus=fwd(agg.bus)))
print("lab_fwd (paper definition, truncated at the end) last 6:", nat.lab.dropna().tail(6).round(3).to_dict(), flush=True)

# ---------------------------------------------------------------- wealth and shocks
cw = pd.read_parquet(OUT / "county_wealth_q.parquet"); cw["q"] = pd.PeriodIndex(cw.q, freq="Q")
S = cw.set_index(["fips", "q"]).S.reindex(idx)
Sl = S.groupby(level=0).shift(1)                          # S(t-1)
Rt = pd.Series(nat.R.reindex(QS).values, index=QS)
qv = idx.get_level_values(1)
P = pd.DataFrame(index=idx)
P["S_l1"] = Sl
P["R"] = Rt.reindex(qv).values
P["SR"] = P.S_l1 * P.R
P["R_tot"] = nat.R_tot.reindex(qv).values
P["SRtot"] = P.S_l1 * P.R_tot
for j in range(1, 9):
    P[f"SR_l{j}"] = P.SR.groupby(level=0).shift(j)
    P[f"SRtot_l{j}"] = P.SRtot.groupby(level=0).shift(j)
for v in ["bond", "hpi", "lab", "bus"]:
    P[f"S_{v}"] = P.S_l1 * nat[v].reindex(qv).values
for c in ycols:
    base = L[c].groupby(level=0).shift(1)                 # ln y(t-1)
    for h in H:
        P[f"d{c}_h{h}"] = L[c].groupby(level=0).shift(-h) - base
for h in H:
    P[f"bartik_h{h}"] = bart[f"bartik_h{h}"].values if f"bartik_h{h}" in bart else np.nan
meta = cw.groupby("fips")[["late_filer", "large_top5", "pop2010", "region", "large_share"]].first()
P = P.reset_index()
P = P.merge(meta, left_on="fips", right_index=True, how="left")
P["state"] = P.fips.str[:2]
P["q"] = P.q.astype(str)
P["stq"] = P.state + "_" + P.q
P = P[P.q >= "1989Q1"]
P.to_parquet(OUT / "panel.parquet", index=False)
print("panel rows", len(P), "with SR", int(P.SR.notna().sum()), "| columns", len(P.columns))
x = P[(P.q >= "1992Q1") & (P.q <= "2014Q4")]
print("1992Q1-2014Q4 county-quarters with SR and dpay_nt_h7:", int((x.SR.notna() & x.dpay_nt_h7.notna()).sum()))
