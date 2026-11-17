"""County stock market wealth relative to labor income, quarterly: S(a,t) in Chodorow-Reich, Nenov and Simsek.

    python 06_wealth.py <cns dir>        (paperwright venv; needs out/ from 02, 03 and 05)

  1. Taxable stock wealth = county dividends (IRS SOI, consistent filing basis from 02) / county dividend yield.
     County yield = the wealth-weighted average of the age-bin yields in the paper's Table A.1 for the
     county's Census region (weights: households by age of head x SCF mean taxable stock wealth by age),
     scaled each year so that aggregate dividends / aggregate taxable wealth = the market dividend yield
     (Shiller S&P Composite: December trailing-12-month dividends / average price over the year; the paper
     uses CRSP value-weighted).
  2. Total stock wealth = b x taxable + households x (age-of-head effects + college effect), the SCF
     wave-by-wave regression from 05 (paper Table A.3 column 2), converted to current dollars with CPI-U.
  3. Quarterly: wealth / average price of the year ("shares") and IRS wages are interpolated linearly with
     each tax year centered at mid-year; wealth at the end of a quarter = shares x the price in the quarter's
     last month. After mid-2023 (last IRS year) shares are held and wages grow with national compensation.
     S = wealth / annual wages.
  4. Sample flags: the paper's late-filer counties (from 02) and the top 5% of counties by the share of
     private employment at firms with 500+ employees (QWI, mean of 2008/2012/2016/2019 Q1).
Writes out/county_wealth_q.parquet and out/wealth_checks.txt.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

D = Path(sys.argv[1]); OUT = D / "out"; RAW = D / "raw"
log = open(OUT / "wealth_checks.txt", "w")
def say(*a):
    print(*a); print(*a, file=log, flush=True)

YLD = {1: [2.81, 2.48, 2.65, 3.00, 2.91], 2: [2.21, 2.25, 2.27, 2.39, 2.73],
       3: [2.28, 2.43, 2.51, 2.40, 2.96], 4: [2.51, 2.50, 2.50, 2.82, 3.27]}      # Table A.1 cols 1-4, x100
YB = ["lt35", "35_44", "45_54", "55_64", "65p"]
HB = ["lt25", "25_34", "35_44", "45_54", "55_64", "65p"]

irs = pd.read_parquet(OUT / "irs_county_adj.parquet")
dem = pd.read_parquet(OUT / "county_demog.parquet")
scf = pd.read_csv(OUT / "scf_by_year.csv", index_col=0)
agg = pd.read_csv(OUT / "agg_quarterly.csv", index_col=0); agg.index = pd.PeriodIndex(agg.index, freq="Q")

# ---- market yield and prices by year
a = agg.copy(); a["year"] = a.index.year
ann = a.groupby("year").agg(pbar=("pm", "mean"), d_dec=("dm", "last"), cpi=("cpi", "mean"), nq=("pm", "count"))
ann["dp"] = ann.d_dec / ann.pbar
say("market dividend yield (Shiller), selected years:", ann.dp.loc[[1990, 2000, 2008, 2015, 2019, 2023]].round(4).to_dict())

# ---- county yields
d = irs.merge(dem, on=["fips", "year"], how="left")
miss = d[d.region.isna() | d.H.isna()]
say("IRS county-years without SEER demographics:", len(miss), "counties:", miss.fips.nunique(), "dividends share:",
    round(miss["div"].sum() / d["div"].sum(), 4))
d = d.dropna(subset=["region", "H"]).copy()
d = d.merge(scf[[f"deq_{b}" for b in YB] + ["b_deq", "d_col"] + [f"g_{b}" for b in HB]], left_on="year", right_index=True, how="left")
wts = np.column_stack([d[f"Hy_{b}"] * d[f"deq_{b}"] for b in YB]); wts = wts / wts.sum(axis=1, keepdims=True)
ytab = np.array([YLD[int(r)] for r in d.region]) / 100
d["yraw"] = (wts * ytab).sum(axis=1)
d = d.merge(ann[["dp", "pbar", "cpi"]], left_on="year", right_index=True, how="left")
ok = d["div"] > 0
c = (d[ok].assign(w=d["div"] / d.yraw).groupby("year").w.sum() / d[ok].groupby("year")["div"].sum()) * ann.dp
d["yld"] = d.yraw * d.year.map(c)
say("county yield / market yield, distribution across county-years:", (d.yld / d.dp).describe(percentiles=[.05, .5, .95]).round(3).to_dict())

# ---- taxable and total stock wealth (dollars)
d["taxw"] = d["div"] * 1000 / d.yld
cpi22 = ann.cpi.loc[2022]
d["demo"] = sum(d[f"H_{b}"] * d[f"g_{b}"] for b in HB) + d.H * d.col.fillna(d.col.mean()) * d.d_col
d["totw"] = d.b_deq * d.taxw + d.demo * d.cpi / cpi22
d["totw"] = d.totw.clip(lower=0)
nat = d.groupby("year")[["taxw", "totw"]].sum() / 1e12
nat["div_bn"] = d.groupby("year")["div"].sum() / 1e6
say("national taxable and total stock wealth ($ trillion):"); say(nat.round(2).to_string())
d["shares"] = d.totw / d.pbar
d["shares_tax"] = d.taxw / d.pbar
d["taxw_flat"] = d["div"] * 1000 / d.dp
d["shares_flat"] = (d.b_deq * d.taxw_flat + d.demo * d.cpi / cpi22).clip(lower=0) / d.pbar
d["wages_d"] = d.wages * 1000

# ---- quarterly interpolation (tax year at mid-year)
qs = pd.period_range("1989Q1", "2026Q2", freq="Q")
tau_q = qs.year + (qs.quarter - 0.5) / 4
yrs = np.arange(1989, 2024); tau_y = yrs + 0.5
def interp(mat):        # mat: counties x years -> counties x quarters, flat outside
    out = np.empty((mat.shape[0], len(qs)))
    for i in range(mat.shape[0]):
        out[i] = np.interp(tau_q, tau_y, mat[i])
    return out
sh = d.pivot(index="fips", columns="year", values="shares").reindex(columns=yrs)
wg = d.pivot(index="fips", columns="year", values="wages_d").reindex(columns=yrs)
# fill interior gaps by interpolation across years, edges by nearest
sh = sh.T.interpolate(limit_area="inside").bfill().ffill().T; wg = wg.T.interpolate(limit_area="inside").bfill().ffill().T
shq = interp(sh.values); wgq = interp(wg.values)
def qpanel(col):
    m = d.pivot(index="fips", columns="year", values=col).reindex(index=sh.index, columns=yrs)
    m = m.T.interpolate(limit_area="inside").bfill().ffill().T
    return interp(m.values)
alt = {"tax": qpanel("shares_tax"), "flat": qpanel("shares_flat"), "annual": qpanel("totw")}
# after mid-2023: wages grow with national compensation (BEA, quarterly)
lab = agg.lab.reindex(qs)
base = lab.loc[pd.Period("2023Q2"):pd.Period("2023Q3")].mean()
late = tau_q > 2023.5
growth = (lab / base).values
wgq[:, late] = wgq[:, late] * growth[late][None, :]
pm = agg.pm.reindex(qs).values
W = shq * pm[None, :]
S = np.where(wgq > 0, W / np.where(wgq > 0, wgq, 1), np.nan)
safe = np.where(wgq > 0, wgq, np.nan)
S_tax = alt["tax"] * pm[None, :] / safe
S_flat = alt["flat"] * pm[None, :] / safe
S_annual = alt["annual"] / safe       # wealth interpolated in dollars, not revalued at the quarter's price
cw = pd.DataFrame(dict(fips=np.repeat(sh.index.values, len(qs)), q=np.tile(qs.astype(str), len(sh)),
                       S=S.ravel(), W=W.ravel(), wages_ann=wgq.ravel(),
                       S_tax=S_tax.ravel(), S_flat=S_flat.ravel(), S_annual=S_annual.ravel()))

# ---- flags and weights
flag = irs.groupby("fips").late_filer_flag.first()
rows = []
for f in sorted((RAW / "census" / "api").glob("qwi_*.json")):
    j = json.load(open(f)); rows += [dict(zip(j[0], r)) for r in j[1:]]
qw = pd.DataFrame(rows); qw["Emp"] = pd.to_numeric(qw.Emp, errors="coerce"); qw["fips"] = qw.state + qw.county
qw = qw.pivot_table(index=["fips", "year"], columns="firmsize", values="Emp", aggfunc="first")
qw["share"] = qw["5"] / qw["0"]
large = qw.groupby("fips").share.mean()
cut = large.quantile(0.95)
say(f"large-firm (500+) employment share: counties {len(large)}, median {large.median():.3f}, 95th pct cut {cut:.3f}")
p10 = dem[dem.year == 2010].set_index("fips")["pop2010"]
reg = dem.groupby("fips").region.first()
cw["late_filer"] = cw.fips.map(flag).fillna(False).astype(bool)
cw["large_share"] = cw.fips.map(large)
cw["large_top5"] = cw.large_share > cut
cw["pop2010"] = cw.fips.map(p10)
cw["region"] = cw.fips.map(reg)
cw.to_parquet(OUT / "county_wealth_q.parquet", index=False)
say("county-quarter rows", len(cw), "counties", cw.fips.nunique(), "| late filers", int(flag.sum()), "| top-5% large-firm", int((large > cut).sum()),
    "| missing large-firm share", int(cw.groupby('fips').large_share.first().isna().sum()))
pw = cw.dropna(subset=["pop2010"])
for q in ["1990Q4", "2000Q4", "2008Q4", "2015Q4", "2019Q4", "2021Q4", "2024Q4"]:
    x = pw[pw.q == q]
    say(q, "S: pop-weighted mean", round(np.average(x.S, weights=x.pop2010), 2), "| p10/p50/p90",
        [round(v, 2) for v in x.S.quantile([.1, .5, .9])], "| aggregate W/wages", round(x.W.sum() / x.wages_ann.sum(), 2))
