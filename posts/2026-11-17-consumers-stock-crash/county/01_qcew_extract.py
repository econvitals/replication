"""Extract the county and national QCEW rows the analysis needs from the BLS quarterly singlefiles.

Usage: python 01_qcew_extract.py <raw qcew dir> <out dir> <year> [<year> ...]
Writes <out>/qcew_<year>.parquet with: area_fips, own_code, industry_code, agglvl_code, year, qtr,
disclosure_code, emp (mean of the three monthly levels), wages (total quarterly wages).
Kept: agglvl 70 (county total covered), 74 (county x NAICS sector, private), 75 (county x NAICS
3-digit, private), 14/15 (national sector / 3-digit, private), 10 (national total).
Suppressed cells (disclosure_code N) are set to missing.
"""
import sys, zipfile, pandas as pd
raw, out = sys.argv[1], sys.argv[2]
KEEP = {70, 74, 75, 14, 15, 10}
cols = ["area_fips","own_code","industry_code","agglvl_code","year","qtr","disclosure_code",
        "month1_emplvl","month2_emplvl","month3_emplvl","total_qtrly_wages"]
dt = {"area_fips":str,"own_code":str,"industry_code":str,"agglvl_code":int,"year":int,"qtr":int,
      "disclosure_code":str,"month1_emplvl":float,"month2_emplvl":float,"month3_emplvl":float,"total_qtrly_wages":float}
for y in sys.argv[3:]:
    z = zipfile.ZipFile(f"{raw}/{y}_qtrly_singlefile.zip"); name = z.namelist()[0]
    parts = []
    with z.open(name) as fh:
        for ch in pd.read_csv(fh, usecols=cols, dtype=dt, chunksize=3_000_000):
            ch = ch[ch.agglvl_code.isin(KEEP)]
            ch = ch[(ch.agglvl_code.isin([70, 10])) | (ch.own_code == "5")]
            parts.append(ch)
    d = pd.concat(parts)
    d["emp"] = d[["month1_emplvl","month2_emplvl","month3_emplvl"]].mean(axis=1)
    d = d.rename(columns={"total_qtrly_wages":"wages"}).drop(columns=["month1_emplvl","month2_emplvl","month3_emplvl"])
    sup = d.disclosure_code.fillna("").eq("N")
    d.loc[sup, ["emp","wages"]] = float("nan")
    d.to_parquet(f"{out}/qcew_{y}.parquet", index=False)
    print(y, len(d), d.groupby("agglvl_code").size().to_dict(), flush=True)
