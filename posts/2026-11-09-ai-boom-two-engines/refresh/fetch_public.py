#!/usr/bin/env python3
"""fetch_public.py: re-pull the public input data straight from the agencies, into data_refreshed/.

OPTIONAL. The main run (run_all.py) never calls this and never touches the network; it reads the
frozen files in data/. Run this only to see how the results move with newer data:

    python refresh/fetch_public.py                 # writes data_refreshed/
    DCBOOM_DATA=data_refreshed python run_all.py   # rerun everything on the refreshed data

Standard library only. Sources (no keys needed unless noted):
  BEA       NIPA flat file, all quarterly series      https://apps.bea.gov/national/Release/TXT/NipaDataQ.txt
  Census    C30 private construction, SA, monthly     https://www.census.gov/construction/c30/xlsx/privsatime.xlsx
  FRED      copies of BLS, Federal Reserve (H.15, H.10), Freddie Mac and Census series, through the
            FRED API (https://api.stlouisfed.org/fred/series/observations). Needs a free key in the
            environment variable FRED_API_KEY (https://fred.stlouisfed.org/docs/api/api_key.html);
            without one this step is skipped and the frozen fred_series.csv is copied instead.
  Phil. Fed Survey of Professional Forecasters, median NGDP levels
            https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/survey-of-professional-forecasters/data-files/files/median_ngdp_level.xlsx

Three inputs are NOT refreshed here; see refresh/README.md for the steps:
  * trade_dc_goods_m.csv (BEA International Transactions table 2.1 quarterly lines, which the BEA API
    serves only with a free key, joined to the latest Census FT-900 exhibits 7 and 8), and
  * stock_gain.csv (share counts from SEC EDGAR times daily closing prices from a market-data vendor),
    and z1_series_used.csv (Federal Reserve Financial Accounts, table L.223 and the household balance
    sheet). refresh/stock_gain_calc.py recomputes the gain once you have supplied those numbers.

Reading the Census and Philadelphia Fed workbooks needs openpyxl (pip install openpyxl==3.1.5); the
main run does not.
"""
import csv
import io
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "data-center-boom-replication (research; python urllib)"}

BEA_SERIES = ["A191RC", "A191RX", "A007RC", "A008RC", "A008RX", "A011RC", "A011RX", "A019RC", "A020RX",
              "A021RX", "DPCERX", "DPCCRG", "B935RC", "C275RC", "C314RC", "LA001282"]
FRED_SERIES = {  # file name: (FRED id, start date kept)
    "UNRATE": ("UNRATE", "2018-01-01"),               # BLS LNS14000000
    "EFFR": ("EFFR", "2018-01-01"),                   # Federal Reserve H.15, effective federal funds rate
    "DGS10": ("DGS10", "2018-01-01"),                 # Federal Reserve H.15, 10-year Treasury constant maturity
    "RTWEXBGS": ("RTWEXBGS", "2018-01-01"),           # Federal Reserve H.10, real broad dollar index
    "MORTGAGE30US": ("MORTGAGE30US", "2018-01-01"),   # Freddie Mac PMMS 30-year fixed
    "WPSFD43": ("PPIDCS", "2009-01-01"),              # BLS PPI final demand construction (FRED's copy of WPSFD43)
    "BOPGSTB": ("BOPGSTB", "1999-01-01"),             # Census/BEA FT-900 goods and services balance, BOP basis, SA
}


def get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(10 * (i + 1))


def bea(out: Path):
    txt = get("https://apps.bea.gov/national/Release/TXT/NipaDataQ.txt").decode("utf-8-sig")
    rows = {}
    for rec in csv.reader(io.StringIO(txt)):
        if len(rec) != 3 or rec[0] not in BEA_SERIES:
            continue
        rows.setdefault(rec[1], {})[rec[0]] = rec[2].replace(",", "")
    with open(out / "bea_nipa_q.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quarter"] + BEA_SERIES)
        for q in sorted(rows):
            w.writerow([q] + [rows[q].get(s, "") for s in BEA_SERIES])
    print("bea_nipa_q.csv", len(rows), "quarters")


def c30(out: Path):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(get("https://www.census.gov/construction/c30/xlsx/privsatime.xlsx")),
                                read_only=True, data_only=True)
    write_c30(list(wb.active.iter_rows(values_only=True)), out)


def write_c30(rows, out: Path):
    """rows: the workbook's first sheet as a list of tuples (newest month first, a 'Date' header row)."""
    h = next(i for i, r in enumerate(rows) if str(r[0]).strip() == "Date")
    names = [re.sub(r"\s+", " ", str(v).replace("_x000D_", " ")).strip() for v in rows[h]]
    names = [re.sub(r"(\D)\d$", r"\1", n) for n in names]          # drop footnote digits ("Construction1")
    body = [r for r in rows[h + 1:] if re.match(r"^[A-Z][a-z]{2}-\d{2}[pr]?$", str(r[0]))]
    months = []
    for r in body:
        mon, yy = str(r[0]).rstrip("pr").split("-")
        y = 2000 + int(yy) if int(yy) < 70 else 1900 + int(yy)
        m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(mon) + 1
        months.append((f"{y:04d}-{m:02d}-01", r))
    months.sort()
    with open(out / "census_c30_private_sa_m.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month"] + names[1:])
        for d, r in months:
            w.writerow([d] + ["" if v is None or str(v).strip() in ("", "(NA)", "(S)", "(X)") else v for v in r[1:len(names)]])
    print("census_c30_private_sa_m.csv", len(months), "months")


def fred(out: Path):
    import json
    import os
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("no FRED_API_KEY in the environment (a free key from fred.stlouisfed.org)")
    with open(out / "fred_series.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["series", "fred_id", "date", "value"])
        for name, (fid, start) in FRED_SERIES.items():
            url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={fid}&api_key={key}"
                   f"&file_type=json&observation_start={start}")
            obs = json.loads(get(url))["observations"]
            n = 0
            for o in obs:
                if o["value"] not in ("", "."):
                    w.writerow([name, fid, o["date"], o["value"]]); n += 1
            print("fred", name, n, "observations")
            time.sleep(1)


def spf(out: Path):
    import openpyxl
    url = ("https://www.philadelphiafed.org/-/media/frbp/assets/surveys-and-data/survey-of-professional-forecasters/"
           "data-files/files/median_ngdp_level.xlsx")
    ws = openpyxl.load_workbook(io.BytesIO(get(url)), read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    with open(out / "spf_median_ngdp_level.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(rows[0])
        for r in rows[1:]:
            if r[0] is not None and int(r[0]) >= 2024:
                w.writerow(r)
    print("spf_median_ngdp_level.csv written")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data_refreshed"
    out.mkdir(exist_ok=True)
    for fn in (bea, fred, c30, spf):
        try:
            fn(out)
        except Exception as ex:                      # keep going; say what failed
            print(f"{fn.__name__}: FAILED ({ex!r}); the frozen copy from data/ is used instead")
    for src in sorted((ROOT / "data").glob("*.csv")):      # anything not refreshed: the frozen copy
        dst = out / src.name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
            print(f"{src.name}: not refreshed, copied from data/ (see refresh/README.md)")
