"""Labor Market Tightness Measures — rebuilds the five-line chart on econvitals.org/labor/#jolts.

    python replicate.py        # needs FRED_API_KEY; writes output/labor_market_tightness.csv

Five BLS gauges of how tight the job market is, each put in standard-deviation units so they
can share one axis:

    standardized(t) = (x(t) - x(February 2020)) / standard deviation of x over 2001-2018

with signs arranged so that a positive number always means tighter.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred_many, save  # noqa: E402

# Six BLS series, read from FRED (which republishes them unchanged).
raw = fred_many([
    "LNS12300060",   # employment-population ratio, ages 25-54 (CPS, seasonally adjusted)
    "UNRATE",        # unemployment rate (CPS, LNS14000000)
    "UNEMPLOY",      # number unemployed, thousands (CPS, LNS13000000)
    "JTSJOL",        # job openings, thousands (JOLTS)
    "JTSQUL",        # quits, thousands (JOLTS)
    "PAYEMS",        # nonfarm payroll employment, thousands (CES0000000001)
], start="2000-01-01")

# Only months where all six exist. This drops October 2025, when the household survey was
# not collected because of the federal shutdown, and the newest month until JOLTS catches up.
raw = raw.dropna()

gauges = pd.DataFrame({
    "emp_prime": raw["LNS12300060"],                                     # higher = tighter
    "unemp": -raw["UNRATE"],                                             # sign flipped
    "openings_per_unemp": raw["JTSJOL"] / raw["UNEMPLOY"],
    "quits": 100 * raw["JTSQUL"] / raw["PAYEMS"],                        # quits rate
    "openings": 100 * raw["JTSJOL"] / (raw["JTSJOL"] + raw["PAYEMS"]),   # job openings rate
})

# The quits and openings rates are built from the levels, as BLS defines them, rather than read
# as the published rates, which BLS rounds to one decimal.

sd = gauges.loc["2001-01-01":"2018-12-01"].std()     # sample standard deviation (n - 1)
feb2020 = gauges.loc["2020-02-01"]
tightness = ((gauges - feb2020) / sd).loc["2001-01-01":]

save(tightness, HERE, "labor_market_tightness")
print(tightness.tail(4).round(3).to_string())
