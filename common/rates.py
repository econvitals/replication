"""Readers for the interest-rate, central-bank and prediction-market measures. Keyless except where
FRED is used (through `econdata.fred`); every download goes through `econdata.get`, so it is cached
and identifies itself.

    published_anywhere(path)       a published Econvitals file, wherever the site serves it from
    bis_policy_rate("GB")          one central bank's daily policy rate from the BIS
    gsw_parameters()               the Federal Reserve Board's daily Svensson yield-curve parameters
    svensson(params, years)        a zero-coupon yield from those parameters
    kalshi(path)                   one call to Kalshi's public market-data API (no account needed)
    ny_fed_rstar("LW")             the New York Fed's one-sided r* estimates, quarterly
"""
from __future__ import annotations

import io
import json
import math

import numpy as np
import pandas as pd

from common import econdata

SITE = "https://econvitals.org/"


# ------------------------------------------------------------------------------ Econvitals
def published_anywhere(path: str) -> dict:
    """A published Econvitals file. Chart data lives in the public data repository (what
    `econdata.published` reads); a few tools keep their data on econvitals.org itself, under the
    same path, so when the data repository does not have the file it is read from the site."""
    try:
        return econdata.published(path)
    except Exception:  # noqa: BLE001 — not in the data repository: the site serves it
        return json.loads(econdata.get(SITE + path, timeout=120))


# ------------------------------------------------------------------------------ BIS
BIS_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{area}"


def bis_policy_rate(area: str, start: str = "2015-01-01") -> pd.Series:
    """Daily central-bank policy rate (percent, end of day) from the BIS "Central bank policy
    rates" dataset. `area` is the BIS code: US, XM (euro area), JP, GB, CA, AU, CH, SE, NO, NZ,
    CN, IN, ..."""
    text = econdata.get(BIS_URL.format(area=area), {"startPeriod": start, "format": "csv"},
                        timeout=120)
    df = pd.read_csv(io.StringIO(text), usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values,
                  index=pd.to_datetime(df["TIME_PERIOD"]), name=area)
    return s.dropna().sort_index()


# ------------------------------------------------------------------------------ yield curves
GSW_URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"


def gsw_parameters() -> pd.DataFrame:
    """The Federal Reserve Board's U.S. Treasury yield curve (Gürkaynak, Sack and Wright), as the
    six daily Svensson parameters BETA0-BETA3, TAU1, TAU2 (1961 on). The file has a few lines of
    notes above the header."""
    text = econdata.get(GSW_URL, timeout=300)
    lines = text.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Date,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[head:])), index_col="Date", parse_dates=True)
    cols = ["BETA0", "BETA1", "BETA2", "BETA3", "TAU1", "TAU2"]
    df = df[cols].apply(pd.to_numeric, errors="coerce")
    # Before 1980 the curve is Nelson-Siegel: BETA3 and TAU2 are missing (or -999.99) and drop out.
    df.loc[(df["TAU2"] <= 0) | df["TAU2"].isna(), ["BETA3", "TAU2"]] = [0.0, 1.0]
    return df.dropna().sort_index()


def svensson(p, years):
    """Zero-coupon yield (percent, continuously compounded) at maturity `years` from Svensson
    parameters p = (BETA0, BETA1, BETA2, BETA3, TAU1, TAU2). Vectorized over rows of `p`."""
    b0, b1, b2, b3, t1, t2 = (np.asarray(p, dtype=float)[..., i] for i in range(6))
    n = np.asarray(years, dtype=float)
    x1, x2 = n / t1, n / t2
    f1 = (1 - np.exp(-x1)) / x1
    f2 = (1 - np.exp(-x2)) / x2
    return b0 + b1 * f1 + b2 * (f1 - np.exp(-x1)) + b3 * (f2 - np.exp(-x2))


# ------------------------------------------------------------------------------ Kalshi
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"


def kalshi(path: str, params: dict | None = None) -> dict:
    """One read from Kalshi's public market-data API (markets, events, daily candles). No key and
    no account; read-only. Results are cached like every other download, so a rerun inside the
    cache window sees the same prices."""
    return json.loads(econdata.get(f"{KALSHI}/{path.lstrip('/')}", params))


# ------------------------------------------------------------------------------ New York Fed
RSTAR_URL = ("https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/rstar/"
             "r-star-data-{model}.txt")


def ny_fed_rstar(model: str = "LW") -> pd.Series:
    """The New York Fed's current one-sided estimate of the natural rate of interest (r*),
    quarterly, percent: model "LW" (Laubach-Williams) or "HLW" (Holston-Laubach-Williams, United
    States). The files behind the New York Fed's r* charts hold each series as [time in
    milliseconds, value] pairs; quarters are dated to their first day."""
    want = {"LW": "R Star one side", "HLW": "R Star US"}[model]
    blocks = json.loads(econdata.get(RSTAR_URL.format(model=model), timeout=120))
    pairs = next(b[want] for b in blocks if want in b)
    out = {pd.Timestamp(ms, unit="ms").to_period("Q").start_time: float(v)
           for ms, v in pairs if v is not None and math.isfinite(float(v))}
    return pd.Series(out, name=f"rstar_{model.lower()}").sort_index()
