"""Real Oil and Mining Investment — rebuilds the oil-and-mining capital spending chart on
econvitals.org/gdp/gdpdetail/ (and its companion, business investment excluding oil and mining).

    python replicate.py        # needs FRED_API_KEY and BEA_API_KEY
                               # writes output/oil_mining.csv and output/bfi_ex_oil_mining.csv

Chained-dollar series cannot be added, so the two BEA pieces of oil and mining investment are
combined with a Törnqvist quantity index: each quarter's growth is the average of the two pieces'
growth, weighted by their shares of nominal spending in that quarter and the one before.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import bea_wide, fred, save  # noqa: E402

START = "2005-01-01"

# Structures: mining exploration, shafts and wells (petroleum and natural gas, plus mining).
ns = fred("E318RC1Q027SBEA", START)          # nominal, $ billions
rs = fred("E318RX1Q020SBEA", START)          # real, chained 2017 $ billions
# Equipment: mining and oilfield machinery. Not on FRED; BEA's underlying-detail tables
# 5.5.5U (nominal) and 5.5.6U (real), published in $ millions.
ne = bea_wide("U50505", "Q", by="code", dataset="NIUnderlyingDetail")["C270RC"] / 1e3
re = bea_wide("U50506", "Q", by="code", dataset="NIUnderlyingDetail")["C270RX"] / 1e3
# All nonresidential (business) fixed investment, nominal and real, for the companion series.
nbfi, rbfi = fred("PNFI", START), fred("PNFIC1", START)

df = pd.concat({"ns": ns, "rs": rs, "ne": ne, "re": re, "nbfi": nbfi, "rbfi": rbfi},
               axis=1).dropna()
df = df[df.index >= START]


def tornqvist(nominal: pd.DataFrame, real: pd.DataFrame) -> pd.Series:
    """Quantity index (first quarter = 100) of the components in the columns of `real`;
    `nominal` has the same columns in current dollars."""
    share = nominal.div(nominal.sum(axis=1), axis=0)
    weight = 0.5 * (share + share.shift(1))               # average share, this and last quarter
    dln = (weight * np.log(real).diff()).sum(axis=1)      # weighted quantity growth (log points)
    return 100 * np.exp(dln.cumsum())


def to_2017_dollars(index: pd.Series, nominal: pd.Series) -> pd.Series:
    """Scale so the 2017 average equals 2017 nominal spending (BEA's reference year)."""
    ref = index.index.year == 2017
    return index * nominal[ref].mean() / index[ref].mean()


def growth(level: pd.Series) -> pd.DataFrame:
    """1-quarter change at an annual rate and 4-quarter change, percent."""
    return pd.DataFrame({"q1_ann": 100 * ((level / level.shift(1)) ** 4 - 1),
                         "q4_yoy": 100 * (level / level.shift(4) - 1)})


# 1. Oil and mining: the Törnqvist index of structures and equipment.
om_nominal = df["ns"] + df["ne"]
om_index = tornqvist(df[["ns", "ne"]].set_axis(["s", "e"], axis=1),
                     df[["rs", "re"]].set_axis(["s", "e"], axis=1))
oil_mining = to_2017_dollars(om_index, om_nominal)

# 2. Everything else in business investment: BFI's published real growth less the oil and
#    mining contribution, divided by the rest's share (the Törnqvist residual).
w_om = 0.5 * (om_nominal / df["nbfi"] + (om_nominal / df["nbfi"]).shift(1))
dln_ex = (np.log(df["rbfi"]).diff() - w_om * np.log(om_index).diff()) / (1 - w_om)
ex_level = to_2017_dollars(100 * np.exp(dln_ex.fillna(0).cumsum()), df["nbfi"] - om_nominal)

out_om = growth(oil_mining).assign(level=oil_mining)
out_ex = growth(ex_level).assign(level=ex_level)
save(out_om, HERE, "oil_mining")
save(out_ex, HERE, "bfi_ex_oil_mining")
print("Oil and mining (chained 2017 $bn, growth in percent):")
print(out_om.tail(4).round(2).to_string())
print("\nBusiness investment excluding oil and mining:")
print(out_ex.tail(4).round(2).to_string())
