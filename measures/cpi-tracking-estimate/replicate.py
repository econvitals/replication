"""Econvitals CPI Tracking Estimate — a forecast of the coming month's CPI, every cut.

    python replicate.py        # needs FRED_API_KEY and EIA_API_KEY; BLS data come from bulk files

A few days before BLS publishes a month's CPI, Econvitals estimates it for twelve cuts: all items,
core, core goods, core services, shelter, core services ex shelter, core ex shelter, core ex
shelter and used cars, food, energy, and the Cleveland Fed's median and 16% trimmed mean.

How the number is made:
  1. The basket is 49 pieces (inputs/cpi_pieces.csv) whose relative-importance weights add to
     nearly all of the CPI; each cut is the weighted sum of its pieces at last month's weights.
  2. Every piece gets every candidate estimate: its own 3-, 6-, 12- and 24-month average change,
     its 12-month median, the 12-month average plus half its usual calendar-month pattern, and a
     pull back toward the 12-month average. A few pieces also get an outside series: motor fuel
     and fuel oil the month's average retail gasoline and diesel price (EIA), less the usual
     seasonal gap; piped gas the Henry Hub price one to three months back; rent and owners'
     equivalent rent a fit on their own 3- and 12-month pace and the reading six months back.
  3. Each month a piece uses the candidate with the smallest average miss over the previous 48
     months (at least 24 scored), using nothing from that month or later.
  4. The median and trimmed mean sort the Cleveland Fed's 45 components (each estimated the same
     way) at the Cleveland Fed's weights.

This script runs that for every month since 2015 BLS has published (a back-cast: each month
estimated only from what came before it) and writes output/cpi_tracking.csv beside the published
outcome. It stops at the newest month BLS has published; it never writes an estimate of a month
not yet out.
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bls_flat, eia, fred, get, save  # noqa: E402
from common.tracking import bls_levels, mom, seasonal_adjust, trimmed_mean, weighted_median  # noqa: E402

START, SHOW_FROM = pd.Period("2013-01", "M"), pd.Period("2015-01", "M")
LOOKBACK, MIN_SCORED, MIN_COVERAGE = 48, 24, 0.8
CLEVELAND_WEIGHTS = ("https://www.clevelandfed.org/-/media/files/webcharts/mediancpi/"
                     "mediancpi_component_table.csv?sc_lang=en")
CUTS = {"headline": ("food", "energy", "core_goods", "shelter", "core_services"),
        "core": ("core_goods", "shelter", "core_services"),
        "food": ("food",), "energy": ("energy",), "core_goods": ("core_goods",),
        "core_services": ("shelter", "core_services"), "shelter": ("shelter",),
        "core_services_ex_shelter": ("core_services",),
        "core_ex_shelter": ("core_goods", "core_services")}

pieces = pd.read_csv(HERE / "inputs" / "cpi_pieces.csv").fillna("")
published = pd.read_csv(HERE / "inputs" / "cpi_published_cuts.csv")
comp = pd.read_csv(HERE / "inputs" / "cleveland_median_cpi_components.csv")


def level_id(p) -> str:
    return ("CUUR0000" if p.unadjusted else "CUSR0000") + p.item


# ------------------------------------------------------------------------------ data
ids = {level_id(p) for p in pieces.itertuples() if not p.residual_of}
ids |= {"CUSR0000" + p.residual_of for p in pieces.itertuples() if p.residual_of}
ids |= {"CUUR0000SETB", "CUUR0000SEHE", "CUSR0000SETB", "CUSR0000SEHE"}
ids |= {"CUSR0000" + c for c in published["bls_item"]}
national = [s for s in comp["bls_series"] if s[4:8] == "0000"]
ids |= set(national) | {"CUUR" + s[4:] for s in national}
L = bls_levels(ids)
for s in comp["bls_series"]:                 # the four regional OER indexes, from FRED
    if s not in L:
        x = fred(s)
        x.index = x.index.to_period("M")
        L[s] = x

# Relative importance (BLS's weights), from the CPI bulk "aspect" file: aspect type I.
asp = bls_flat("cu", "cu.aspect")
asp = asp[(asp["aspect_type"] == "I") & asp["period"].str.match(r"M(0[1-9]|1[0-2])$")
          & asp["series_id"].str.startswith("CUUR0000")]
asp = asp.assign(month=pd.PeriodIndex(asp["year"] + "-" + asp["period"].str[1:], freq="M"),
                 item=asp["series_id"].str[8:], value=pd.to_numeric(asp["value"], errors="coerce"))
RI = asp.pivot_table(index="month", columns="item", values="value").sort_index()


def eia_monthly(route: str, series: str, freq: str) -> pd.Series:
    """Monthly average of an EIA price series, read page by page."""
    rows, offset = [], 0
    while True:
        d = eia(route, {"frequency": freq, "data[0]": "value", "facets[series][]": series,
                        "sort[0][column]": "period", "sort[0][direction]": "asc",
                        "length": 5000, "offset": offset})
        rows.append(d)
        if len(d) < 5000:
            break
        offset += 5000
    d = pd.concat(rows)
    s = pd.Series(pd.to_numeric(d["value"], errors="coerce").values,
                  index=pd.to_datetime(d["period"])).dropna()
    return s.groupby(s.index.to_period("M")).mean().sort_index()


def pct(s: pd.Series) -> pd.Series:
    return s.pct_change(fill_method=None) * 100


GAS = pct(eia_monthly("petroleum/pri/gnd/data", "EMM_EPMR_PTE_NUS_DPG", "weekly"))  # regular
DIESEL = pct(eia_monthly("petroleum/pri/gnd/data", "EMD_EPD2D_PTE_NUS_DPG", "weekly"))
HUB = pct(eia_monthly("natural-gas/pri/fut/data", "RNGWHHD", "daily"))             # Henry Hub


def full_mom(level: pd.Series) -> pd.Series:
    return mom(level.loc["2006-01":])


# One-month change of each piece; household operations (no longer published) is backed out
# of household furnishings and operations less household furnishings and supplies.
M, W = {}, {}
for p in pieces.itertuples():
    if not p.residual_of:
        M[p.item], W[p.item] = full_mom(L[level_id(p)]), RI[p.item]
for p in pieces.itertuples():
    if p.residual_of:
        less = p.less.split(";")
        wp, wk = RI[p.residual_of], sum(RI[k] for k in less)
        mp = full_mom(L["CUSR0000" + p.residual_of])
        M[p.item] = (wp.shift(1) * mp - sum(RI[k].shift(1) * M[k] for k in less)) / (wp - wk).shift(1)
        W[p.item] = wp - wk
M, W = pd.DataFrame(M), pd.DataFrame(W)

# The Cleveland Fed's 45 components: changes (regional OER adjusted here; BLS publishes it
# unadjusted only) and weights (the Cleveland Fed's current weights rolled back through history
# with each component's unadjusted index).
anchor = pd.read_csv(io.StringIO(get(CLEVELAND_WEIGHTS)))
anchor = dict(zip(anchor["Component"], anchor["Relative Importance (Normalized)"].astype(float)))
CM, CW = {}, {}
for c in comp.itertuples():
    lvl = L[c.bls_series].loc["2006-01":].dropna()
    if c.adjust_here == "yes":
        lvl = seasonal_adjust(lvl, "2006-01")
    CM[c.component], CW[c.component] = mom(lvl), L["CUUR" + c.bls_series[4:]].loc["2006-01":]
CM, CW = pd.DataFrame(CM), pd.DataFrame(CW)
t0 = CW.dropna().index[-1]
CW = CW * pd.Series({n: anchor[n] / CW.at[t0, n] for n in CW.columns})
CW = CW.div(CW.sum(axis=1), axis=0)
CODE = dict(zip(comp["component"], comp["bls_series"].str[8:]))


# ------------------------------------------------------------------------------ candidates
def own(m: pd.Series, t: pd.Period) -> dict:
    """Estimates of month t from the piece's own past (m holds no missing months)."""
    hist = m.loc[:t - 1]
    out = {}
    for n in (3, 6, 12, 24):
        x = hist.tail(n)
        out[f"mean{n}"] = float(x.mean()) if len(x) >= n // 2 else np.nan
    x = hist.tail(12)
    out["median12"] = float(x.median()) if len(x) >= 6 else np.nan
    # the 12-month mean plus half this calendar month's average gap over the past four years
    gaps = []
    for k in range(1, 5):
        s = t - 12 * k
        if s in m.index:
            prior = m.loc[:s - 1].tail(12)
            if len(prior) >= 6:
                gaps.append(float(m.loc[s] - prior.mean()))
    out["seasonal12"] = (float(x.mean()) + (0.5 * np.mean(gaps) if len(gaps) >= 2 else 0.0)
                         if len(x) >= 6 else np.nan)
    # pull back toward the 12-month mean by however much last month's gap has tended to echo
    out["revert12"] = np.nan
    if len(hist) >= 48:
        roll = hist.shift(1).rolling(12, min_periods=6).mean()
        d = pd.DataFrame({"y": hist - roll, "x": (hist - roll).shift(1)}).dropna().tail(84)
        if len(d) >= 36 and d["x"].var() != 0:
            beta = float(np.clip((d["x"] * d["y"]).sum() / (d["x"] ** 2).sum(), -0.6, 0.6))
            out["revert12"] = float(x.mean() + beta * (hist.iloc[-1] - x.mean()))
    return out


def regress(y: pd.Series, X: pd.DataFrame, t: pd.Period, window: int) -> float:
    """Least squares of y on X over the `window` months before t, read at t."""
    X = X.reindex(pd.period_range(X.index.min(), max(X.index.max(), t), freq="M"))
    d = pd.concat([y.rename("y"), X], axis=1).loc[:t - 1].dropna().tail(window)
    if len(d) < 36 or t not in X.index or X.loc[t].isna().any():
        return np.nan
    A = np.column_stack([np.ones(len(d)), d[X.columns].values])
    b, *_ = np.linalg.lstsq(A, d["y"].values, rcond=None)
    return float(b[0] + X.loc[t].values @ b[1:])


def seasonal_gap(item: str, t: pd.Period) -> float:
    """What seasonal adjustment takes off this calendar month (latest earlier year that has it)."""
    gap = full_mom(L["CUUR0000" + item]) - full_mom(L["CUSR0000" + item])
    for k in range(1, 4):
        v = gap.get(t - 12 * k, np.nan)
        if pd.notna(v):
            return float(v)
    return np.nan


def outside(item: str, m: pd.Series, t: pd.Period) -> dict:
    out = {}
    if item in ("SETB", "SEHE"):      # motor fuel, fuel oil: the month's retail fuel price
        src = GAS if item == "SETB" else DIESEL
        est = regress(full_mom(L["CUUR0000" + item]), pd.DataFrame({"x0": src, "x1": src.shift(1)}),
                      t, 120)
        gap = seasonal_gap(item, t)
        if not (np.isnan(est) or np.isnan(gap)):
            out["fuel_price"] = est - gap
    if item == "SEHF02":              # piped gas: Henry Hub one to three months back
        out["henry_hub"] = regress(m, pd.DataFrame({f"h{k}": HUB.shift(k) for k in (1, 2, 3)}), t, 120)
    if item in ("SEHA", "SEHC"):      # rent, owners' equivalent rent: their own pace
        h = pd.DataFrame({"m3": m.shift(1).rolling(3, min_periods=2).mean(),
                          "m12": m.shift(1).rolling(12, min_periods=6).mean(), "m6": m.shift(6)})
        out["rent_own"] = regress(m, h, t, 84)
    return out


def picks(frame: pd.DataFrame, code: dict, months) -> pd.DataFrame:
    """Each piece's chosen estimate, by month: the candidate with the smallest average miss over
    the previous LOOKBACK months (12-month mean until enough months are scored)."""
    chosen = {}
    for col in frame.columns:
        m = frame[col].dropna()
        est = pd.DataFrame({t: {**own(m, t), **outside(code[col], m, t)} for t in months}).T
        est = est[sorted(est.columns)]
        miss = est.sub(frame[col].reindex(est.index), axis=0).abs()
        score = miss.rolling(LOOKBACK, min_periods=MIN_SCORED).mean().shift(1)
        vals = {}
        for t in est.index:
            r = score.loc[t].dropna()
            r = r[est.loc[t, r.index].notna()]
            v = est.at[t, r.idxmin()] if len(r) else np.nan
            vals[t] = est.at[t, "mean12"] if pd.isna(v) else v
        chosen[col] = pd.Series(vals)
    return pd.DataFrame(chosen)


def aggregate(m: pd.DataFrame, cut: str) -> pd.Series:
    """Weighted change of a cut's pieces at last month's weights (blank if under 80% covered)."""
    if cut == "core_ex_shelter_used":
        ids_ = [p.item for p in pieces.itertuples() if p.group in CUTS["core_ex_shelter"] and not p.used_cars]
    else:
        ids_ = [p.item for p in pieces.itertuples() if p.group in CUTS[cut]]
    full = pd.period_range(W.index.min(), max(W.index.max(), m.index.max()), freq="M")
    lag = W[ids_].reindex(full).ffill().shift(1).reindex(m.index)
    x = m[ids_]
    ok = x.notna() & lag.notna()
    covered = lag.where(ok, 0).sum(axis=1)
    out = (x.where(ok, 0) * lag.where(ok, 0)).sum(axis=1) / covered
    return out.where(covered >= MIN_COVERAGE * lag.sum(axis=1))


# ------------------------------------------------------------------------------ the back-cast
last = L["CUSR0000SA0"].index.max()          # the newest month BLS has published
months = pd.period_range(START, last, freq="M")
P = picks(M, {c: c for c in M.columns}, months)
PC = picks(CM, CODE, months)

res = pd.DataFrame(index=months)
for cut in list(CUTS) + ["core_ex_shelter_used"]:
    res[cut] = aggregate(P.reindex(months), cut)
for t in months:
    w = CW.loc[:t - 1].dropna()
    if not len(w):
        continue
    x, w = PC.loc[t].values.astype(float), w.iloc[-1].values
    ok = np.isfinite(x) & np.isfinite(w)          # components with no estimate are left out
    res.loc[t, "median"] = weighted_median(x[ok], w[ok])
    res.loc[t, "trimmed"] = trimmed_mean(x[ok], w[ok], 0.08, 0.08)

# What BLS (and the Cleveland Fed) then published, for scoring.
for r in published.itertuples():
    res[f"{r.cut}_published"] = full_mom(L["CUSR0000" + r.bls_item]).reindex(months)
res["core_services_ex_shelter_published"] = aggregate(M.reindex(months), "core_services_ex_shelter")
for cut, sid in (("median", "MEDCPIM157SFRBCLE"), ("trimmed", "TRMMEANCPIM157SFRBCLE")):
    s = fred(sid)
    s.index = s.index.to_period("M")
    res[f"{cut}_published"] = s.reindex(months)
res = res.loc[SHOW_FROM:]
res.index = res.index.to_timestamp()
save(res, HERE, "cpi_tracking")

cuts = [c for c in res.columns if not c.endswith("_published")]
recent = res.loc["2022-01":]
mae = {c: (recent[c] - recent[f"{c}_published"]).abs().mean() for c in cuts}
print("average miss since 2022, percentage points:", ", ".join(f"{c} {v:.3f}" for c, v in mae.items()))
print(res[["headline", "headline_published", "core", "core_published", "median", "trimmed"]]
      .tail(6).round(3).to_string())
