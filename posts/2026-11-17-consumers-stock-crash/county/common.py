"""Shared regression helper for the county stock-wealth regressions (pyfixest)."""
import numpy as np, pandas as pd, pyfixest as pf

LAGS = [f"SR_l{j}" for j in range(1, 9)]
CTRL = ["S_bond", "S_hpi", "S_lab", "S_bus"]

def load(out):
    P = pd.read_parquet(f"{out}/panel.parquet")
    return P

def sample(P, start, end, baseline=True, drop=None):
    """Shock quarters start..end (strings like '1992Q1'); baseline drops late filers and top-5% large-firm counties.
    drop: (h, lo, hi) removes shocks whose window t-1..t+h overlaps lo..hi."""
    x = P[(P.q >= start) & (P.q <= end) & P.pop2010.notna()]
    if baseline:
        x = x[~x.late_filer & ~x.large_top5.fillna(False)]
    if drop is not None:
        h, lo, hi = drop
        q = pd.PeriodIndex(x.q, freq="Q")
        a = (q - 1).astype(str); b = (q + h).astype(str)
        x = x[~((b >= lo) & (a <= hi))]
    return x

def fit(x, dep, h, main="SR", controls=True, bartik=True, lags=True, extra=None, vcov=None):
    rhs = [main] if isinstance(main, str) else list(main)
    if lags: rhs += LAGS
    if controls: rhs += CTRL
    if bartik: rhs += [f"bartik_h{h}"]
    if extra: rhs += extra
    y = f"d{dep}_h{h}"
    cols = list(dict.fromkeys([y] + rhs + ["fips", "stq", "q", "pop2010"]))
    d = x[cols].replace([np.inf, -np.inf], np.nan).dropna()
    safe = {c: c.replace("-", "m") for c in [y] + rhs if "-" in c}      # h < 0: a minus sign would be read as subtraction
    if safe:
        d = d.rename(columns=safe); y = safe.get(y, y); rhs = [safe.get(c, c) for c in rhs]
    m = pf.feols(f"{y} ~ {' + '.join(rhs)} | fips + stq", data=d, weights="pop2010",
                 vcov=vcov or {"CRV1": "fips+q"})
    return m, d

def row(m, d, name, **tags):
    t = m.tidy()
    mains = [k for k in t.index if not (k.startswith("SR_l") or k.startswith("S_") or k.startswith("bartik"))]
    r = dict(spec=name, n=len(d), counties=d.fips.nunique(), periods=d.q.nunique(),
             first=d.q.min(), last=d.q.max(), **tags)
    for k in mains:
        r[f"b_{k}"] = 100 * t.loc[k, "Estimate"]; r[f"se_{k}"] = 100 * t.loc[k, "Std. Error"]
    return r

def swap(P, cw, Scol=None, Rcol=None):
    """Rebuild the shock, its lags and the S x aggregate controls with another wealth column of
    county_wealth_q (e.g. 'S_tax') and/or the end-of-quarter total return ('tot')."""
    x = P.copy()
    if Scol is not None:
        s = cw[["fips", "q", Scol]].rename(columns={Scol: "Sx"}).copy()
        s["q"] = pd.PeriodIndex(s.q, freq="Q"); s = s.sort_values(["fips", "q"])
        s["Snew"] = s.groupby("fips").Sx.shift(1); s["q"] = s.q.astype(str)
        x = x.merge(s[["fips", "q", "Snew"]], on=["fips", "q"], how="left")
        for v in ["bond", "hpi", "lab", "bus"]:
            ratio = (P[f"S_{v}"] / P.S_l1).groupby(P.q).median()
            x[f"S_{v}"] = x.Snew * x.q.map(ratio)
        x["S_l1"] = x.Snew
    R = x.R_tot if Rcol == "tot" else x.R
    x["SR"] = x.S_l1 * R
    x = x.sort_values(["fips", "q"])
    for j in range(1, 9):
        x[f"SR_l{j}"] = x.groupby("fips").SR.shift(j)
    return x
