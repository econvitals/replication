"""Shared helpers for the wealth-MPC project: data loading, regressions, chart style."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

plt.rcParams.update({
    "font.family": "serif", "font.size": 10, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": "#262626", "axes.grid": True,
    "axes.grid.axis": "y", "grid.color": "#D9D9D9", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False,
})
C = dict(primary="#4472C4", secondary="#ED7D31", highlight="#C00000", gray="#8C8C8C",
         gold="#C99700", teal="#2C8C99", burgundy="#8E3B5E", purple="#7E5BA6",
         ink="#262626", muted="#808080")
SRC = "Source: Federal Reserve Board, Financial Accounts; Bureau of Economic Analysis; author’s calculations."
PANDEMIC = pd.period_range("2020Q1", "2021Q2", freq="Q")   # quarters dummied out of full-sample regressions


def load(out):
    d = pd.read_csv(Path(out) / "panel.csv", index_col=0)
    d.index = pd.PeriodIndex(d.index, freq="Q")
    d["sent"] = d["sent"].interpolate(limit_direction="both")
    return d


def add_basics(d):
    """Ratios and changes used across the scripts. Wealth is dated at the START of the quarter
    (end of the previous quarter)."""
    x = pd.DataFrame(index=d.index)
    y = d["dpi"]
    x["cy"] = d["pce"] / y                                # PCE as a share of disposable income
    x["oy"] = d["outlays"] / y
    for k in ["S", "H", "O", "HE", "O_he", "nw"]:
        x[f"{k}y"] = d[k].shift(1) / y                    # start-of-quarter wealth over income
    x["tr_share"] = d["transfers"] / y
    x["unrate"] = d["unrate"]
    x["rr"] = d["real_tb3m"]
    x["sent"] = d["sent"]
    x["willing"] = d["willing"]
    x["ygap"] = 100 * (np.log(d["r_dpi"]) - np.log(d["r_dpi"]).shift(1).rolling(8).mean())
    # changes, scaled by last quarter's income (real, per person)
    yl = d["r_dpi"].shift(1)
    x["dc"] = d["r_pce"].diff() / yl
    x["dc_nds"] = d["r_pce_nds"].diff() / yl
    x["dy"] = d["r_dpi"].diff() / yl
    x["dyx"] = d["r_ex_transfer_y"].diff() / yl
    x["dtr"] = d["r_transfers"].diff() / yl
    for k in ["S", "H", "O", "NW"]:
        x[f"g{k}"] = d[f"r_rg_{k}"] / yl                  # real holding gain during the quarter over income
    x["du"] = d["unrate"].diff()
    x["drr"] = d["real_tb3m"].diff()
    x["dsent"] = d["sent"].diff()
    for q in PANDEMIC:
        x[f"D{q}"] = (x.index == q).astype(float)
    return x


def ols(y, X, lags=8, const=True):
    if const:
        X = sm.add_constant(X, has_constant="add")
    return sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": True})


def lincom(m, names, weights=None):
    """Sum (or weighted sum) of coefficients with its HAC standard error."""
    w = np.zeros(len(m.params))
    for i, n in enumerate(names):
        w[list(m.params.index).index(n)] = 1.0 if weights is None else weights[i]
    est = float(w @ m.params.values)
    se = float(np.sqrt(w @ m.cov_params().values @ w))
    return est, se


def finish(fig, ax, title, units, path, source=SRC, note=None, width=58):
    """Title (wrapped to at most two lines, never clipped), a units line under it, note and source below."""
    import textwrap
    tl = textwrap.wrap(title, width)
    if len(tl) > 2:
        tl = textwrap.wrap(title, int(len(title) / 2) + 6)
    ul = textwrap.wrap(units, 98)
    ax.set_title("\n".join(tl), loc="left", pad=13 + 16 * len(ul))
    ax.text(0, 1.02, "\n".join(ul), transform=ax.transAxes, fontsize=9.5, color=C["muted"], va="bottom", linespacing=1.15)
    foot = [source] if note is None else textwrap.wrap(note, 125) + [source]
    fig.text(0.01, -0.02, "\n".join(foot), fontsize=7.5, color=C["muted"], va="top", ha="left", linespacing=1.3)
    fig.savefig(path)
    plt.close(fig)


def qdates(idx):
    return idx.to_timestamp(how="end")


# ---------------------------------------------------------------------------------------------
# The two workhorse specifications
# ---------------------------------------------------------------------------------------------
CTL = ["tr_share", "unrate", "rr", "ygap"]       # controls in the levels regression
WEALTH3 = ["Sy", "Hy", "Oy"]
DUMS = [f"D{q}" for q in PANDEMIC]


def levels_fit(x, a, b, wealth=WEALTH3, ctl=CTL, dep="cy", dols=0, lags=8):
    """PCE over income on start-of-quarter wealth over income, by type, plus controls.
    Coefficients on the wealth ratios are dollars of annual spending per dollar of wealth.
    dols > 0 adds that many leads and lags of the quarterly change in each wealth ratio."""
    cols = list(wealth) + list(ctl)
    X = x[cols].copy()
    if dols:
        for k in wealth:
            dk = x[k].diff()
            for j in range(-dols, dols + 1):
                X[f"d{k}_{j}"] = dk.shift(j)
    if str(b) >= "2020Q1":
        X[DUMS] = x[DUMS]
    m = ols(x[dep].loc[a:b], X.loc[a:b], lags=lags)
    return m


def dl_design(x, J=8, kinds=("gS", "gH", "gO"), split=(), ylags=4, extra=True, thresh=0.0):
    """Distributed lag: quarterly change in real PCE per person (over last quarter's income) on
    current and J lagged real holding gains by type (over the same income), income changes and
    changes in unemployment and the real interest rate. `split` lists gain types entered separately
    for gains above and below `thresh`."""
    X = pd.DataFrame(index=x.index)
    for k in kinds:
        for j in range(J + 1):
            if k in split:
                X[f"{k}p_{j}"] = (x[k] - thresh).clip(lower=0).shift(j)
                X[f"{k}n_{j}"] = (x[k] - thresh).clip(upper=0).shift(j)
            else:
                X[f"{k}_{j}"] = x[k].shift(j)
    for j in range(ylags + 1):
        X[f"dy_{j}"] = x["dy"].shift(j)
    if extra:
        for j in range(3):
            X[f"du_{j}"] = x["du"].shift(j)
            X[f"drr_{j}"] = x["drr"].shift(j)
    return X


def dl_fit(x, a, b, J=8, dep="dc", lags=4, **kw):
    X = dl_design(x, J=J, **kw)
    if str(b) >= "2020Q1":
        X[DUMS] = x[DUMS]
    return ols(x[dep].loc[a:b], X.loc[a:b], lags=lags)


def cum(m, k, h):
    """Cumulative response after h quarters: sum of the coefficients on lags 0..h of gain type k."""
    return lincom(m, [f"{k}_{j}" for j in range(h + 1)])
