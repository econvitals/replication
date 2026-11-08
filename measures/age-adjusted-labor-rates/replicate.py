"""Age-Adjusted Labor Market Rates — rebuilds the eight "Actual vs. Age/Sex-Adjusted" charts on
econvitals.org/labor/demographicdetail/#levels.

    python replicate.py        # no key needed; writes output/<rate>_adjusted_<band>.csv

An older population participates and works less, so the headline participation rate falls
even when no group changes its behavior. Each month's change in the rate is split into a
behavior part (people in each of 30 age-by-sex cells changing what they do) and a composition
part (the mix of cells shifting); see common/labor.py for the formula. The adjusted rate
cumulates only the behavior part, and is pinned to equal the actual rate in the latest month:

    adjusted(t) = actual(latest) - [cumulative behavior(latest) - cumulative behavior(t)]

so the whole history moves slightly with each release. The age-band versions (16-24, 25-54,
55+) use only the cells in the band, so they adjust for the mix within the band.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.labor import chained_decomposition  # noqa: E402

BANDS = {"16plus": "all-ages", "16_24": "16-24", "25_54": "25-54", "55plus": "55plus"}

for band, label in BANDS.items():
    frame, _ = chained_decomposition(band)
    out = {}
    for rate in ("lfpr", "epop"):
        actual, cumw = frame[f"{rate}_actual"], frame[f"{rate}_cumw"]
        adjusted = actual.iloc[-1] - (cumw.iloc[-1] - cumw)
        out[rate] = pd.DataFrame({"actual": actual, "adjusted": adjusted})
    for rate, df in out.items():
        save(df, HERE, f"{rate}_adjusted_{label}")
    print(f"{label:>8}: participation {out['lfpr']['actual'].iloc[-1]:.2f}, "
          f"adjusted in {out['lfpr'].index[0]:%b %Y} {out['lfpr']['adjusted'].iloc[0]:.2f} "
          f"vs actual {out['lfpr']['actual'].iloc[0]:.2f}")
