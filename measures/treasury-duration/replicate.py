"""Treasury Duration Index — rebuilds the duration chart on econvitals.org/fiscal/.

    python replicate.py               # the last 36 months (no key for Treasury or the NY Fed;
                                      # FRED_API_KEY for the mortgage rates)
    python replicate.py --since 2007-01     # the whole chart (downloads ~240 months of files)

Writes output/treasury_duration.csv: date, all_debt, net_fed, incl_mbs (years), plus the
par outstanding and the Fed's share as an audit trail.

At each month end, every marketable Treasury security outstanding (Treasury's Monthly Statement of
the Public Debt) is matched to the par the Federal Reserve holds (the New York Fed's SOMA file):

  all_debt  par-weighted Macaulay duration of all marketable Treasury debt.
  net_fed   the same, with the Fed's Treasuries replaced dollar for dollar by the overnight
            reserves that fund them (duration one day). The denominator is unchanged.
  incl_mbs  net_fed less the dollar duration of the Fed's agency MBS, agency debt and agency
            CMBS (also reserve-funded), over the same Treasury par. From December 2008.
"""
import argparse
import datetime as dt
import math
import re
import sys
from bisect import bisect_left
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, save  # noqa: E402
from common.finance import (soma_agency, soma_asof_dates, soma_asof_for,  # noqa: E402
                            treasury_curve, treasury_securities)

DAY = 1 / 365.25                                   # one day, in years: the tenor of reserves
PAR_TENORS = [1/12, 2/12, 3/12, 4/12, 6/12, 1, 2, 3, 5, 7, 10, 20, 30]   # par curve points used
REAL_TENORS = [5, 7, 10, 20, 30]                   # real (TIPS) curve points
MBS_START = "2008-12"                              # the Fed's first agency purchases


# ---------------------------------------------------------------- yield curves
_years = {}


def curve_on(kind, day, tenors):
    """[(years, yield %)] on `day`, or the nearest business day before it with 3+ points."""
    for back in range(12):
        d = day - dt.timedelta(days=back)
        if (kind, d.year) not in _years:
            _years[(kind, d.year)] = treasury_curve(kind, d.year)
        tbl = _years[(kind, d.year)]
        if d in tbl.index:
            row = tbl.loc[d]
            pts = [(t, float(row[t])) for t in tenors if t in row.index and pd.notna(row[t])]
            if len(pts) >= 3:
                return sorted(pts)
    raise RuntimeError(f"no {kind} curve near {day}")


def interp(pts, x):
    """Linear interpolation on the curve, flat beyond its ends."""
    xs = [p[0] for p in pts]
    if x <= xs[0]:
        return pts[0][1]
    if x >= xs[-1]:
        return pts[-1][1]
    i = bisect_left(xs, x)
    (x0, y0), (x1, y1) = pts[i - 1], pts[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# ---------------------------------------------------------------- Treasury securities
def macaulay(kind, t, coupon, ytm):
    """Macaulay duration in years of one security with `t` years to run, at yield `ytm` (%)."""
    if t <= 0:
        return 0.0
    if kind == "bill":
        return t                                   # one cash flow, at maturity
    if kind == "frn":
        return 7 / 365.25                          # resets weekly off the 13-week bill rate
    c, y = (coupon or 0.0) / 2, ytm / 200          # semiannual coupon per 100, semiannual yield
    n = max(1, round(t * 2))
    first = t - (n - 1) * 0.5                      # time to the next coupon
    pv = wt = 0.0
    for k in range(n):
        tk = first + k * 0.5
        disc = (c + (100 if k == n - 1 else 0)) / (1 + y) ** (2 * tk)
        pv += disc
        wt += tk * disc
    return wt / pv if pv else t


def treasury_month(month_end, soma_date):
    """(par $bn, duration all, duration net of the Fed, Fed's par $bn) at one month end."""
    secs = treasury_securities(month_end, soma_date)
    if secs.empty:                                  # Treasury has not published this month yet
        return None
    par_c = curve_on("par", month_end, PAR_TENORS)
    real_c = curve_on("real", month_end, REAL_TENORS)   # TIPS: a real duration at real yields
    tot = tot_dur = net_dur = fed = 0.0
    for s in secs.itertuples():
        t = (s.maturity - month_end).days / 365.25
        if t <= 0:                                  # matured but not yet redeemed
            continue
        d = macaulay(s.kind, t, s.coupon, interp(real_c if s.kind == "tips" else par_c, t))
        tot += s.par
        tot_dur += s.par * d
        net_dur += (s.par - s.fed_par) * d
        fed += s.fed_par
    # Fed holdings swapped for overnight reserves: same denominator, one-day duration.
    return tot / 1e3, tot_dur / tot, (net_dur + fed * DAY) / tot, fed / 1e3


# ---------------------------------------------------------------- the Fed's MBS
# Nobody publishes the duration of the Fed's MBS book, so it is modeled pool group by pool group.
WAC_SPREAD, DISC_SPREAD, SHOCK = 0.6, 0.8, 0.25     # pool rate over coupon; discount spread; ±25bp
POOL = re.compile(r"(\d+(?:\.\d+)?)%\s+(\d\d)/(\d\d)")   # "UMBS MORTPASS 2.5% 10/50"


def logistic(x):
    return 1 / (1 + math.exp(-x))


def cpr(incentive, seasoned):
    """Annual prepayment rate: housing turnover (3.5-7%, lower when locked in) plus a
    refinancing S-curve in (pool rate - mortgage rate), halved for pools 2+ years old."""
    refi = 0.35 * logistic((incentive - 1.0) / 0.45) * (0.5 if seasoned else 1.0)
    return 0.035 + 0.035 * logistic((incentive + 0.75) / 0.35) + refi


def pool_price(n, coupon, mortgage_rate, curve, shift, seasoned):
    wac = coupon + WAC_SPREAD
    smm = 1 - (1 - cpr(wac - (mortgage_rate + shift), seasoned)) ** (1 / 12)
    i, bal, pv = wac / 1200, 100.0, 0.0
    for k in range(1, n + 1):
        pmt = bal * i / (1 - (1 + i) ** -(n - k + 1))
        sched = pmt - bal * i
        prepay = (bal - sched) * smm
        cf = bal * coupon / 1200 + sched + prepay        # the investor gets the pass-through coupon
        bal -= sched + prepay
        t = k / 12
        y = (interp(curve, t) + DISC_SPREAD + shift) / 200
        pv += cf / (1 + y) ** (2 * t)
        if bal < 1e-6:
            break
    return pv


def pool_duration(n, coupon, mortgage_rate, curve, seasoned):
    """Effective duration from ±25bp shocks to the curve and the mortgage rate together."""
    p0, up, dn = (pool_price(n, coupon, mortgage_rate, curve, s, seasoned) for s in (0, SHOCK, -SHOCK))
    return (dn - up) / (2 * p0 * SHOCK / 100)


def mortgage_rate(weekly, asof):
    """Freddie Mac's weekly survey rate averaged over asof's month (latest week if none yet)."""
    month = weekly[(weekly.index.year == asof.year) & (weekly.index.month == asof.month)]
    return month.mean() if len(month) else weekly.iloc[-1]


def fed_long_assets_dollar_duration(soma_date, pmms30, pmms15):
    """Sum of face ($bn) x duration over the Fed's agency MBS, agency CMBS and agency debt."""
    asof = dt.date.fromisoformat(soma_date)
    curve = curve_on("par", asof, PAR_TENORS)
    r30, r15 = mortgage_rate(pmms30, asof), mortgage_rate(pmms15, asof)
    groups, dd = {}, 0.0
    for h in soma_agency(soma_date):
        if h["securityType"] == "Agency Debts":         # agency debt: priced as plain bonds
            par = float(h.get("parValue") or 0) / 1e9
            t = (dt.date.fromisoformat(h["maturityDate"][:10]) - asof).days / 365.25
            if par > 0 and t > 0:
                dd += par * macaulay("note", t, float(h.get("coupon") or 0), interp(curve, t))
            continue
        face = float(h.get("currentFaceValue") or 0) / 1e9      # MBS and CMBS: remaining face
        m = POOL.search(h.get("securityDescription") or "")
        if face <= 0 or not m:
            continue
        yy = int(m.group(3)) + (2000 if int(m.group(3)) < 70 else 1900)
        kind = "cmbs" if h["securityType"] == "CMBS" else ("15" if h.get("term") == "15yr" else "30")
        months_left = (yy - asof.year) * 12 + int(m.group(2)) - asof.month
        key = (kind, float(m.group(1)), months_left)       # pool groups: type, coupon, months left
        groups[key] = groups.get(key, 0.0) + face
    for (kind, coupon, n), face in groups.items():
        if n <= 0:
            continue
        if kind == "cmbs":                                  # agency CMBS: priced as plain bonds
            dd += face * macaulay("note", n / 12, coupon, interp(curve, n / 12))
            continue
        term = 180 if kind == "15" or n <= 180 else 360    # original term, months
        rate = r15 if term == 180 else r30
        dd += face * pool_duration(n, coupon, rate, curve, seasoned=(term - n) >= 24)
    return dd


# ---------------------------------------------------------------- the monthly panel
def main():
    ap = argparse.ArgumentParser()
    default = (pd.Timestamp.today() - pd.DateOffset(months=36)).strftime("%Y-%m")
    ap.add_argument("--since", default=default, help="first month, YYYY-MM (the chart starts 2007-01)")
    since = ap.parse_args().since

    dates = soma_asof_dates()
    # Freddie Mac's Primary Mortgage Market Survey, 30- and 15-year fixed rates, weekly.
    pmms30, pmms15 = fred("MORTGAGE30US", "2008-01-01"), fred("MORTGAGE15US", "2008-01-01")
    rows = []
    for me in pd.date_range(since, pd.Timestamp.today(), freq="ME"):
        month_end = me.date()
        soma_date = soma_asof_for(month_end, dates)
        month = treasury_month(month_end, soma_date)
        if month is None:
            continue
        par_bn, all_debt, net_fed, fed_bn = month
        # The site rounds net_fed to four decimals before subtracting the MBS leg; so does this.
        net_fed, par_bn = round(net_fed, 4), round(par_bn, 1)
        incl_mbs = None
        if month_end.strftime("%Y-%m") >= MBS_START:
            incl_mbs = net_fed - fed_long_assets_dollar_duration(soma_date, pmms30, pmms15) / par_bn
        rows.append(dict(date=me, all_debt=all_debt, net_fed=net_fed, incl_mbs=incl_mbs,
                         par_bn=par_bn, fed_share_pct=100 * fed_bn / par_bn, soma_date=soma_date))
        print(f"  {month_end}  {all_debt:.4f}  {net_fed:.4f}  "
              f"{'' if incl_mbs is None else f'{incl_mbs:.4f}'}", flush=True)
    out = pd.DataFrame(rows).set_index("date")
    save(out, HERE, "treasury_duration")
    print(out.tail(3).round(4).to_string())


if __name__ == "__main__":
    main()
