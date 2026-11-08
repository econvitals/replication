"""Econvitals Employment Dispersion Index — rebuilds the chart on econvitals.org/labor/#employment.

    python replicate.py        # no key needed; writes output/employment_dispersion.csv

How uneven job growth is across industries: the employment-weighted standard deviation of
12-month employment growth across about 89 industries that together make up all nonfarm jobs
(the "Lilien" measure of sectoral shifts). For each month t:

    g_i   = ln E_i(t) - ln E_i(t-12)           12-month log growth of industry i
    w_i   = E_i(t-12) / sum_j E_j(t-12)        its share of jobs a year earlier
    gbar  = sum_i w_i g_i
    sigma = 100 * sqrt( sum_i w_i (g_i - gbar)^2 )      in percentage points

The industries are BLS's not-seasonally-adjusted payroll employment (CES) cells:
  * every private 3-digit NAICS industry BLS publishes (73 of them);
  * for each of the 10 private supersectors, an "everything else" cell: the supersector total
    minus its published 3-digit industries, kept only where that remainder is real (BLS levels
    are in thousands to one decimal, so a remainder under 0.05 is zero, not a tiny industry);
  * six government cells: federal (except Postal Service), Postal Service, and state and local
    government, each split into education and everything else.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bls_flat, bls_series, save  # noqa: E402

START = "1990-01-01"        # BLS's 3-digit history is complete from 1990
PRIVATE_SUPERSECTORS = ["10", "20", "30", "40", "50", "55", "60", "65", "70", "80"]
GOVERNMENT = ["90911000", "90919120", "90921611", "90922000", "90931611", "90932000"]

# BLS's bulk "Employment" files, one per supersector (a manufacturing or trade industry sits in
# its sector's file: 31/32 for durable/nondurable goods, 41-43 for wholesale, retail,
# transportation and utilities). About 77 MB in all; no key and no daily quota.
FILES = ["10a.MiningAndLogging", "20a.Construction", "30a.Manufacturing",
         "31a.ManufacturingDurableGoods", "32a.ManufacturingNondurableGoods",
         "40a.TradeTransportationAndUtilities", "41a.WholesaleTrade", "42a.RetailTrade",
         "43a.TransportationAndWarehousingAndUtilities", "50a.Information",
         "55a.FinancialActivities", "60a.ProfessionalBusinessServices",
         "65a.EducationAndHealthCare", "70a.LeisureAndHospitality", "80a.OtherServices",
         "90a.Government"]


def supersector(industry_code: str) -> str:
    """The private supersector a 3-digit industry rolls up to."""
    prefix = industry_code[:2]
    return {"31": "30", "32": "30", "41": "40", "42": "40", "43": "40", "44": "40"}.get(prefix, prefix)


# 1. Which cells. BLS's industry list marks 3-digit NAICS industries by their NAICS code.
industries = bls_flat("ce", "ce.industry")
three_digit = industries.loc[industries["naics_code"].str.len() == 3, "industry_code"].tolist()
totals = [ss + "000000" for ss in PRIVATE_SUPERSECTORS]
wanted = three_digit + totals + GOVERNMENT

# 2. Employment levels, thousands, not seasonally adjusted: series CEU<industry code>01.
series_id = {code: f"CEU{code}01" for code in wanted}
levels = pd.concat([bls_series("ce", f"ce.data.{f}.Employment", series_id.values()) for f in FILES],
                   axis=1)
levels = levels.T.groupby(level=0).first().T          # a series can sit in two files; keep one
levels = levels.loc[START:].rename(columns={v: k for k, v in series_id.items()})

# 3. The panel of cells.
cells = {code: levels[code] for code in three_digit if code in levels}
for ss in PRIVATE_SUPERSECTORS:
    children = [c for c in cells if supersector(c) == ss]
    remainder = levels[ss + "000000"].sub(levels[children].sum(axis=1, min_count=1), fill_value=0)
    remainder = remainder.dropna()
    remainder = remainder[remainder >= 0.05]
    if len(remainder):
        cells[ss + "-other"] = remainder
for code in GOVERNMENT:
    cells[code] = levels[code]
E = pd.DataFrame(cells).sort_index()

# 4. The dispersion.
E_year_ago = E.shift(12)
g = np.log(E) - np.log(E_year_ago)
w = E_year_ago.div(E_year_ago.sum(axis=1), axis=0)
gbar = (w * g).sum(axis=1)
sigma = 100 * np.sqrt((w * g.sub(gbar, axis=0) ** 2).sum(axis=1))
sigma = sigma.loc[E.index[12]:].dropna().rename("sigma")

save(sigma, HERE, "employment_dispersion")
print(f"{E.shape[1]} industry cells")
print(sigma.tail(4).round(4).to_frame().to_string())
