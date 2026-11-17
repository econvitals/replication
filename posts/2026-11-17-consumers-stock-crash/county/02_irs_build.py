"""County dividends and wages from IRS Statistics of Income, 1989-2023, on a consistent filing basis.

    python 02_irs_build.py <raw irs dir> <out dir>          (paperwright venv)

Follows Chodorow-Reich, Nenov and Simsek (2021), online appendix A.1.1:
  - 2010 onward: county files (returns filed through December of the filing year).
  - 2004-2009: ZIP-code files (also December basis) allocated to counties, scaled county by county
    by the ratio of 2010 county-file to 2010 ZIP-allocated amounts.
  - 1989-2003: county files (September basis) scaled by the ratio of 2004 ZIP-based (as just built)
    to 2004 county-file amounts.
  - Flag counties where ZIP-based / county-file dividends exceed 2 in any of 2004-2009 (the paper
    drops 74 such counties).
ZIP codes are allocated to counties with the Census 2010 ZCTA-county relationship file (population
shares; area shares for ZCTAs with no population). Amounts are thousands of dollars.
Writes irs_county_raw.parquet, irs_zip_county.parquet, irs_county_adj.parquet and irs_checks.txt.
"""
import glob, re, sys, zipfile, tempfile
from pathlib import Path
import numpy as np, pandas as pd

RAW, OUT = Path(sys.argv[1]), Path(sys.argv[2])
log = open(OUT / "irs_checks.txt", "w")
def say(*a):
    print(*a); print(*a, file=log, flush=True)

def num(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)): return float(v)
    s = str(v).strip().replace(",", "")
    try: return float(s)
    except ValueError: return np.nan

def header_text(df, col, upto):
    return " ".join(str(df.iat[r, col]) for r in range(upto) if isinstance(df.iat[r, col], str)).upper()

# ------------------------------------------------------------ county files 1990-2009 (Excel)
def parse_county_xls(path, year):
    out = []
    for sname, df in pd.read_excel(path, header=None, sheet_name=None).items():
        if df.shape[0] < 5 or df.shape[1] < 7: continue
        H = min(14, len(df))
        hdr = {c: header_text(df, c, H) for c in range(df.shape[1])}
        divc = [c for c, t in hdr.items() if "DIVIDEND" in t]
        wagec = [c for c, t in hdr.items() if "WAGE" in t or "SALAR" in t]
        hdr4 = {c: " ".join(str(df.iat[r, c]) for r in range(4, H) if isinstance(df.iat[r, c], str)).upper() for c in range(df.shape[1])}
        retc = [c for c, t in hdr4.items() if "RETURNS" in t]
        if not divc or not wagec: continue
        divc, wagec = divc[0], wagec[0]; retc = retc[0] if retc else None
        # state / county code columns: the adjacent integer pair before the county name
        best, pair = 0, None
        for c in range(0, min(4, df.shape[1] - 1)):
            a = df.iloc[:, c].map(num); b = df.iloc[:, c + 1].map(num)
            ok = (a.between(1, 78) & (a == a.round()) & b.between(0, 999) & (b == b.round())).sum()
            if ok > best: best, pair = ok, c
        if pair is None or best < 1: continue
        for r in range(len(df)):
            st, cty = num(df.iat[r, pair]), num(df.iat[r, pair + 1])
            if np.isnan(st) or np.isnan(cty) or not (1 <= st <= 78) or st != round(st) or cty != round(cty): continue
            out.append(dict(year=year, fips=f"{int(st):02d}{int(cty):03d}", wages=num(df.iat[r, wagec]),
                            div=num(df.iat[r, divc]), n1=num(df.iat[r, retc]) if retc is not None else np.nan,
                            src=Path(path).name))
    return out

rows = []
tmp = Path(tempfile.mkdtemp())
for y in range(1990, 2010):
    d = tmp / f"c{y}"; zipfile.ZipFile(RAW / f"{y}countyincome.zip").extractall(d)
    for f in sorted(glob.glob(str(d / "**" / "*.xls"), recursive=True)):
        rows += parse_county_xls(f, y)
c = pd.DataFrame(rows)
c = c[c.fips.str[2:] != "000"]
c = c.drop_duplicates(["year", "fips"])
# 1989 CSV
z = zipfile.ZipFile(RAW / "1989countyincome.zip")
c89 = pd.read_csv(z.open("89incyallnoagi.csv"), encoding="utf-8-sig")
c89 = pd.DataFrame(dict(year=1989, fips=c89.STATEFIPS.astype(int).map("{:02d}".format) + c89.COUNTYFIPS.astype(int).map("{:03d}".format),
                        wages=c89.WAGES_SAL, div=c89.DIVIDENDS, n1=c89.N1, src="89incyallnoagi.csv"))
c89 = c89[c89.fips.str[2:] != "000"]
# 2010+ CSV
csvs = {2010: tmp / "c2010.csv"}
zipfile.ZipFile(RAW / "2010countydata.zip").extract("10incyallnoagi.csv", tmp); csvs[2010] = tmp / "10incyallnoagi.csv"
for y in range(2011, 2024):
    yy = f"{y % 100:02d}"
    csvs[y] = RAW / (f"{yy}cyallnoagi.csv" if y == 2012 else f"{yy}incyallnoagi.csv")
new = []
for y, f in csvs.items():
    x = pd.read_csv(f, dtype={"STATEFIPS": str, "COUNTYFIPS": str}, encoding="latin1")
    x.columns = [k.upper() for k in x.columns]
    if "AGI_STUB" in x: x = x[x.AGI_STUB == 0]
    x = pd.DataFrame(dict(year=y, fips=x.STATEFIPS.str.zfill(2) + x.COUNTYFIPS.str.zfill(3), wages=x.A00200, div=x.A00600, n1=x.N1, src=Path(f).name))
    new.append(x[x.fips.str[2:] != "000"])
county = pd.concat([c89, c] + new, ignore_index=True)
county = county[county.fips.str[:2].astype(int) <= 56]     # 50 states + DC
county.to_parquet(OUT / "irs_county_raw.parquet", index=False)
say("COUNTY FILES: counties per year and national totals ($bn)")
tab = county.groupby("year").agg(n=("fips", "nunique"), div=("div", "sum"), wages=("wages", "sum"), n1=("n1", "sum"))
tab["div"] /= 1e6; tab["wages"] /= 1e6
say(tab.round(1).to_string())

# ------------------------------------------------------------ ZIP files 2004-2010 (Excel)
def parse_zip_xls(path, year):
    out = []
    for sname, df in pd.read_excel(path, header=None, sheet_name=None).items():
        if df.shape[0] < 10 or df.shape[1] < 8: continue
        H = 12
        # header row: the row holding "Salaries"
        hr = None
        for r in range(H):
            if any(isinstance(v, str) and "salaries" in v.lower() for v in df.iloc[r].tolist()):
                hr = r; break
        if hr is None: continue
        row = [str(v).lower() if isinstance(v, str) else "" for v in df.iloc[hr].tolist()]
        wc = [i for i, v in enumerate(row) if "salaries" in v][0]
        dcs = [i for i, v in enumerate(row) if "dividend" in v and "qualified" not in v]
        if not dcs: continue
        dc = dcs[0]
        def amount_col(c):
            for rr in range(hr + 1, min(hr + 4, len(df))):
                a = str(df.iat[rr, c]).lower() if c < df.shape[1] else ""
                b = str(df.iat[rr, c + 1]).lower() if c + 1 < df.shape[1] else ""
                if "number" in a and "amount" in b: return c + 1
                if "amount" in a: return c
            return c
        wa, da = amount_col(wc), amount_col(dc)
        hdr0 = " ".join(str(df.iat[r, 0]) for r in range(hr, hr + 3) if isinstance(df.iat[r, 0], str)).upper()
        hdr1 = " ".join(str(df.iat[r, 1]) for r in range(hr, hr + 3) if isinstance(df.iat[r, 1], str)).upper()
        zc = 1 if ("ZIP" in hdr1 and "ZIP" not in hdr0) else 0
        oc = 1 - zc   # the other of the first two columns (class label, or data in the 2004 layout)
        for r in range(hr + 1, len(df)):
            zv = num(df.iat[r, zc])
            if np.isnan(zv) or zv < 1000 or zv >= 99999 or zv != round(zv): continue
            other = df.iat[r, oc]
            if isinstance(other, str) and other.strip() and other.strip().lower() not in ("total",):
                if any(k in other.lower() for k in ("$", "under", "more", "less")): continue
            if zc == 1 and not (other is None or (isinstance(other, float) and np.isnan(other)) or str(other).strip().lower() in ("", "total")):
                continue
            out.append(dict(year=year, zip=f"{int(zv):05d}", wages=num(df.iat[r, wa]), div=num(df.iat[r, da]), src=Path(path).name))
    return out

zrows = []
for y in range(2004, 2011):
    d = tmp / f"z{y}"; zipfile.ZipFile(RAW / "zip" / f"{y}zipcode.zip").extractall(d)
    fs = sorted(glob.glob(str(d / "**" / "*.xls"), recursive=True))
    n0 = len(zrows)
    for f in fs: zrows += parse_zip_xls(f, y)
    say(f"ZIP {y}: {len(fs)} files, {len(zrows) - n0} zip rows")
zp = pd.DataFrame(zrows)
zp = zp.groupby(["year", "zip"], as_index=False).agg(wages=("wages", "first"), div=("div", "first"))
say("ZIP totals by year ($bn):", (zp.groupby("year")[["div", "wages"]].sum() / 1e6).round(1).to_string())

# crosswalk
cw = pd.read_csv(RAW / "zcta_county_rel_10.txt", dtype={"ZCTA5": str, "GEOID": str})
cw["w"] = np.where(cw.ZPOP > 0, cw.ZPOPPCT, cw.ZAREAPCT) / 100
cw["w"] = cw.w / cw.groupby("ZCTA5").w.transform("sum")
m = zp.merge(cw[["ZCTA5", "GEOID", "w"]], left_on="zip", right_on="ZCTA5", how="left")
unmatched = m[m.GEOID.isna()].groupby("year")["div"].sum() / zp.groupby("year")["div"].sum()
say("share of ZIP dividends with no ZCTA match:", unmatched.round(4).to_dict())
m = m.dropna(subset=["GEOID"])
zc = m.assign(div=m["div"] * m.w, wages=m.wages * m.w).groupby(["year", "GEOID"], as_index=False)[["div", "wages"]].sum()
zc = zc.rename(columns={"GEOID": "fips"})
zc.to_parquet(OUT / "irs_zip_county.parquet", index=False)

# ------------------------------------------------------------ consistent panel
cp = county.pivot_table(index="fips", columns="year", values=["div", "wages"])
zpv = zc.pivot_table(index="fips", columns="year", values=["div", "wages"])
adj = {}
for v in ["div", "wages"]:
    C = cp[v]; Z = zpv[v].reindex(C.index)
    r10 = C[2010] / Z[2010]
    s = pd.DataFrame(index=C.index)
    for y in range(2010, 2024): s[y] = C[y]
    for y in range(2004, 2010): s[y] = Z[y] * r10
    r04 = s[2004] / C[2004]
    for y in range(1989, 2004): s[y] = C[y] * r04
    adj[v] = s[sorted(s.columns)]
    if v == "div":
        ratio = (Z[list(range(2004, 2010))] / C[list(range(2004, 2010))])
        flag = (ratio > 2).any(axis=1)
        say(f"counties with ZIP/county dividend ratio > 2 in some year 2004-2009: {int(flag.sum())} (paper: 74)")
        say("ZIP/county dividend ratio 2004-2009, distribution across counties:")
        say(ratio.describe(percentiles=[.05, .25, .5, .75, .95]).round(3).to_string())
        say("2010 county/ZIP-allocated dividend ratio:", r10.describe(percentiles=[.05, .5, .95]).round(3).to_string())
panel = pd.concat({v: adj[v].stack() for v in adj}, axis=1).reset_index()
panel.columns = ["fips", "year", "div", "wages"]
panel["late_filer_flag"] = panel.fips.map(flag).fillna(False)
raw = county.set_index(["fips", "year"])[["div", "wages", "n1"]].add_suffix("_raw")
panel = panel.merge(raw, left_on=["fips", "year"], right_index=True, how="left")
panel.to_parquet(OUT / "irs_county_adj.parquet", index=False)
say("ADJUSTED national totals ($bn):")
say((panel.groupby("year")[["div", "wages", "div_raw", "wages_raw"]].sum() / 1e6).round(1).to_string())
