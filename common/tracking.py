"""Helpers shared by the inflation tracking estimates (PCE, CPI and the release-day estimate).

Three things live here because more than one folder needs them:

* `bls_levels(ids)` reads BLS price indexes (CPI, PPI, import prices) from BLS's public bulk
  files, so no BLS API key or daily quota is involved. It downloads only the few topic files
  that hold the series asked for (a few megabytes each) and caches them like everything else.
* `seasonal_adjust()` adjusts an index that BLS publishes only unadjusted, as BEA and the
  Cleveland Fed do before using it.
* `mom()` is the one-month percent change, left blank across a gap (BLS skips a month when an
  item's sample is too thin, and it published no October 2025 CPI at all).
* `first_print()` reads ALFRED, the St. Louis Fed's archive of every vintage of a FRED series,
  to get the value an agency FIRST published for a month, which is what a forecast is scored
  against. The track-record scripts (history.py) also use it as evidence that a month has been
  released: a month ALFRED does not have has not been published.

Monthly results are pandas Series on a monthly PeriodIndex (`pd.Period("2026-09", "M")`).
"""
from __future__ import annotations

import json
import os
import warnings

import numpy as np
import pandas as pd

from common.econdata import bls_flat, get, key

# The BLS bulk files (download.bls.gov/pub/time.series/<survey>/) that hold the series the
# tracking estimates use, by survey. CPI: the U.S. city average topic files. PPI: the industry
# files for the services BEA prices with producer prices, plus two commodity files.
BLS_FILES = {
    "cu": ["cu.data.1.AllItems", "cu.data.2.Summaries", "cu.data.11.USFoodBeverage",
           "cu.data.12.USHousing", "cu.data.13.USApparel", "cu.data.14.USTransportation",
           "cu.data.15.USMedical", "cu.data.16.USRecreation",
           "cu.data.17.USEducationAndCommunication", "cu.data.18.USOtherGoodsAndServices",
           "cu.data.20.USCommoditiesServicesSpecial"],
    "pc": ["pc.data.8.Apparel", "pc.data.36.AirTransportation",
           "pc.data.47.AmbulatoryHealthCareServices", "pc.data.50.Hospitals",
           "pc.data.51.NursingResidentialCareFacil", "pc.data.57.Finance",
           "pc.data.58.InsuranceCarriers", "pc.data.63.ProfessionalandTechnicalServ",
           "pc.data.67.AdministrativeandSupportServ", "pc.data.71.Accommodation"],
    "wp": ["wp.data.4.Textile", "wp.data.30.Services"],
    "ei": ["ei.data.10.ServicesImport"],
}
PREFIX_SURVEY = {"CU": "cu", "PC": "pc", "WP": "wp", "EI": "ei"}


def bls_levels(ids) -> dict[str, pd.Series]:
    """{series_id: monthly index levels} for every requested series found in the bulk files."""
    want = set(ids)
    out: dict[str, pd.Series] = {}
    for survey in sorted({PREFIX_SURVEY[i[:2]] for i in want}):
        for fn in BLS_FILES[survey]:
            todo = want - set(out)
            if not todo:
                break
            df = bls_flat(survey, fn)
            df = df[df["series_id"].isin(todo) & df["period"].str.match(r"M(0[1-9]|1[0-2])$")]
            if df.empty:
                continue
            df = df.assign(month=pd.PeriodIndex(df["year"] + "-" + df["period"].str[1:], freq="M"),
                           value=pd.to_numeric(df["value"], errors="coerce")).dropna(subset=["value"])
            for sid, g in df.groupby("series_id"):
                out[sid] = g.set_index("month")["value"].sort_index()
    return out


def mom(level: pd.Series) -> pd.Series:
    """Percent change on the month; blank where either month is missing."""
    s = level.dropna()
    if s.empty:
        return s
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    return (full / full.shift(1) - 1) * 100


def seasonal_adjust(level: pd.Series, start: str = "2008-01", x13: bool = False) -> pd.Series:
    """Seasonally adjust an unadjusted monthly index, on the series from `start`.

    With x13=True and the Census Bureau's X-13ARIMA-SEATS installed (free from census.gov; set
    X13PATH to the folder holding the x13as program), X-13 is run with its automatic model
    choice and outlier detection, which is what BEA and the Cleveland Fed do. Otherwise, a
    simple stand-in: month-of-year means of the log level less a centered 13-month moving
    average, recent years weighted more (half-life five years), outliers clipped at 2.5
    robust standard deviations."""
    s = level.loc[start:].dropna()
    if x13 and os.environ.get("X13PATH"):
        try:
            from statsmodels.tsa.x13 import x13_arima_analysis
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = x13_arima_analysis(s, x12path=os.environ["X13PATH"], prefer_x13=True,
                                         log=None, outlier=True, print_stdout=False)
            return res.seasadj
        except Exception as exc:  # noqa: BLE001 - X-13 refuses a few short or odd series
            print(f"  X-13 could not adjust a series ({type(exc).__name__}); using the stand-in")
    if len(s) < 48:
        return s
    logs = np.log(s)
    si = (logs - logs.rolling(13, center=True).mean()).dropna()
    factor = {}
    for m in range(1, 13):
        x = si[si.index.month == m]
        if len(x) < 3:
            factor[m] = 0.0
            continue
        med = x.median()
        mad = (x - med).abs().median() * 1.4826 or 1e-9
        w = 0.5 ** ((x.index.year.max() - np.asarray(x.index.year)) / 5.0)
        factor[m] = float((x.clip(med - 2.5 * mad, med + 2.5 * mad).values * w).sum() / w.sum())
    avg = np.mean(list(factor.values()))
    f = pd.Series([factor[p.month] - avg for p in s.index], index=s.index)
    return np.exp(np.log(s) - f)


# ------------------------------------------------------------------------------ ALFRED
_FRED_OBS = "https://api.stlouisfed.org/fred/series/observations"


def _alfred(series_id: str, **params) -> list[dict]:
    p = {"series_id": series_id, "api_key": key("FRED_API_KEY"), "file_type": "json", **params}
    raw = json.loads(get(_FRED_OBS, p))
    if "observations" not in raw:
        raise RuntimeError(f"ALFRED {series_id}: {raw.get('error_message', raw)}")
    return raw["observations"]


def first_release_dates(series_id: str, start: str = "2015-01-01") -> dict[pd.Period, str]:
    """{month: the date its value was first published} for every month FRED has released."""
    obs = _alfred(series_id, observation_start=start, output_type=4,
                  realtime_start="1776-07-04", realtime_end="9999-12-31")
    return {pd.Period(o["date"][:7], freq="M"): o["realtime_start"]
            for o in obs if o["value"] not in (".", "")}


def first_print(series_id: str, month: pd.Period, released_on: str, kind: str = "index",
                lag: int = 1) -> float:
    """The month's percent change as first published, read from the vintage of the day the
    month first came out.

    kind="index": FRED carries an index; the change is over `lag` months (1 or 12), with both
    levels from that day's vintage (so a revision of the earlier month that landed the same day
    counts, as the agency's own release counts it). kind="rate": FRED carries the one-month
    change itself. kind="annualized": FRED carries a one-month change at an annual rate (the
    Dallas Fed's convention); it is converted back to a plain one-month change."""
    obs = _alfred(series_id, observation_start=str((month - lag).start_time.date()),
                  observation_end=str(month.start_time.date()),
                  realtime_start=released_on, realtime_end=released_on)
    lv = {pd.Period(o["date"][:7], freq="M"): float(o["value"]) for o in obs
          if o["value"] not in (".", "")}
    if month not in lv:
        return float("nan")
    if kind == "rate":
        return lv[month]
    if kind == "annualized":
        return ((1 + lv[month] / 100) ** (1 / 12) - 1) * 100
    if month - lag not in lv:
        return float("nan")
    return (lv[month] / lv[month - lag] - 1) * 100


def weighted_median(x: np.ndarray, w: np.ndarray) -> float:
    """The value at the 50th percentile of the weight distribution (components sorted by x)."""
    o = np.argsort(x, kind="mergesort")
    cum = np.cumsum(w[o] / w.sum())
    return float(x[o][min(int(np.searchsorted(cum, 0.5)), len(x) - 1)])


def trimmed_mean(x: np.ndarray, w: np.ndarray, low: float, high: float) -> float:
    """Weighted mean after trimming `low` of the weight from the bottom and `high` from the top,
    splitting the component that straddles each cut (the Dallas and Cleveland Feds' rule)."""
    o = np.argsort(x, kind="mergesort")
    xs, ws = x[o], w[o] / w.sum()
    cum = np.cumsum(ws)
    prev = np.concatenate([[0.0], cum[:-1]])
    kept = np.maximum(0.0, np.minimum(cum, 1 - high) - np.maximum(prev, low))
    return float((xs * kept).sum() / kept.sum())
