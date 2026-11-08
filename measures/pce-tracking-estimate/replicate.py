"""Econvitals PCE Tracking Estimate — econvitals.org/inflation/#pce (the lead line and tracker charts).

    python replicate.py        # needs BEA_API_KEY; the BLS price indexes come from BLS's bulk files

BEA builds the PCE price index from about 220 detailed components and prices almost every one of
them with a BLS index that is already public when BEA publishes: the CPI for most of spending,
producer prices (PPI) for health care, airfares, financial services and insurance, and import
prices for foreign air travel. This script redoes that assembly with BEA's own map of sources
(inputs/pce_leaf_map.csv), for a month whose PCE BEA has not yet published:

  1. Translate. Each component's one-month change is the change in its BLS source (or a fixed
     blend of several, with weights fitted to BEA's own history of the component). Where BEA
     seasonally adjusts an unadjusted BLS index itself, we adjust it too (with X-13 if you have
     it, see common/tracking.py) and then add an "implied seasonal factor": the average, for
     this calendar month over the past five years, of the gap between BEA's published change
     and the translated one.
  2. Fill. A component whose source is not out yet, or that BEA prices with no monthly source
     at all (about a tenth of core: nonprofits, bank services without explicit charges, life
     insurance, foreign travel...), gets its own average change over the last 12 months.
  3. Add up. Weight the components by last month's spending shares (BEA's nominal table).
     Once producer prices are in, take 1.4 basis points off core (and a little more off the
     core variants), the average gap between this translation and BEA's first print.

It does this for every month of the last three years at each stage — after the CPI, after the
CPI and PPI, after all three — using only BEA data through the month before, as the estimate
would have been made at the time. Writes output/pce_tracking.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_wide, save  # noqa: E402
from common.tracking import (bls_levels, mom, seasonal_adjust, trimmed_mean,  # noqa: E402
                             weighted_median)

MONTHS_BACK = 36
STAGES = {"post_cpi": {"cpi"}, "post_ppi": {"cpi", "ppi"}, "post_import": {"cpi", "ppi", "import"}}
FIRST_PRINT_OFFSET_BP = {"core": 1.4, "core_ex_housing": 1.7, "core_ex_housing_used": 1.7,
                         "core_services_ex_housing": 2.1}   # applied once the PPI is in
IMPLIED_YEARS = 5
FILL_MONTHS = 12
# One series per release that says whether that release is out for a month yet.
RELEASE_ANCHOR = {"cpi": "CUSR0000SA0", "ppi": "PCU622110622110", "import": "EIUIV142"}

# ------------------------------------------------------------------------------ inputs
leaves = pd.read_csv(HERE / "inputs" / "pce_leaf_map.csv").set_index("line")
leaves["series"] = leaves["series"].fillna("").map(
    lambda s: [tuple(x.split(":")) for x in s.split(";") if x])        # [(series id, sa rule)]
dallas = pd.read_csv(HERE / "inputs" / "dallas_trimmed_mean_components.csv")
dallas["leaf_lines"] = dallas["leaf_lines"].fillna("").map(
    lambda s: [int(x) for x in str(s).split(";") if x])


def bea_table(name: str) -> pd.DataFrame:
    """A BEA underlying-detail table, one column per line, on a monthly PeriodIndex."""
    years = ",".join(str(y) for y in range(2008, pd.Timestamp.today().year + 1))
    df = bea_wide(name, "M", years, dataset="NIUnderlyingDetail")
    df.index = df.index.to_period("M")
    return df


prices = bea_table("U20404")     # Table 2.4.4U: price indexes by product (seasonally adjusted)
nominal = bea_table("U20405")    # Table 2.4.5U: spending by product, current dollars
pub_mom = prices.apply(mom)      # BEA's published one-month changes, %

ids = {sid for lst in leaves["series"] for sid, _ in lst}
ids |= set(leaves["gap_proxy"].dropna()) | set(RELEASE_ANCHOR.values())
levels = bls_levels(ids)
missing = sorted(ids - set(levels))
if missing:
    print("not in BLS's bulk files (left out of their blends):", ", ".join(missing))


# ------------------------------------------------------------------------------ step 1: translate
def source_mom(sid: str, sa_rule: str):
    """One-month % change of a BLS source series. sa_rule: 'bls' = BLS's own seasonally adjusted
    series, 'none' = used as published, 'own' = unadjusted, adjusted here (BEA does it itself)."""
    if sid not in levels or len(levels[sid]) < 14:
        return None
    lv = levels[sid]
    # BEA runs X-13 itself: used here when it is installed (X13PATH), else a stand-in
    return mom(seasonal_adjust(lv, "2008-01", x13=True) if sa_rule == "own" else lv)


SRC = {(sid, sa): source_mom(sid, sa) for lst in leaves["series"] for sid, sa in lst}


def nnls_weights(y: pd.Series, X: pd.DataFrame) -> np.ndarray:
    """Non-negative weights summing to one that best fit y = X w. Least squares, dropping any
    series that comes out negative and refitting (with two to six series this is exact)."""
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    cols = list(X.columns)
    if len(d) < 18:
        return np.repeat(1 / len(cols), len(cols))
    keep = list(cols)
    while keep:
        b, *_ = np.linalg.lstsq(d[keep].values, d["y"].values, rcond=None)
        if (b >= 0).all():
            break
        keep = [c for c, bi in zip(keep, b) if bi > min(b)]   # drop the most negative
    w = pd.Series(0.0, index=cols)
    if keep and b.sum() > 0:
        w[keep] = b / b.sum()
    else:
        w[:] = 1 / len(cols)
    return w.values


def translated(line: int, through: pd.Period) -> pd.Series | None:
    """The component's one-month change implied by its source(s), every month."""
    leaf = leaves.loc[line]
    parts = [SRC[s] for s in leaf["series"]]
    if leaf["kind"] in ("cpi", "ppi"):
        return parts[0]
    if leaf["kind"] != "composite":
        return None
    have = [(i, p) for i, p in enumerate(parts) if p is not None]
    if not have:
        return None
    X = pd.DataFrame({i: p for i, p in have})
    if leaf["weights"] == "fit":     # BEA publishes no weights for its blends: fit them
        y = pub_mom[line].loc[pd.Period(leaf["fit_start"], "M"):through]
        w = nnls_weights(y, X)
    else:
        w = np.array([float(x) for x in leaf["weights"].split(";")])[[i for i, _ in have]]
    ok = X.notna().values
    num = np.nansum(X.values * w, axis=1)
    den = (ok * w).sum(axis=1)       # renormalize over the parts published that month
    return pd.Series(np.where(den > 0, num / np.where(den > 0, den, 1), np.nan), index=X.index)


def regress_on(y: pd.Series, x: pd.Series, month, through, max_slope: float) -> float | None:
    """Fit BEA's component on a related series over the last five years; read off this month."""
    if month not in x.index or pd.isna(x.get(month)):
        return None
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    d = d[(d.index <= through) & (d.index > through - 60)]
    if len(d) < 24 or d["x"].std() == 0:
        return None
    b = min(max(np.cov(d["x"], d["y"])[0, 1] / d["x"].var(), 0.0), max_slope)
    return float(d["y"].mean() + b * (x[month] - d["x"].mean()))


def implied_factor(line: int, raw: pd.Series, month, through) -> float:
    """Average gap between BEA's change and the translated one, same calendar month, 5 years."""
    gap = (pub_mom[line] - raw).dropna()
    gap = gap[(gap.index <= through) & (gap.index > through - 12 * IMPLIED_YEARS)]
    same = gap[gap.index.month == month.month]
    if len(same) >= 2:
        return float(same.mean())
    return float(gap.mean()) if len(gap) else 0.0


# ------------------------------------------------------------------------------ steps 2 and 3
def estimate(month: pd.Period, released: set) -> dict:
    through = month - 1                       # the newest BEA month the estimate may use
    rows = []
    for line, leaf in leaves.iterrows():
        val, status = np.nan, "filled"
        raw = translated(line, through) if leaf["release"] in released else None
        if raw is not None and month in raw.index and pd.notna(raw.get(month)):
            if leaf["damped"]:            # BEA smooths these with a judgmental trend
                val = regress_on(pub_mom[line], raw, month, through, 1.0)
            if pd.isna(val):
                val = raw[month]
                if any(sa == "own" for _, sa in leaf["series"]):
                    val += implied_factor(line, raw, month, through)
            status = "released"
        elif leaf["release"] in released and pd.notna(leaf["gap_proxy"]) and leaf["gap_proxy"] in levels:
            # BLS has stopped publishing this item; its parent stands in
            val = regress_on(pub_mom[line], mom(levels[leaf["gap_proxy"]]), month, through, 1.5)
            status = "released" if val is not None else "filled"
        if status == "filled" or val is None or pd.isna(val):
            status = "filled"
            if leaf["kind"] == "constant":
                val = float(leaf["constant"])
            else:
                hist = pub_mom[line].loc[:through].dropna()
                val = float(hist.iloc[-FILL_MONTHS:].mean()) if len(hist) else 0.0
        share = leaf["sign"] * nominal.at[through, line] / nominal.at[through, 1] * 100
        rows.append(dict(line=line, mom=val, share=0.0 if pd.isna(share) else share, status=status))
    d = pd.DataFrame(rows).set_index("line").join(leaves[["group", "housing", "services",
                                                           "used_vehicles", "market_based_excluded"]])

    def avg(mask) -> float:           # share-weighted average change of a set of components
        sh = d.loc[mask, "share"]
        return float((sh / sh.sum() * d.loc[mask, "mom"]).sum())

    core = d["group"] == "core"
    out = {
        "overall": float((d["share"] / 100 * d["mom"]).sum()),
        "core": avg(core),
        "core_ex_housing": avg(core & (d["housing"] == 0)),
        "core_ex_housing_used": avg(core & (d["housing"] == 0) & (d["used_vehicles"] == 0)),
        "core_services_ex_housing": avg(core & (d["housing"] == 0) & (d["services"] == 1)),
        "market_based_core": avg(core & (d["market_based_excluded"] == 0)),
    }
    # Dallas Fed trimmed mean and median, on the Dallas Fed's 177 components
    comp = []
    for c in dallas.itertuples():
        kids = [k for k in c.leaf_lines if k in d.index]
        sh = d.loc[kids, "share"]
        if kids and sh.sum() > 0:
            comp.append(((sh / sh.sum() * d.loc[kids, "mom"]).sum(), sh.sum()))
    x, w = np.array([c[0] for c in comp]), np.array([c[1] for c in comp])
    out["median"] = weighted_median(x, w)
    out["trimmed_mean"] = trimmed_mean(x, w, 0.24, 0.31)
    out["core_before_offset"] = out["core"]
    if "ppi" in released:
        for k, bp in FIRST_PRINT_OFFSET_BP.items():
            out[k] -= bp / 100
    out["known_share_core"] = float(d.loc[core & (d["status"] == "released"), "share"].sum()
                                    / d.loc[core, "share"].sum() * 100)
    return out


def out_for(month: pd.Period) -> set:
    return {r for r, sid in RELEASE_ANCHOR.items() if month in levels.get(sid, pd.Series(dtype=float)).index}


newest = levels[RELEASE_ANCHOR["cpi"]].index.max()
months = [m for m in pd.period_range(newest - MONTHS_BACK + 1, newest, freq="M")
          if m - 1 in nominal.index and "cpi" in out_for(m)]
rows = []
for m in months:
    for stage, rel in STAGES.items():
        if rel <= out_for(m):
            r = estimate(m, rel)
            bea_head, bea_core = pub_mom.at[m, 1] if m in pub_mom.index else np.nan, \
                pub_mom.at[m, 374] if m in pub_mom.index else np.nan
            rows.append(dict(record=f"{m} {stage}", month=str(m), stage=stage, **r,
                             bea_overall=bea_head, bea_core=bea_core))
res = pd.DataFrame(rows).set_index("record")
save(res, HERE, "pce_tracking")

# How close to BEA's own numbers (its history as published today) the method gets, by stage.
done = res.dropna(subset=["bea_core"])
miss = (done["core_before_offset"] - done["bea_core"]).abs().groupby(done["stage"]).mean() * 100
print("average miss on core PCE against BEA's current history, basis points:",
      ", ".join(f"{s} {miss.get(s, np.nan):.1f}" for s in STAGES))
print(res[["overall", "core", "core_before_offset", "median", "trimmed_mean",
           "bea_overall", "bea_core"]].tail(6).round(3).to_string())
