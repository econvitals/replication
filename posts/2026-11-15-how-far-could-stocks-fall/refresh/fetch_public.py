#!/usr/bin/env python3
"""Optional: re-download the public data into data_refreshed/ (never run by run_all.py).

The package's results come from the frozen files in data/. This script fetches today's versions of the ones that
can be fetched by script, for a reader who wants to see how the numbers move as the sources are revised.
Not fetched: the Z.1 table (download the Financial Accounts zip from federalreserve.gov/releases/z1 and read
series LM153064475 from table S1M.e.b) and the 2000 net income figures (typed from the filings named in the file).

    python refresh/fetch_public.py
"""
import io
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data_refreshed"
UA = {"User-Agent": "econvitals-replication (replication of an Econvitals Occasional Post)"}


def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    OUT.mkdir(exist_ok=True)
    for s in ("GDP", "CPATAX", "DFII10"):
        (OUT / f"fred_{s.lower()}.csv").write_bytes(get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}"))
        print("FRED", s)
    z = zipfile.ZipFile(io.BytesIO(get("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
                                       "F-F_Research_Data_Factors_daily_CSV.zip")))
    (OUT / "french_factors_daily.csv").write_bytes(z.read(z.namelist()[0]))
    print("Kenneth French daily factors")
    (OUT / "mpd_stats.csv").write_bytes(get("https://www.minneapolisfed.org/-/media/files/banking/mpd/mpd_stats.csv"))
    print("Minneapolis Fed market-based probabilities (all markets; the package uses the sp12m rows)")
    for cik in ("0001045810", "0001652044", "0000789019"):
        (OUT / f"sec_companyfacts_{cik}.json").write_bytes(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"))
        print("SEC company facts", cik)
    print("Shiller's ie_data.xls: download it from shillerdata.com by hand (its address changes with each update)")


if __name__ == "__main__":
    main()
