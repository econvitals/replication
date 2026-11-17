"""National quarterly series for the county stock-wealth regressions.

    python 03_aggregates.py <raw agg dir> <out dir>      (chartbook venv: needs macrolib)

Writes agg_quarterly.csv indexed by quarter (e.g. 1990Q1):
  rm      total return on the CRSP value-weighted market in the quarter (Ken French Mkt-RF + RF)
  rf      return on one-month T-bills compounded over the quarter (French RF)
  pd      S&P Composite price / trailing 12-month dividends in the quarter's last month (Shiller)
  bond5   holding return over the quarter on a 5-year zero (Gurkaynak-Sack-Wright Svensson curve):
          5*y5(t-1) - 4.75*y4.75(t), continuously compounded yields
  pm, dm  S&P Composite price and annualized dividends, quarter-end month (Shiller)
  cpi     CPI-U, quarterly average (FRED CPIAUCSL)
  dhpi    log change in the Case-Shiller national home price index (SA), t-1 to t
  lab_fwd, bus_fwd  ln(sum_{j=0..11} beta^-j A_{t+j}) - ln(A_{t-1}) for compensation (BEA A033RC)
          and nonfarm proprietors' income (A041RC); beta = 1.03^(1/4). Missing where t+11 is beyond data.
"""
import io, sys, zipfile
from pathlib import Path
import numpy as np, pandas as pd
from macrolib import bea, fred

RAW, OUT = Path(sys.argv[1]), Path(sys.argv[2])

# ---- French: monthly percent, YYYYMM rows until the annual block ----
z = zipfile.ZipFile(RAW / "ff3.zip"); txt = z.read(z.namelist()[0]).decode("latin1")
rows = []
for line in txt.splitlines():
    p = [x.strip() for x in line.split(",")]
    if len(p) >= 5 and len(p[0]) == 6 and p[0].isdigit():
        rows.append((p[0], float(p[1]), float(p[4])))
    elif rows and len(p[0]) == 4:   # annual block starts
        break
ff = pd.DataFrame(rows, columns=["ym", "mktrf", "rf"])
ff["m"] = pd.PeriodIndex(pd.to_datetime(ff.ym, format="%Y%m"), freq="M")
ff = ff.set_index("m")
ff["rm_m"] = (ff.mktrf + ff.rf) / 100; ff["rf_m"] = ff.rf / 100
q = ff.groupby(ff.index.asfreq("Q")).agg(rm=("rm_m", lambda x: np.prod(1 + x) - 1 if len(x) == 3 else np.nan),
                                          rf=("rf_m", lambda x: np.prod(1 + x) - 1 if len(x) == 3 else np.nan))

# ---- Shiller: monthly P and D (D = annualized dividends) ----
sh = pd.read_excel(RAW / "ie_data_new.xls", sheet_name="Data", header=None, skiprows=8)
sh = sh.iloc[:, :3]; sh.columns = ["date", "P", "D"]
sh = sh[pd.to_numeric(sh.date, errors="coerce").notna()].copy()
sh["date"] = sh.date.astype(float)
sh["y"] = sh.date.astype(int); sh["mo"] = ((sh.date - sh.y) * 100).round().astype(int)
sh["m"] = pd.PeriodIndex(pd.to_datetime(dict(year=sh.y, month=sh.mo, day=1)), freq="M")
sh = sh.set_index("m")[["P", "D"]].apply(pd.to_numeric, errors="coerce")
# Shiller's D is interpolated from quarterly S&P figures and lags the price; carry the last D forward
sh["D"] = sh["D"].ffill()
shq = sh[sh.index.month % 3 == 0]
q["pd"] = pd.Series((shq.P / shq.D).values, index=shq.index.asfreq("Q"))
q["pm"] = pd.Series(shq.P.values, index=shq.index.asfreq("Q"))
q["dm"] = pd.Series(shq.D.values, index=shq.index.asfreq("Q"))
q["pd_lastmonth"] = pd.Series([str(m) for m in shq.index], index=shq.index.asfreq("Q"))

# ---- GSW 5-year zero holding return ----
g = pd.read_csv(RAW / "gsw.csv", skiprows=9)
g["Date"] = pd.to_datetime(g["Date"]); g = g.set_index("Date")
def sv(row, n):
    b0, b1, b2, b3, t1, t2 = (row[k] for k in ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"])
    a1 = (1 - np.exp(-n / t1)) / (n / t1); a2 = a1 - np.exp(-n / t1)
    a3 = (1 - np.exp(-n / t2)) / (n / t2) - np.exp(-n / t2)
    return (b0 + b1 * a1 + b2 * a2 + b3 * a3) / 100
ge = g.dropna(subset=["BETA0"]).groupby(pd.PeriodIndex(g.dropna(subset=["BETA0"]).index, freq="Q")).last()
y5 = ge.apply(lambda r: sv(r, 5.0), axis=1); y475 = ge.apply(lambda r: sv(r, 4.75), axis=1)
q["bond5"] = np.exp(5 * y5.shift(1) - 4.75 * y475) - 1

# ---- Case-Shiller national (SA), quarterly average ----
cs = fred.series("CSUSHPISA", start="1987-01-01")
cs = pd.Series({pd.Timestamp(o.d): o.v for o in cs.obs}).dropna()
csq = cs.groupby(cs.index.to_period("Q")).mean()
q["dhpi"] = np.log(csq).diff()

# ---- CPI-U (quarterly average), to put SCF dollars in nominal terms ----
cpi = fred.series("CPIAUCSL", start="1985-01-01")
cpi = pd.Series({pd.Timestamp(o.d): o.v for o in cpi.obs}).dropna()
q["cpi"] = cpi.groupby(cpi.index.to_period("Q")).mean()

# ---- BEA labor and noncorporate income, forward-looking human/business wealth revisions ----
got = bea.series_many(["T20100/A033RC", "T20100/A041RC"], start="1980-01-01", freq="Q")
for name, code in [("lab", "T20100/A033RC"), ("bus", "T20100/A041RC")]:
    a = pd.Series({pd.Period(o.d, "Q"): o.v for o in got[code].obs}).sort_index()
    q[name] = a
    beta = 1.03 ** 0.25
    disc = sum(a.shift(-j) / beta ** j for j in range(12))
    q[f"{name}_fwd"] = np.log(disc) - np.log(a.shift(1))

q = q.loc["1985Q1":]
q.index = q.index.astype(str)
q.to_csv(OUT / "agg_quarterly.csv")
print(q.loc["1989Q4":].describe().T[["count", "mean", "std", "min", "max"]].round(4))
print(q.tail(8).round(4))
