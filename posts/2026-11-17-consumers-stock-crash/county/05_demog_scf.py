"""County demographics and the SCF relationships used to turn taxable dividends into total stock wealth.

    python 05_demog_scf.py <cns dir>        (paperwright venv; reads raw/, writes out/)

Follows Chodorow-Reich, Nenov and Simsek (2021), online appendix A.1.2-A.1.3, with public stand-ins:
  * County population by age: SEER county file (raw/census/seer20.txt.gz, 20 age groups; 18 = 85-89, 19 = 90+), 1969-2024.
  * Households by age of head: SEER adults in each bin x the national headship rate for that bin,
    which is SCF households in the bin / SEER national population in the bin (interpolated between waves).
  * College share: share of adults 25+ with a bachelor's degree or more, Census 2000 SF3 and ACS
    5-year (2008-12, 2011-15, 2016-20, 2019-23), interpolated; before 2000 each county keeps its 2000
    gap to the national SCF head college share.
  * SCF, every wave 1989-2022 (summary extract, constant 2022 dollars):
      - mean taxable stock wealth (DEQ) by the five age bins of the dividend-yield table (A.1.2 weights);
      - per-wave regression of total stock wealth (EQUITY) on taxable stock wealth (DEQ), head-age bins
        and a college-degree dummy (A.3 column 2), weighted, no constant + six age bins.
Writes out/county_demog.parquet (fips x year) and out/scf_waves.csv, out/scf_by_year.csv.
"""
import gzip, json, sys, tempfile, zipfile
from pathlib import Path
import numpy as np, pandas as pd, pyreadstat

D = Path(sys.argv[1]); RAW, OUT = D / "raw", D / "out"
log = open(OUT / "demog_checks.txt", "w")
def say(*a):
    print(*a); print(*a, file=log, flush=True)

HEAD_BINS = ["lt25", "25_34", "35_44", "45_54", "55_64", "65p"]      # SCF regression (A.3)
YLD_BINS = ["lt35", "35_44", "45_54", "55_64", "65p"]                 # dividend-yield table (A.1)
SEER_GROUP = {5: "lt25", 6: "25_34", 7: "25_34", 8: "35_44", 9: "35_44", 10: "45_54", 11: "45_54",
              12: "55_64", 13: "55_64", 14: "65p", 15: "65p", 16: "65p", 17: "65p", 18: "65p", 19: "65p"}

def head_bin(age):
    return np.select([age < 25, age < 35, age < 45, age < 55, age < 65], HEAD_BINS[:5], "65p")

# ------------------------------------------------------------------ SEER
rows = []
with gzip.open(RAW / "census" / "seer20.txt.gz", "rt") as f:
    for line in f:
        y = int(line[0:4])
        if y < 1988: continue
        rows.append((y, line[6:11], int(line[16:18]), int(line[18:26])))
s = pd.DataFrame(rows, columns=["year", "fips", "ag", "pop"])
s["bin"] = s.ag.map(SEER_GROUP)
tot = s.groupby(["fips", "year"]).pop.sum().rename("pop")
adults = s.dropna(subset=["bin"]).pivot_table(index=["fips", "year"], columns="bin", values="pop", aggfunc="sum").fillna(0)
seer = adults.join(tot).reset_index()
say("SEER: counties", seer.fips.nunique(), "years", seer.year.min(), seer.year.max())
nat_pop = seer.groupby("year")[HEAD_BINS].sum()

# ------------------------------------------------------------------ SCF waves
waves = [1989, 1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022]
scf_rows, coef_rows = [], []
for w in waves:
    z = zipfile.ZipFile(RAW / "scf" / f"scfp{w}s.zip"); n = z.namelist()[0]; t = tempfile.mkdtemp(); z.extract(n, t)
    df, _ = pyreadstat.read_dta(f"{t}/{n}", usecols=["wgt", "age", "edcl", "equity", "deq", "networth"])
    # the summary-extract weight already sums to the household population across the five implicates
    df["hb"] = head_bin(df.age.values)
    df["yb"] = np.select([df.age < 35, df.age < 45, df.age < 55, df.age < 65], YLD_BINS[:4], "65p")
    df["col"] = (df.edcl == 4).astype(float)
    hh = df.groupby("hb").wgt.sum()
    deq_mean = (df.deq * df.wgt).groupby(df.yb).sum() / df.wgt.groupby(df.yb).sum()
    r = dict(wave=w, households=df.wgt.sum(), col_share=np.average(df.col, weights=df.wgt),
             med_networth=float(np.nan))
    o = np.argsort(df.networth.values); cw = np.cumsum(df.wgt.values[o]); r["med_networth"] = df.networth.values[o][np.searchsorted(cw, cw[-1] / 2)]
    for b in HEAD_BINS: r[f"hh_{b}"] = hh.get(b, 0.0)
    for b in YLD_BINS: r[f"deq_{b}"] = deq_mean[b]
    r["agg_deq"] = (df.deq * df.wgt).sum(); r["agg_equity"] = (df.equity * df.wgt).sum()
    scf_rows.append(r)
    # A.3 column 2: EQUITY on DEQ + six age-of-head dummies (no constant) + college
    X = np.column_stack([df.deq.values] + [(df.hb == b).astype(float).values for b in HEAD_BINS] + [df.col.values])
    sw = np.sqrt(df.wgt.values)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], df.equity.values * sw, rcond=None)
    fit = X @ beta; resid = df.equity.values - fit
    r2 = 1 - np.average(resid ** 2, weights=df.wgt) / np.average((df.equity - np.average(df.equity, weights=df.wgt)) ** 2, weights=df.wgt)
    coef_rows.append(dict(wave=w, b_deq=beta[0], **{f"g_{b}": beta[1 + i] for i, b in enumerate(HEAD_BINS)}, d_col=beta[-1], r2=r2))
scf = pd.DataFrame(scf_rows).set_index("wave"); coefs = pd.DataFrame(coef_rows).set_index("wave")
scf = scf.join(coefs)
say("SCF waves (constant 2022 dollars):"); say(scf[["households", "col_share", "med_networth", "agg_deq", "agg_equity", "b_deq", "g_lt25", "g_45_54", "g_65p", "d_col", "r2"]].round(3).to_string())
# headship rate = SCF households in the bin / SEER national population in the bin
for b in HEAD_BINS:
    scf[f"head_{b}"] = scf[f"hh_{b}"] / nat_pop.loc[scf.index, b].values
say("Headship rates:"); say(scf[[f"head_{b}" for b in HEAD_BINS]].round(3).to_string())
scf.to_csv(OUT / "scf_waves.csv")
# annual interpolation, held flat outside the waves
yrs = range(1988, 2027)
sy = scf.reindex(sorted(set(yrs) | set(scf.index))).interpolate(method="index", limit_area="inside").ffill().bfill().loc[list(yrs)]
sy.index.name = "year"; sy.to_csv(OUT / "scf_by_year.csv")

# ------------------------------------------------------------------ college share
def load(f):
    j = json.load(open(f)); return pd.DataFrame(j[1:], columns=j[0])
api = RAW / "census" / "api"
c00 = load(api / "sf3_2000.json"); num = [c for c in c00.columns if c.startswith("P037") and c != "P037001"]
c00 = pd.DataFrame(dict(fips=c00.state + c00.county, col=c00[num].astype(float).sum(axis=1) / c00.P037001.astype(float), year=2000))
acs = []
for y, mid in [(2012, 2010), (2015, 2013), (2020, 2018), (2023, 2021)]:
    a = load(api / f"acs5_{y}.json"); num = [f"B15003_0{k}E" for k in (22, 23, 24, 25)]
    acs.append(pd.DataFrame(dict(fips=a.state + a.county, col=a[num].astype(float).sum(axis=1) / a.B15003_001E.astype(float), year=mid)))
col = pd.concat([c00] + acs).pivot_table(index="fips", columns="year", values="col")
colg = col.reindex(columns=range(1988, 2027)).T.interpolate(method="index", limit_area="inside").T
nat = sy.col_share
for y in range(1988, 2000):                                   # keep the county's 2000 gap to the national share
    colg[y] = colg[2000] + (nat[y] - nat[2000])
colg = colg.T.ffill().T
colg = colg.stack().rename("col").reset_index().rename(columns={"level_1": "year"})
say("college share: counties", colg.fips.nunique(), "| pop-unweighted mean 1990/2000/2021:",
    [round(colg[colg.year == y].col.mean(), 3) for y in (1990, 2000, 2021)])

# ------------------------------------------------------------------ county-year table
cd = seer.merge(sy[[f"head_{b}" for b in HEAD_BINS] + [f"deq_{b}" for b in YLD_BINS]], left_on="year", right_index=True, how="left")
for b in HEAD_BINS: cd[f"H_{b}"] = cd[b] * cd[f"head_{b}"]
cd["H"] = cd[[f"H_{b}" for b in HEAD_BINS]].sum(axis=1)
# yield-table bins in households: <35 = lt25 + 25_34
cd["Hy_lt35"] = cd.H_lt25 + cd.H_25_34
for b in YLD_BINS[1:]: cd[f"Hy_{b}"] = cd[f"H_{b}"]
cd = cd.merge(colg, on=["fips", "year"], how="left")
REGION = {**{s: 1 for s in ["09", "23", "25", "33", "44", "50", "34", "36", "42"]},
          **{s: 2 for s in ["17", "18", "26", "39", "55", "19", "20", "27", "29", "31", "38", "46"]},
          **{s: 3 for s in ["10", "11", "12", "13", "24", "37", "45", "51", "54", "01", "21", "28", "47", "05", "22", "40", "48"]},
          **{s: 4 for s in ["04", "08", "16", "30", "32", "35", "49", "56", "02", "06", "15", "41", "53"]}}
cd["region"] = cd.fips.str[:2].map(REGION)
p10 = cd[cd.year == 2010].set_index("fips")["pop"].rename("pop2010")
cd = cd.merge(p10, left_on="fips", right_index=True, how="left")
keep = ["fips", "year", "pop", "pop2010", "region", "H", "col"] + [f"H_{b}" for b in HEAD_BINS] + [f"Hy_{b}" for b in YLD_BINS]
cd[keep].to_parquet(OUT / "county_demog.parquet", index=False)
say("county_demog rows", len(cd), "missing college share:", int(cd.col.isna().sum()), "missing region:", int(cd.region.isna().sum()))
say("national households (SEER x headship) vs SCF:", round(cd[cd.year == 2019].H.sum() / 1e6, 1), "m vs", round(sy.households[2019] / 1e6, 1), "m")
