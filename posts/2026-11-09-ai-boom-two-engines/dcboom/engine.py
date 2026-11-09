"""engine.py: the FRB/US experiment, the U.S. economy 2023-2028 with and without the data-center buildout.

MODEL. The Board's FRB/US (bundled under pyfrbus/ and fed/), with business investment and non-oil imports
each split into an exogenous data-center piece and the Board's own equation for everything else
(model_setup.py -> output/model/model_dc.xml). The data-center pieces enter GDP at current nominal shares,
and data-center capital is not counted as productive capacity, so the experiment is a pure demand shock.

BASELINE. The Board's LONGBASE (the 2026-11-04 file: history through 2026Q2, the Board's projection after),
reproduced exactly by tracking residuals from 2023Q1. Nothing here depends on where its history ends: the
residuals, the shock and the stock-gain window all start in 2023Q1 and follow the study's own data, so a newer
LONGBASE changes the baseline the effects are measured around and nothing in the code. Every "without" run
takes the following out of that baseline, from 2023Q1:
  * investment: the excess of BEA computers + communication equipment + Census data-center construction
    over their 2015-2022 trends (output/inputs/inv_excess.csv), as a share of nominal GDP, entered as
    negative `edc` (real units at baseline prices). After 2026Q4 the share is held at its 2026Q4 level
    through 2031Q4 and then fades to zero by 2035Q4 (that tail matters only to forward-looking runs and to
    the "if the boom continues" projections);
  * its imports: an import share by type of spending applied to each type's excess (computers 85 percent,
    communication equipment 75 percent, data-center construction 10 percent, all scaled by one factor k
    so the share over 2023Q1-2026Q4 is the target, 75 percent in the post; no share above 100 percent),
    entered as negative `emdc`. After 2026Q4 the import ratio is held at its 2026Q4 value;
  * (switch) the AI stock-market gain: household stock wealth `wpsn` in the without run is pinned lower than
    the run's own world without the stock gain taken out (its first solve: the same run with the stock instrument
    at the baseline, i.e. run A's world for B, the forward-looking run without the gain for C) by the share
    f(t) = G/M of market value that the seven companies' extra gain represents (data/stock_gain.csv). So each run
    takes out the stated gain from its own world, and not the gain plus whatever the buildout did to stock prices
    (Jason Furman, 2026-11-09). The premium construction keeps the earlier drafts' target, the baseline (the actual
    path) times (1 - f), so that it still reproduces them. Two constructions (`stock_mode`):
      - "earnings" (the default): investors' expected growth of real dividends `zdivgr` is lowered through
        its add factor `zdivgr_aerr`; `zdivgr` stays endogenous, and nothing else moves, because `zdivgr`
        appears only in the stock-wealth equation (d log wpsn / d zdivgr = +0.25). So the gain is higher
        expected earnings, and the cost of capital for business investment is left alone;
      - "premium": the equity premium `reqp` (exogenized) is raised (d log wpsn / d reqp = -0.25). The
        premium also enters the cost of capital `rbfi`, so this version boosts business investment too.
        It is the construction in earlier drafts of the post, kept so those results still reproduce.
    Either way the path is found by fixed-point iteration, one full solve per step, until wpsn is within
    0.05 percent of the target over the fitting window, and the instrument's gap is held at its last fitted
    value after the window. Under model-consistent expectations `zdivgr` is forward-looking
    (zdivgr = a*hgynid(+1) + b*zdivgr(+1) + zdivgr_aerr, b = 0.99), so an add factor at t also moves every
    earlier quarter; the earnings step inverts that recursion (`_earnings_step`);
  * (switch, forward-looking runs only) a believed productivity payoff: trend MFP growth `hmfpt` lower by
    `prod` a year from 2027Q1.
Monetary policy: the inertial Taylor rule (rffintay) from 2023Q1. Fiscal policy: the Board's
debt-stabilizing rule. Expectations: VAR (backward-looking) or `mcap+wp` (model-consistent asset prices
and wage-price setting); forward-looking runs let the policy rule's r* learn (drstar = 1).

Every effect is "with minus without" = baseline minus the counterfactual: percent for levels
(100 * (base / cf - 1)), percentage points for rates and shares of GDP.
"""
import io
import time
from contextlib import redirect_stdout

import numpy as np
import pandas as pd

from . import paths

START = pd.Period("2023Q1", freq="Q")
VAR_END = pd.Period("2030Q4", freq="Q")
MCE_END = START + 200 - 1                                  # 2072Q4: 200 quarters for model-consistent runs
SHOW = pd.period_range(START, "2026Q4", freq="Q")          # default window: effects reported, stock gain fitted
DATA_END = pd.Period("2026Q4", freq="Q")
RULES = {"inertial": "rffintay", "balanced": "rfftay"}
BASE_SHARES = {"comp": 0.85, "comm": 0.75, "dcc": 0.10}  # direct import shares by type, before scaling by k
STOCK_MODES = ("earnings", "premium")                     # how the stock gain is removed; the first is the default
STOCK_INSTRUMENT = {"earnings": "zdivgr_aerr", "premium": "reqp"}


# ------------------------------------------------------------------ inputs
def _inv_excess():
    inv = pd.read_csv(paths.OUT_INPUTS / "inv_excess.csv", index_col=0)
    inv.index = pd.PeriodIndex(inv.index, freq="Q")
    return inv


def shock_build(kind="build"):
    """Percent of nominal GDP, quarterly START..MCE_END. Data 2023Q1-2026Q4; then held through 2031Q4 and
    16 equal steps to zero by 2035Q4."""
    inv = _inv_excess()
    idx = pd.period_range(START, MCE_END, freq="Q")
    s = pd.Series(0.0, index=idx)
    s.loc[START:DATA_END] = inv.loc[START:DATA_END, "inv_excess_share"].values
    last = s.loc[DATA_END]
    s.loc["2027Q1":"2031Q4"] = last
    for i in range(16):
        s.loc[pd.Period("2032Q1", freq="Q") + i] = last * (15 - i) / 16
    return s


def shock_grows(kind="build"):
    """The 'keeps growing' variant: from its 2026Q4 level the excess rises 0.5 percent of GDP a year
    through 2028Q4, is held through 2031Q4, then fades to zero by 2035Q4."""
    s = shock_build("build").copy()
    last = s.loc[DATA_END]
    q = pd.period_range(DATA_END + 1, "2028Q4", freq="Q")
    s.loc[q] = last + 0.5 * np.arange(1, len(q) + 1) / 4
    top = s.loc[pd.Period("2028Q4", "Q")]
    s.loc["2029Q1":"2031Q4"] = top
    for i in range(16):
        s.loc[pd.Period("2032Q1", "Q") + i] = top * (15 - i) / 16
    s.loc["2036Q1":] = 0.0
    return s


PATHS = {"build": shock_build, "grows": shock_grows}


def stock_cut():
    """f(t) = G/M, the seven companies' extra gain as a share of total market value, by quarter; after the
    last quarter, held."""
    st = pd.read_csv(paths.DATA / "stock_gain.csv")
    st = st[st["quarter"].astype(str).str.fullmatch(r"\d{4}Q[1-4]")].copy()     # drop the 2022-11-30 base row
    st["q"] = pd.PeriodIndex(st["quarter"], freq="Q")
    st = st[st["q"] >= START].drop_duplicates("q", keep="last").set_index("q")
    f = (st["G"] / st["M"]).astype(float)
    idx = pd.period_range(START, MCE_END, freq="Q")
    return f.reindex(idx).ffill().fillna(0.0)


def import_share_series(target, path="build"):
    """Percent of nominal GDP: the imported part of the buildout, START..MCE_END.
    Returns (series, k, achieved cumulative share, shares by type, import ratio after 2026)."""
    inv = _inv_excess()
    w = inv.loc[START:DATA_END]

    def imp(k):
        a = {c: min(1.0, k * s) for c, s in BASE_SHARES.items()}
        return sum(a[c] * w[f"{c}_excess"] for c in a)
    lo, hi = 0.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        r = imp(k).sum() / w["inv_excess"].sum()
        lo, hi = (k, hi) if r < target else (lo, k)
    m = imp(k)
    s = pd.Series(0.0, index=pd.period_range(START, MCE_END, freq="Q"))
    s.loc[START:DATA_END] = (100 * m / w["ngdp"]).values
    inv_share = PATHS[path]("build")
    ratio_last = float(m.iloc[-1] / w["inv_excess"].iloc[-1])
    s.loc[DATA_END + 1:] = ratio_last * inv_share.loc[DATA_END + 1:].values
    shares = {c: min(1.0, k * v) for c, v in BASE_SHARES.items()}
    return s, k, float(m.sum() / w["inv_excess"].sum()), shares, ratio_last


# ------------------------------------------------------------------ model
_DATA = None


def data():
    global _DATA
    if _DATA is None:
        from pyfrbus.load_data import load_data
        d = load_data(str(paths.LONGBASE))
        d["ebfio"] = d["ebfi"]; d["emoo"] = d["emo"]
        for c in ("edc", "emdc", "kdcsw"):
            d[c] = 0.0
        d["dcw"] = 1.0
        xfsn = d["xgdpn"] - d["ein"]
        d["sbfixfs"] = 0.01 * d["pbfir"] * d["pxp"] / xfsn
        d["semoxfs"] = 0.01 * d["pmo"] / xfsn
        d["sbfixp"] = 0.01 * d["pbfir"] * d["pxp"] / d["xpn"]
        d["nxgdp"] = 100 * (d["exn"] - d["emn"]) / d["xgdpn"]
        d["cagdp"] = 100 * d["fcbn"] / d["xgdpn"]
        _DATA = d
    return _DATA


def base_frame(end, rstar=False):
    d = data().copy()
    if rstar:      # the Board's option: the rule's r* moves toward the real funds rate (drstar = 1)
        d.loc[START:end, "drstar"] = 1
    for k in ["dmpintay", "dmptay", "dmpalt", "dmprr", "dmptlr", "dmptrsh"]:
        d.loc[START:end, k] = 0
    d.loc[START:end, "dmpex"] = 0
    d.loc[START:end, "rfffix"] = d.loc[START:end, "rff"]
    d.loc[START:end, "dfpdbt"] = 1; d.loc[START:end, "dfpsrp"] = 0; d.loc[START:end, "dfpex"] = 0
    return d


_CACHE = {}


def setup(exp, rule="inertial", exog=(), rstar=False):
    key = (exp, rule, tuple(sorted(exog)), rstar)
    if key not in _CACHE:
        from pyfrbus.frbus import Frbus
        end = MCE_END if exp != "var" else VAR_END
        f = Frbus(str(paths.DC_MODEL_XML), mce={"var": None, "mcap": "mcap+wp"}[exp])
        f.append_replace({"rffrule": f"rffrule - rffrule_aerr = dmpex*rfffix + (1-dmpex)*{RULES[rule]}"})
        if exog:
            f.exogenize(sorted(exog))
        with redirect_stdout(io.StringIO()):
            wa = f.init_trac(START, end, base_frame(end, rstar))
        _CACHE[key] = (f, wa, end)
    return _CACHE[key]


def solve(f, end, frame, exp):
    with redirect_stdout(io.StringIO()):
        if exp == "var":
            try:
                return f.solve(START, end, frame)
            except Exception:
                return f.solve(START, end, frame, {"newton": "newton"})
        try:
            return f.solve(START, end, frame, {"maxiter": 60})
        except Exception:                     # fail fast: a non-converging forward-looking run costs minutes
            return f.solve(START, end, frame, {"newton": "trust", "maxiter": 40})


def stock_exog(stock, stock_mode):
    """The variables the stock construction exogenizes: the premium version fixes `reqp`; the earnings
    version moves an add factor and exogenizes nothing."""
    if stock_mode not in STOCK_MODES:
        raise ValueError(f"stock_mode must be one of {STOCK_MODES}, not {stock_mode!r}")
    return ["reqp"] if (stock and stock_mode == "premium") else []


def stock_base(own, wa, q, stock_mode):
    """The stock wealth the without-the-stock-gain target scales by (1 - f): the run's own world before the gain is
    taken out (`own`, its first solve), so the gain removed is the stated one; with the premium construction, the
    baseline, as the earlier drafts had it (they compared with the actual path, which also carries whatever the
    buildout did to stock prices)."""
    if stock_mode == "premium":
        return wa.loc[q, "wpsn"].values
    return own.loc[q, "wpsn"].values.copy()


def _premium_step(gap):
    return -4.0 * gap                                          # d log wpsn / d reqp = -0.25


def _earnings_step(f, exp, n, nS):
    """The change in the `zdivgr_aerr` gap (quarters 0..nS-1 of a solve n quarters long, the last value held
    to the end) that moves log wpsn by `gap` over the fitting window, through the direct channel
    d log wpsn / d zdivgr = +0.25. With VAR expectations zdivgr moves one for one with its add factor in the
    same quarter, so the step is 4 * gap, the premium step with the sign flipped. With model-consistent
    expectations zdivgr(t) = a*hgynid(t+1) + b*zdivgr(t+1) + zdivgr_aerr(t), with zdivgr after the last
    quarter fixed at the baseline, so a change da in the add factor moves zdivgr by
    dz(t) = sum_k b^k da(t+k). To move zdivgr by d = 4 * gap: da(t) = d(t) - b*d(t+1) inside the window,
    and the held last value da = d(nS-1) / (1 + b + ... + b^(n-nS)). The general-equilibrium responses
    (profits, interest rates) are left to the next iteration, as in the premium version."""
    if exp == "var":
        return lambda gap: 4.0 * gap
    b = float(f.constants["y_zdivgr_2"])
    held = (1.0 - b ** (n - nS + 1)) / (1.0 - b)

    def step(gap):
        d = 4.0 * gap
        dx = np.empty_like(d)
        dx[:-1] = d[:-1] - b * d[1:]
        dx[-1] = d[-1] / held
        return dx
    return step


def counterfactual(exp="var", target=0.75, prod=0.0, stock=False, rstar=False, warm=None, tol=5e-4, maxit=8,
                   path="build", fit=SHOW, stock_mode="earnings"):
    """Solve one without-the-boom run. `fit` = the quarters over which the stock-wealth target is hit (the
    instrument's gap is held at its last fitted value afterwards). `stock_mode` = how the stock gain is
    removed: "earnings" (lower expected dividend growth, the default) or "premium" (a higher equity premium,
    the construction in earlier drafts of the post). Returns (cf, base, info)."""
    exog = (["hmfpt"] if prod else []) + stock_exog(stock, stock_mode)
    f, wa, end = setup(exp, "inertial", tuple(exog), rstar)
    fr = wa.copy()
    q = pd.period_range(START, end, freq="Q")
    s = PATHS[path]("build").loc[q].values / 100.0
    mshare, k, achieved, shares, ratio_last = import_share_series(target, path)
    ngdp = wa.loc[q, "xgdpn"].values
    fr.loc[q, "edc"] = -s * ngdp / (0.01 * wa.loc[q, "pbfir"].values * wa.loc[q, "pxp"].values)
    fr.loc[q, "emdc"] = -(mshare.loc[q].values / 100.0) * ngdp / (0.01 * wa.loc[q, "pmo"].values)
    if prod:
        q2 = pd.period_range("2027Q1", end, freq="Q")
        fr.loc[q2, "hmfpt"] = wa.loc[q2, "hmfpt"].values - prod
    endo = [v for v in f.endo_names if v in fr.columns and v not in exog]

    def warm_from(sol):
        fr.loc[q, endo] = sol.loc[q, endo].values
    if warm is not None:
        warm_from(warm)
    info = {"k": k, "import_share_cum": achieved, "type_shares": shares, "ratio_after_2026": ratio_last}
    t0 = time.time()
    cf = solve(f, end, fr, exp)
    if stock:
        fcut = stock_cut().loc[q]
        target_w = np.log(stock_base(cf, wa, q, stock_mode) * (1 - fcut.values))
        x = np.zeros(len(q)); hist = []
        nS = len(fit)
        col = STOCK_INSTRUMENT[stock_mode]
        step = _premium_step if stock_mode == "premium" else _earnings_step(f, exp, len(q), nS)
        for it in range(maxit):
            gap = target_w - np.log(cf.loc[q, "wpsn"].values)          # < 0: without-run stock wealth still too high
            err = float(np.max(np.abs(gap[:nS])))
            hist.append(round(err, 6))
            if err < tol:
                break
            x[:nS] = x[:nS] + step(gap[:nS])
            x[nS:] = x[nS - 1]
            fr.loc[q, col] = wa.loc[q, col].values + x
            if exp != "var":
                warm_from(cf)
            cf = solve(f, end, fr, exp)
        else:                                  # iteration limit reached: measure the last solve too
            gap = target_w - np.log(cf.loc[q, "wpsn"].values)
            err = float(np.max(np.abs(gap[:nS])))
            hist.append(round(err, 6))
        info["stock_iterations"] = hist
        info["stock_converged"] = bool(err < tol)   # the unrounded gap: one just under the tolerance rounds up to it
        if stock_mode != "premium":            # (the premium version writes exactly what it always wrote)
            info["stock_mode"] = stock_mode
            info["zdivgr_effect"] = [round(float(v), 5) for v in (wa.loc[q, "zdivgr"].values - cf.loc[q, "zdivgr"].values)[:nS]]
    info["secs"] = round(time.time() - t0, 1)
    return cf, wa, info


# ------------------------------------------------------------------ reporting
LEVELS = ["xgdp", "xgdpn", "xgdpt", "ecnia", "ebfi", "ebfio", "eh", "ex", "em", "emoo", "fpxr", "wpsn",
          "pcnia", "kbfi", "xb"]
RATES = ["rff", "rg10", "rg10p", "rme", "rbbb", "picx4", "picxfe", "lur", "xgap2", "reqp", "hmfpt"]


def shares(df):
    g = df["xgdpn"]
    return pd.DataFrame({
        "nx": 100 * (df["exn"] - df["emn"]) / g,
        "ca": 100 * df["fcbn"] / g,
        "res": 100 * df["ehn"] / g,
        "bfio": 100 * 0.01 * df["ebfio"] * df["pbfir"] * df["pxp"] / g,
        "dcinv": 100 * 0.01 * df["edc"] * df["pbfir"] * df["pxp"] / g,
        "dcimp": 100 * 0.01 * df["emdc"] * df["pmo"] / g,
        "pce": 100 * 0.01 * df["pcnia"] * df["ecnia"] / g,
        "govbal": 100 * df["gfsrpn"] / g,
    }, index=df.index)


def effects(cf, base, idx=SHOW):
    """with minus without = base minus cf."""
    A, B = cf.loc[idx], base.loc[idx]
    out = pd.DataFrame(index=idx)
    for v in LEVELS:
        out[v] = 100 * (B[v] / A[v] - 1)
    for v in RATES:
        out[v] = B[v] - A[v]
    sA, sB = shares(A), shares(B)
    for v in sA.columns:
        out[v] = sB[v] - sA[v]
    out["xgdp_bn"] = B["xgdp"] - A["xgdp"]                      # 2012$ bn, annual rate
    return out


def pack(e):
    return {c: [round(float(x), 5) for x in e[c].values] for c in e.columns}
