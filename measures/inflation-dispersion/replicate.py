"""Inflation Dispersion Index — rebuilds the chart "Standard Deviation of Inflation Across Categories"
on econvitals.org/inflation/#cpi.

    python replicate.py        # no key needed; writes output/inflation_dispersion.csv

How spread out price changes are across the CPI basket. For 177 detailed CPI categories
(common/inflation.py, cpi_strata_panel: the lowest-level items in BLS's December 2023
relative-importance table, weighted by that table, CPI-U, not seasonally adjusted):

    π_i   = 12-month inflation of category i (percent)
    π̄     = Σ w_i π_i                       the spending-weighted mean
    sigma = √( Σ w_i (π_i − π̄)² )           the weighted standard deviation (percentage points)

Each month the weights are rescaled over the categories that have a 12-month change, so a
category that starts late does not tilt the result; a month where less than half the basket has
one (including October 2025, when BLS collected no prices, and the months before 1983) is blank.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.inflation import cpi_strata_panel  # noqa: E402

idx, weights = cpi_strata_panel()
grid = idx.asfreq("MS")
pi = 100 * (grid / grid.shift(12) - 1)                 # 12-month change by calendar month
w = pi.notna().mul(weights, axis=1)                    # weight only where a change exists
coverage = w.sum(axis=1)                               # share of the basket covered this month
w = w.div(coverage.replace(0, np.nan), axis=0)         # rescale to sum to 1
mean = (w * pi.fillna(0)).sum(axis=1)
sigma = np.sqrt((w * pi.sub(mean, axis=0).pow(2).fillna(0)).sum(axis=1))
sigma = sigma.mask(coverage < 0.5).dropna()

out = sigma.to_frame("sigma")
out["mean"] = mean.reindex(out.index)                  # the weighted mean, for reference (≈ CPI inflation)
save(out, HERE, "inflation_dispersion")
pct = (out["sigma"] <= out["sigma"].iloc[-1]).mean() * 100      # as the chart caption computes it
print(out.tail(4).round(3).to_string())
print(f"latest ({out.index[-1]:%b %Y}) is at the {pct:.0f}th percentile of history since {out.index[0]:%Y}")
