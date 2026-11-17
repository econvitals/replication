"""Cleaner county dividends and wages, 1989-2023: a fixed late-filer factor per county instead of year-by-year ZIP data.

    python 02b_irs_clean.py <out dir>        (paperwright venv; reads irs_county_raw / irs_zip_county from 02)

Why: the paper's splice (02_irs_build.py) uses ZIP-allocated amounts for 2004-2009 scaled by each county's 2010
county/ZIP ratio. The ZIP files drop small ZIP codes from 2008 on (rows fall from about 38,500 to 29,600), so the
2010 ratio mis-scales 2004-2007 and county growth rates jump at 2004 and 2008. Here:
  * Before 2010 (county files counted returns filed by September), each county's dividends and wages are scaled by
    a fixed late-filer factor = median over 2004-2007 of ZIP-allocated / county-file amounts (the years with full
    ZIP coverage; ZIP files count returns filed by December, like the county files from 2010).
  * Late-filer counties are flagged as in the paper's method (ZIP/county dividends > 2 in any of 2004-2009; 75 here, 74 in
    the paper), taken from the 02 build. Factors below 1 (small counties, where ZIP files suppress dividend cells) are set to 1.
  * Isolated one-year spikes that reverse the next year (|change| > 0.35 log points for wages, > 0.8 for dividends,
    in opposite directions, and the neighbors within 0.25 / 0.5 of each other) are replaced by the average of the
    neighbors in logs. These are coding errors in individual state files (Virginia 1995, Kansas 2009, ...).
Writes irs_county_adj.parquet (the version used downstream; the paper-method version is kept as
irs_county_adj_paper.parquet) and appends to irs_checks.txt.
"""
import shutil, sys
from pathlib import Path
import numpy as np, pandas as pd

OUT = Path(sys.argv[1])
if not (OUT / "irs_county_adj_paper.parquet").exists():
    shutil.copy(OUT / "irs_county_adj.parquet", OUT / "irs_county_adj_paper.parquet")
log = open(OUT / "irs_checks.txt", "a")
def say(*a):
    print(*a); print(*a, file=log, flush=True)
say("\n==== 02b_irs_clean.py")
raw = pd.read_parquet(OUT / "irs_county_raw.parquet")
zc = pd.read_parquet(OUT / "irs_zip_county.parquet")
C = {v: raw.pivot_table(index="fips", columns="year", values=v) for v in ["div", "wages"]}
Z = {v: zc.pivot_table(index="fips", columns="year", values=v) for v in ["div", "wages"]}
yrs = list(range(1989, 2024))
adj, flags = {}, None
for v in ["div", "wages"]:
    c = C[v].reindex(columns=yrs).where(C[v] > 0)
    z = Z[v].reindex(index=c.index)
    ratio = (z[[2004, 2005, 2006, 2007]] / c[[2004, 2005, 2006, 2007]])
    r = ratio.median(axis=1)
    nat = (z[[2004, 2005, 2006, 2007]].sum() / c[[2004, 2005, 2006, 2007]].sum()).mean()
    r = r.fillna(nat).clip(1.0, 3.0)      # late filing only adds; ratios below 1 are ZIP-file cell suppression
    say(f"{v}: late-filer factor, national {nat:.3f}; across counties", r.describe(percentiles=[.05, .5, .95]).round(3).to_dict())
    if v == "div":
        flags = pd.read_parquet(OUT / "irs_county_adj_paper.parquet").groupby("fips").late_filer_flag.first()
        say("late-filer flag kept from the paper-method build (ZIP/county dividends > 2 in any of 2004-2009):", int(flags.sum()), "(paper: 74)")
    s = c.copy()
    for y in yrs:
        if y < 2010: s[y] = c[y] * r
    # spike repair in logs
    L = np.log(s)
    thr, near = (0.8, 0.5) if v == "div" else (0.35, 0.25)
    fixed = 0
    for i in range(1, len(yrs) - 1):
        a, b, n = L[yrs[i - 1]], L[yrs[i]], L[yrs[i + 1]]
        d1, d2 = b - a, n - b
        bad = (d1.abs() > thr) & (d2.abs() > thr) & (np.sign(d1) != np.sign(d2)) & ((n - a).abs() < near)
        L.loc[bad, yrs[i]] = (a[bad] + n[bad]) / 2
        fixed += int(bad.sum())
    # isolated bad first/last-but-one handled by interpolation of any remaining holes
    s = np.exp(L).T.interpolate(limit_area="inside").T
    say(f"{v}: spikes repaired: {fixed}")
    g = np.log(s).diff(axis=1)
    say(f"{v}: s.d. across counties of the log change, by year:", g.std().round(3).loc[[1995, 1996, 2004, 2005, 2008, 2009, 2010, 2011, 2012]].to_dict())
    adj[v] = s
panel = pd.concat({v: adj[v].stack() for v in adj}, axis=1).reset_index()
panel.columns = ["fips", "year", "div", "wages"]
panel["late_filer_flag"] = panel.fips.map(flags).fillna(False).astype(bool)
rr = raw.set_index(["fips", "year"])[["div", "wages", "n1"]].add_suffix("_raw")
panel = panel.merge(rr, left_on=["fips", "year"], right_index=True, how="left")
panel.to_parquet(OUT / "irs_county_adj.parquet", index=False)
say("national totals after cleaning ($bn):", (panel.groupby("year")[["div", "wages"]].sum() / 1e6).round(1).loc[[1989, 2000, 2007, 2009, 2010, 2015, 2023]].to_dict())
