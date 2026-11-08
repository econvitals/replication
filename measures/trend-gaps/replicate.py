"""Trend Gaps — rebuilds the Economy vs. Trend tool (econvitals.org/tools/trend-gaps/) for its
headline series: how far each stands from the path it was on before COVID.

    python replicate.py        # needs FRED_API_KEY

The headline series are the eight concept tiles (real GDP, productivity, payroll and household
employment, ECI wages, real ECI wages, PCE prices, real disposable income per person) and the CPI.
The pre-COVID end point is February 2020 (monthly) or 2019 Q4 (quarterly); time is year +
(month - 1) / 12. The trends:

  fit2 / fit5 / fit10   least squares of log(level) on time over the 2, 5 or 10 years ending at
                        the end point, carried forward;
  cycle07 / cycle01     constant growth from the 2007 (or 2001) business-cycle peak to the end
                        point (December 2007 / 2007 Q4; March 2001 / 2001 Q1);
  hp                    a Hodrick-Prescott trend on logs from 2000 to the end point (lambda 1,600
                        quarterly, 129,600 monthly), extended at its growth over its final year;
  cbo                   CBO's January 2020 projection, re-anchored so 2019 Q4 matches the actual
                        (monthly series interpolate CBO's quarterly path).

The gap is 100 x (actual / trend - 1). Writes output/gaps.csv (the latest gap under each trend),
output/levels.csv (the series and CBO paths) and, for the nightly comparison, output/site_gaps.csv
and output/site_levels.csv (the same arithmetic on the published series).
"""
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402
from common.rates import published_anywhere  # noqa: E402

START = "2000-01-01"
PRECOVID = {"M": "2020-02-01", "Q": "2019-10-01"}
PEAKS = {"2007": {"M": "2007-12-01", "Q": "2007-10-01"}, "2001": {"M": "2001-03-01", "Q": "2001-01-01"}}
# id: (FRED series, scale to the units shown, column in CBO's January 2020 file)
SERIES = {
    "real_gdp": ("GDPC1", 1, "real_gdp"),                  # BEA, billions of chained 2017 dollars
    "productivity": ("OPHNFB", 1, "output_per_hr_nfb"),    # BLS, nonfarm business output per hour
    "payrolls": ("PAYEMS", 1e-3, "empl_payroll_nf"),       # BLS, payroll employment, millions
    "hh_employment": ("CE16OV", 1e-3, "empl_civ_16yo"),    # BLS, household-survey employment
    "eci": ("ECIWAG", 1, "eci_wages_salaries"),            # BLS, ECI private wages and salaries
    "real_eci": (None, 1, ("eci_wages_salaries", "cpiu")), # ECI / CPI (built below)
    "pce_price": ("PCEPI", 1, "pce_price_index"),          # BEA, PCE price index
    "real_dpi_pc": ("A229RX0", 1, None),                   # BEA, real disposable income per person
    "cpi": ("CPIAUCSL", 1, "cpiu"),                        # BLS, CPI-U, seasonally adjusted
}
TRENDS = ["fit5", "fit2", "fit10", "cycle07", "cycle01", "hp", "cbo"]


def qstart(d):
    return pd.Timestamp(d.year, 3 * ((d.month - 1) // 3) + 1, 1)


def quarterly_mean(monthly):
    """Quarter averages of complete quarters; a quarter with a month never published (October
    2025, the shutdown) is averaged over the months that exist once a later quarter has begun."""
    g = monthly.groupby(monthly.index.map(qstart))
    n, m = g.size(), g.mean()
    return m[(n == 3) | ((m.index < m.index.max()) & (n >= 2))]


# ---------------------------------------------------------------- the series
def build_series():
    data = {}
    cpi = fred("CPIAUCSL")
    for sid, (code, scale, _) in SERIES.items():
        if sid == "real_eci":                  # each quarter's ECI / that quarter's average CPI,
            eci = fred("ECIWAG")               # as an index with 2019 Q4 = 100
            raw = (eci / quarterly_mean(cpi)).dropna()
            s = raw * 100 / raw[pd.Timestamp("2019-10-01")]
        else:
            s = fred(code) * scale
        data[sid] = s[s.index >= START].round(4)   # the page works from four-decimal values
    return data


def freq_of(s):
    return "Q" if set(s.index[-12:].month) <= {1, 4, 7, 10} and len(set(s.index.month)) == 4 else "M"


def cbo_path(sid, actual, cbo):
    """CBO's January 2020 path, re-anchored so 2019 Q4 equals the actual; a monthly series puts
    each quarter at its middle month and interpolates month by month (in logs)."""
    col = SERIES[sid][2]
    if col is None:
        return None
    q = cbo[col[0]] / cbo[col[1]] if isinstance(col, tuple) else cbo[col]
    q = pd.Series(q.values, index=q.index.map(qstart))      # quarter-end dates -> quarter starts
    f, q4 = freq_of(actual), pd.Timestamp("2019-10-01")
    anchor = actual[q4] if f == "Q" else quarterly_mean(actual)[q4]
    q = q / q[q4] * anchor
    last = actual.index[-1]
    nxt = qstart(last).replace(day=28) + pd.DateOffset(days=95)
    q = q[(q.index >= "2019-07-01") & (q.index <= nxt)]
    if f == "M":
        pts = [(d + pd.DateOffset(months=1), v) for d, v in q.items()]
        path = {}
        for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
            n = (d1.year - d0.year) * 12 + d1.month - d0.month
            for i in range(n):
                w = i / n
                path[d0 + pd.DateOffset(months=i)] = math.exp((1 - w) * math.log(v0) + w * math.log(v1))
        path[pts[-1][0]] = pts[-1][1]
        q = pd.Series(path)
    lo = "2019-10-01" if f == "Q" else "2019-11-01"
    return q[(q.index >= lo) & (q.index <= last)].round(4)


# ---------------------------------------------------------------- the trends (as the page fits them)
def yr(d):
    return d.year + (d.month - 1) / 12


def hp_filter(y, lam):
    """Hodrick-Prescott trend: solves (I + lam K'K) tau = y exactly."""
    n = len(y)
    K = np.zeros((n - 2, n))
    for i in range(n - 2):
        K[i, i:i + 3] = [1, -2, 1]
    return np.linalg.solve(np.eye(n) + lam * K.T @ K, y)


def trend_at(s, key, cbo_line, when):
    """The trend's value at `when`, or None when the series cannot carry this trend."""
    f = freq_of(s)
    E = pd.Timestamp(PRECOVID[f])
    tE, step = yr(E), (1 / 12 if f == "M" else 0.25)
    if key == "cbo":
        return None if cbo_line is None or when not in cbo_line.index else cbo_line[when]
    if key == "hp":
        win = s[(s.index >= "2000-01-01") & (s.index <= E)]
        if len(win) < 24:
            return None
        tau = hp_filter(np.log(win.values), 129600 if f == "M" else 1600)
        per = 12 if f == "M" else 4
        if when in win.index:
            return math.exp(tau[list(win.index).index(when)])
        return math.exp(tau[-1] + (tau[-1] - tau[-1 - per]) * (yr(when) - tE)) if yr(when) > tE else None
    if key.startswith("cycle"):
        d0 = pd.Timestamp(PEAKS[key[-2:].replace("07", "2007").replace("01", "2001")][f])
        if d0 not in s.index or E not in s.index:
            return None
        b = (math.log(s[E]) - math.log(s[d0])) / (tE - yr(d0))
        return math.exp(math.log(s[E]) + b * (yr(when) - tE)) if yr(when) >= yr(d0) - 1e-9 else None
    years = int(key[3:])
    lo = max(tE - years + step, yr(s.index[0]))
    win = s[[lo - 1e-9 <= yr(d) <= tE + 1e-9 for d in s.index]]
    if len(win) < 3:
        return None
    x, y = np.array([yr(d) for d in win.index]), np.log(win.values)
    b = ((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum()
    a = y.mean() - b * x.mean()
    return math.exp(a + b * yr(when)) if yr(when) >= yr(win.index[0]) - 1e-9 else None


def latest_gaps(data, cbo_lines):
    rows = {}
    for sid, s in data.items():
        last = s.index[-1]
        row = {"latest": last.date().isoformat(), "level": s.iloc[-1]}
        for key in TRENDS:
            t = trend_at(s, key, cbo_lines.get(sid), last)
            row[key] = None if t is None else round(100 * (s.iloc[-1] / t - 1), 6)
        rows[sid] = row
    return pd.DataFrame(rows).T.rename_axis("series")


def long_form(data, cbo_lines):
    out = {f"{sid} {d.date()}": v for sid, s in data.items() for d, v in s.items()}
    out.update({f"{sid}/cbo {d.date()}": v for sid, s in cbo_lines.items() if s is not None
                for d, v in s.items()})
    return pd.Series(out, name="value").rename_axis("series_date")


# ---------------------------------------------------------------- run
cbo = pd.read_csv(HERE / "inputs" / "cbo_jan2020_quarterly.csv", index_col="date", parse_dates=True)
data = build_series()
cbo_lines = {sid: cbo_path(sid, s, cbo) for sid, s in data.items()}
gaps = latest_gaps(data, cbo_lines)
save(gaps, HERE, "gaps")
save(long_form(data, cbo_lines), HERE, "levels")

# The published series, with the same arithmetic applied to them (the page fits its trends in the
# browser, from the series it publishes; only the series themselves are in the published file).
site = published_anywhere("tools/trend-gaps/data.json")["series"]
pub = {sid: pd.Series({pd.Timestamp(d): v for d, v in site[sid]["data"]}) for sid in SERIES}
pub_cbo = {sid: (pd.Series({pd.Timestamp(d): v for d, v in site[sid]["cbo"]}) if site[sid].get("cbo")
                 else None) for sid in SERIES}
save(latest_gaps(pub, pub_cbo), HERE, "site_gaps")
save(long_form(pub, pub_cbo), HERE, "site_levels")

print(gaps[["latest"] + TRENDS].to_string())
