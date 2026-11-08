"""Inflation Skewness Index — rebuilds the chart "CPI Inflation Skewness" on econvitals.org/inflation/#cpi.

    python replicate.py        # no key needed; writes output/inflation_skewness.csv

The same 177 CPI categories and weights as the dispersion index (common/inflation.py,
cpi_strata_panel). Each month:

    π_i    = 12-month inflation of category i (percent)
    mean   = Σ w_i π_i                       the spending-weighted average
    median = the π_i where the cumulative weight, sorted by π, first reaches one half
    skew   = mean − median                   positive: a few fast-rising items lift the average

Weights are rescaled each month over the categories that have a 12-month change; a month where
less than half the basket has one (October 2025, and the months before 1983) is blank.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import cpi_strata_panel  # noqa: E402


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    keep = ~np.isnan(values)
    v, w = values[keep], weights[keep]
    if w.sum() == 0:
        return np.nan
    order = np.argsort(v)
    cum = np.cumsum(w[order] / w.sum())
    return float(v[order][np.searchsorted(cum, 0.5)])


idx, weights = cpi_strata_panel()
grid = idx.asfreq("MS")
pi = 100 * (grid / grid.shift(12) - 1)                 # 12-month change by calendar month
w = pi.notna().mul(weights, axis=1)
coverage = w.sum(axis=1)
w = w.div(coverage.replace(0, np.nan), axis=0)
mean = (w * pi.fillna(0)).sum(axis=1)
median = pd.Series([weighted_median(pi.iloc[t].values, w.iloc[t].values) for t in range(len(pi))],
                   index=pi.index)
skew = (mean - median).mask(coverage < 0.5).dropna()

out = pd.DataFrame({"skew": skew, "mean": mean.reindex(skew.index), "median": median.reindex(skew.index)})
save(out, HERE, "inflation_skewness")
pct = (out["skew"] <= out["skew"].iloc[-1]).mean() * 100        # as the chart caption computes it
print(out.tail(4).round(3).to_string())
print(f"latest ({out.index[-1]:%b %Y}) is at the {pct:.0f}th percentile of history since {out.index[0]:%Y}")
