"""Shared pieces for the inflation measures.

Used by the folders under measures/ for the Ecumenical underlying inflation, the PCE-equivalent
tables, core PCE ex housing and used vehicles, core services CPI ex shelter, and the CPI
dispersion and skewness indexes. Everything here starts from public files:

    BEA     NIPA table 2.8.4 (T20804) and underlying-detail tables 2.4.4U / 2.4.5U (U20404 / U20405)
    BLS     CPI bulk files at download.bls.gov/pub/time.series/cu/ (indexes, relative importance)
            and the December 2023 relative-importance table on bls.gov
    Fed     Cleveland Fed median CPI and median PCE; Dallas Fed trimmed-mean PCE; Cleveland Fed
            trimmed-mean CPI (the two Cleveland CPI series through FRED)

Index series are pandas Series on a monthly DatetimeIndex (first of the month).
"""
from __future__ import annotations

import io
import time
from functools import lru_cache, reduce

import numpy as np
import openpyxl
import pandas as pd

from common.econdata import ROOT, bea_nipa, bea_wide, bls_flat, bls_series, fred, get

MEASURES = ROOT / "measures"

# BLS collected no CPI for October 2025 (the federal shutdown), so every CPI index has a hole there.
HOLE = pd.Timestamp("2025-10-01")


# ------------------------------------------------------------------------------ arithmetic
def annualized(index: pd.Series, months: int) -> pd.Series:
    """The `months`-month change of an index at an annual rate, in percent.

    Compares calendar months (a missing month is a blank, never a longer change). One exception,
    Econvitals' rule for the CPI's missing October 2025: a 12-month change whose base is that month
    uses the geometric average of September and November 2025 as the base. Shorter changes that
    start in October 2025 stay blank.
    """
    s = index.dropna().asfreq("MS")
    base = s.shift(months)
    year_on = HOLE + pd.DateOffset(months=12)
    if months == 12 and HOLE in s.index and pd.isna(s[HOLE]) and year_on in base.index:
        sep, nov = s.get(HOLE - pd.DateOffset(months=1)), s.get(HOLE + pd.DateOffset(months=1))
        if pd.notna(sep) and pd.notna(nov):
            base[year_on] = np.sqrt(sep * nov)
    return 100 * ((s / base) ** (12 / months) - 1)


def chain(changes: pd.Series, *, annualized_rates: bool = False,
          seed_prior_month: bool = False) -> pd.Series:
    """Turn a series of 1-month changes into an index (base 100).

    annualized_rates: the changes are 1-month rates at an annual rate (the Dallas Fed's
        convention), so each month's factor is (1 + v/100)^(1/12); otherwise they are plain
        1-month percent changes (the Cleveland Fed's convention), factor 1 + v/100.
    seed_prior_month: put 100 in the month before the first change and apply that change (used
        for the Dallas series, which starts in February 1977); otherwise 100 sits at the first
        month and its own change is not applied.
    """
    s = changes.dropna().sort_index()
    factor = (1 + s / 100) ** (1 / 12) if annualized_rates else 1 + s / 100
    if seed_prior_month:
        start = pd.Series([100.0], index=[s.index[0] - pd.DateOffset(months=1)])
        return pd.concat([start, 100 * factor.cumprod()])
    factor.iloc[0] = 1.0
    return 100 * factor.cumprod()


def average_rate(index: pd.Series, start: str, end: str) -> float | None:
    """Average annual inflation of an index between two months (compound rate, percent)."""
    a, b = pd.Timestamp(start), pd.Timestamp(end)
    if a not in index.index or b not in index.index:
        return None
    n = (b.year - a.year) * 12 + (b.month - a.month)
    return 100 * ((index[b] / index[a]) ** (12 / n) - 1)


def pce_equivalent_adjustment(measure: pd.Series, overall_pce: pd.Series, windows):
    """(adjustment, window): the fixed number of percentage points that, added to the measure,
    makes its average inflation over the window equal overall PCE inflation's. Tries each
    (start, end) window in order and uses the first one the measure fully covers."""
    for start, end in windows:
        pce, own = average_rate(overall_pce, start, end), average_rate(measure, start, end)
        if pce is not None and own is not None:
            return pce - own, (start, end)
    return None, None


def table_month(measures: dict, optional=()) -> pd.Timestamp:
    """The newest month every measure has (measures named in `optional` do not hold it back)."""
    sets = [set(s.dropna().index) for name, s in measures.items() if name not in optional]
    return max(reduce(set.intersection, sets))


# ------------------------------------------------------------------------------ BLS CPI files
# The BLS bulk files that hold full histories: the special aggregates, then the item groups.
CPI_FILES = ["cu.data.20.USCommoditiesServicesSpecial", "cu.data.12.USHousing",
             "cu.data.11.USFoodBeverage", "cu.data.13.USApparel", "cu.data.14.USTransportation",
             "cu.data.15.USMedical", "cu.data.16.USRecreation",
             "cu.data.17.USEducationAndCommunication", "cu.data.18.USOtherGoodsAndServices"]


def cpi_indexes(series_ids) -> pd.DataFrame:
    """Monthly CPI indexes for BLS series ids (one column each), full history, from the bulk files."""
    want, parts = set(series_ids), []
    for f in CPI_FILES:
        if not want:
            break
        got = bls_series("cu", f, want)
        parts.append(got)
        want -= set(got.columns)
    if want:
        raise RuntimeError(f"not found in the BLS CPI files: {sorted(want)}")
    return pd.concat(parts, axis=1)[list(series_ids)]


def cpi_relative_importance(series_ids) -> pd.DataFrame:
    """BLS's monthly relative-importance weights (the "I" aspect, March 2012 on), one column each.
    BLS publishes them on the not-seasonally-adjusted (CUUR...) series ids."""
    a = bls_flat("cu", "cu.aspect")
    a = a[(a["aspect_type"] == "I") & a["series_id"].isin(set(series_ids))
          & a["period"].str.match(r"M(0[1-9]|1[0-2])")]
    a = a.assign(date=pd.to_datetime(a["year"] + "-" + a["period"].str[1:] + "-01"),
                 value=pd.to_numeric(a["value"], errors="coerce"))
    return a.pivot_table(index="date", columns="series_id", values="value", aggfunc="first")


def core_services_cpi_ex_shelter() -> pd.Series:
    """Core services CPI ex shelter: BLS core services (services less energy services) with the
    whole shelter index taken out, month by month, using BLS's relative-importance weights.

    Each month, with B = core services, C = shelter, and H, I their weights in the previous month:
        growth_t = [H * (B_t/B_t-1 - 1) - I * (C_t/C_t-1 - 1)] / (H - I)
    A month BLS published no weight for (October and November 2025) uses the last weight it did.
    The weights start in March 2012; the series before that is Econvitals' recorded history,
    shipped in measures/core-services-cpi-ex-shelter/inputs/, and the rebuilt part is joined to
    its March 2012 level.
    """
    idx = cpi_indexes(["CUSR0000SASLE", "CUSR0000SAH1"]).dropna()
    idx = idx[idx.index >= "2012-03-01"]
    w = cpi_relative_importance(["CUUR0000SASLE", "CUUR0000SAH1"]).reindex(idx.index).ffill()
    B, C = idx["CUSR0000SASLE"], idx["CUSR0000SAH1"]
    H, I = w["CUUR0000SASLE"].shift(), w["CUUR0000SAH1"].shift()  # previous published month's weights
    growth = (H * (B / B.shift() - 1) - I * (C / C.shift() - 1)) / (H - I)
    rebuilt = 100 * (1 + growth.fillna(0)).cumprod()
    hist = pd.read_csv(MEASURES / "core-services-cpi-ex-shelter/inputs/cses_index_1990_2012.csv",
                       comment="#", index_col="date", parse_dates=True)["index"]
    splice = pd.Timestamp("2012-03-01")
    rebuilt = rebuilt * hist[splice] / rebuilt[splice]
    return pd.concat([hist[hist.index <= splice], rebuilt[rebuilt.index > splice]])


@lru_cache(maxsize=1)
def cpi_strata_panel():
    """(indexes, weights) for the 177 detailed CPI categories behind the dispersion indexes.

    The categories are the lowest-level items (codes starting SE or SS) in BLS's December 2023
    relative-importance table; their weights are that table's CPI-U values, scaled to sum to 1.
    Indexes are CPI-U, U.S. city average, not seasonally adjusted (CUUR0000<item>), from 1960.
    """
    raw = get("https://www.bls.gov/cpi/tables/relative-importance/2023.xlsx", binary=True)
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)["Table 1"]
    table = []                                     # (indent level, item name, CPI-U weight)
    for r in ws.iter_rows(values_only=True):
        try:
            table.append((int(r[0]), str(r[1]).strip(), float(r[2])))
        except (TypeError, ValueError):
            continue
    items = bls_flat("cu", "cu.item")
    code_of = {n.strip().lower(): c for n, c in zip(items["item_name"], items["item_code"])}
    leaves = {}
    for i, (level, name, weight) in enumerate(table):
        next_level = table[i + 1][0] if i + 1 < len(table) else 0
        code = code_of.get(name.lower())
        if level >= 2 and next_level <= level and code and code[:2] in ("SE", "SS"):
            leaves[code] = weight                  # a leaf of the table's indentation tree
    idx = cpi_indexes(["CUUR0000" + c for c in leaves])
    idx.columns = [c[8:] for c in idx.columns]
    idx = idx[idx.index >= "1960-01-01"]
    w = pd.Series(leaves)
    return idx, (w / w.sum()).reindex(idx.columns)


# ------------------------------------------------------------------------------ BEA PCE detail
_last_download = 0.0


@lru_cache(maxsize=None)
def pce_detail_table(table: str) -> pd.DataFrame:
    """One BEA underlying-detail table (U20404 prices or U20405 spending), monthly, long form.

    Each is about 75 MB. BEA's API allows 100 MB a minute and shuts a key out for an hour beyond
    that, so a second download starts at least a minute after the first one finished.
    """
    global _last_download
    time.sleep(max(0.0, _last_download + 65 - time.time()))
    started = time.time()
    df = bea_nipa(table, "M", dataset="NIUnderlyingDetail")
    if time.time() - started > 10:                 # it came over the network, not from the cache
        _last_download = time.time()
    return df


def pce_detail(by: str = "line"):
    """(prices, spending): BEA tables 2.4.4U (chain price indexes) and 2.4.5U (nominal spending)
    by product, one column per line number (by="line") or BEA series code (by="code")."""
    return tuple(pce_detail_table(t).pivot_table(index="date", columns=by, values="value",
                                                 aggfunc="first") for t in ("U20404", "U20405"))


@lru_cache(maxsize=1)
def pce_headline_indexes() -> pd.DataFrame:
    """BEA table 2.8.4 (monthly PCE price indexes), one column per BEA series code."""
    return bea_wide("T20804", "M", by="code")


def core_pce_ex_housing_used_vehicles() -> pd.Series:
    """Core PCE ex housing and used vehicles: used motor vehicles removed from BEA's core PCE ex
    housing price index with a Törnqvist chain.

    s_t = used-vehicle spending / (core spending - housing spending), and with s̄ = (s_t-1 + s_t)/2
        Δln(index_t) = [Δln(core ex housing_t) - s̄ * Δln(used vehicles_t)] / (1 - s̄)
    Only the changes matter; the level starts at core ex housing's first value.
    """
    exhou = pce_headline_indexes()["IA001176"]           # PCE excluding food, energy, and housing
    prices, spend = pce_detail(by="code")
    used_price = prices["DNPVRG"]                        # net purchases of used motor vehicles
    used_spend = spend["DNPURC"] + spend["DUTRRC"]       # used autos + used light trucks
    share = used_spend / (spend["DPCCRC"] - spend["DHSGRC"])  # core PCE spending less housing
    d = pd.concat({"exhou": exhou, "used": used_price, "s": share}, axis=1).dropna()
    s_bar = (d["s"] + d["s"].shift()) / 2
    dlog = (np.log(d["exhou"] / d["exhou"].shift()) - s_bar * np.log(d["used"] / d["used"].shift())) / (1 - s_bar)
    index = d["exhou"].iloc[0] * np.exp(dlog.fillna(0).cumsum())
    # Econvitals stores this index to six decimals; rounding the same way makes the 1959-61
    # changes (when the index is near 16) agree to the published fourth decimal.
    return index.round(6)


# ------------------------------------------------------------------------------ median and trimmed mean PCE
ALPHA, BETA = 0.24, 0.31     # the Dallas Fed's trim: drop the lowest 24% and highest 31% of weight


@lru_cache(maxsize=1)
def pce_release_day_estimates():
    """(trimmed mean, median): Econvitals' own versions from BEA's 177-component detail, for the
    months the Fed banks have not posted yet (they post about a business day after BEA).

    Each month: every component's 1-month price change, Fisher expenditure weights
    (half Q_t·P_t-1 and half Q_t-1·P_t-1, each as a share), sorted by price change.
      trimmed mean = weighted mean of the middle 45% of weight (boundary components count for the
                     part of their weight inside the window), at an annual rate, as Dallas does;
      median       = the change of the component where cumulative weight first reaches 50%,
                     a plain 1-month percent change, as Cleveland reports it.
    Both rounded to four decimals, as Econvitals stores them.
    """
    comp = pd.read_csv(MEASURES / "ecumenical-underlying-inflation/inputs/pce_trimmed_mean_components.csv")
    lines = comp["line_no"].astype(int).tolist()
    prices, spend = pce_detail()
    P = prices[lines].loc["2015-01-01":]
    Q = spend[lines].loc["2015-01-01":] / P             # real quantities
    trim, med = {}, {}
    P0, Q0 = P.shift(), Q.shift()                      # last month's prices and quantities
    for t in P.index[1:]:
        p0, p1, q0, q1 = P0.loc[t], P.loc[t], Q0.loc[t], Q.loc[t]
        if pd.concat([p0, p1, q0, q1]).isna().any():
            continue                                    # only months with all 177 components
        change = (p1 / p0 - 1).values
        w = 0.5 * (q1 * p0) / (q1 * p0).sum() + 0.5 * (q0 * p0) / (q0 * p0).sum()
        w = (w / w.sum()).values
        order = np.argsort(change, kind="stable")
        change, w = change[order], w[order]
        cum = np.cumsum(w)
        before = np.concatenate([[0.0], cum[:-1]])     # cumulative weight below each component
        inside = np.maximum(0, np.minimum(cum, 1 - BETA) - np.maximum(before, ALPHA))
        m = float(np.sum(change * inside) / inside.sum())
        trim[t] = round(((1 + m) ** 12 - 1) * 100, 4)
        med[t] = round(float(change[min(np.searchsorted(cum, 0.5), len(change) - 1)]) * 100, 4)
    return pd.Series(trim), pd.Series(med)


def splice_release_day(official: pd.Series, estimate: pd.Series, rerun: int = 12) -> pd.Series:
    """The bank's published series, extended by Econvitals' estimate for months it has not posted.

    While the bank is behind, the whole trailing `rerun` months are the estimate (BEA revises the
    prior months in the same release, and the bank's figures for them are not yet revised); once
    the bank posts, its figures stand and this returns the official series unchanged.
    """
    end = official.index.max()
    beyond = estimate[estimate.index > end]
    out = official.copy()
    if len(beyond) and rerun > len(beyond):
        last = out.index[-(rerun - len(beyond)):]
        out[last] = estimate.reindex(last).fillna(out[last])
    return pd.concat([out, beyond])


def median_pce_official() -> pd.Series:
    """Cleveland Fed median PCE, 1-month percent change (its full-history CSV), to four decimals."""
    text = get("https://www.clevelandfed.org/-/media/files/webcharts/medianpce/median-pce-full-history.csv")
    df = pd.read_csv(io.StringIO(text))
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(df.iloc[:, 0], format="%m/%d/%Y"))
    return s.dropna().round(4)


def trimmed_mean_pce_official() -> pd.Series:
    """Dallas Fed trimmed-mean PCE, 1-month change at an annual rate (its historical workbook)."""
    raw = get("https://www.dallasfed.org/~/media/documents/research/pce/pcehist", binary=True)
    ws = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)["Web - Historical"]
    out = {}
    for r in ws.iter_rows(values_only=True):
        if hasattr(r[0], "year") and isinstance(r[1], (int, float)):
            out[pd.Timestamp(r[0].year, r[0].month, 1)] = float(r[1])
    return pd.Series(out).sort_index()


# ------------------------------------------------------------------------------ the measure sets
PCE_WINDOWS = [("1977-01-01", "2020-01-01"), ("1987-01-01", "2020-01-01"), ("2017-01-01", "2020-01-01")]
CPI_WINDOWS = [("1996-01-01", "2020-01-01")]
OPTIONAL_PCE = ("Core ex Housing and Used Cars",)   # rebuilt from detail; never holds the table back


def pce_measures() -> dict:
    """The eight PCE inflation measures, as index levels, in the order the site shows them."""
    t = pce_headline_indexes()
    trim_est, med_est = pce_release_day_estimates()
    median = splice_release_day(median_pce_official(), med_est)
    trimmed = splice_release_day(trimmed_mean_pce_official(), trim_est)
    return {
        "Overall": t["DPCERG"].dropna(),
        "Core": t["DPCCRG"].dropna(),                     # PCE excluding food and energy
        "Core ex Housing": t["IA001176"].dropna(),
        "Core ex Housing and Used Cars": core_pce_ex_housing_used_vehicles(),
        "Core Services ex Housing": t["IA001260"].dropna(),
        "Market Core": t["DPCXRG"].dropna(),              # market-based core, from 1987
        "Median": chain(median),
        "Trimmed Mean": chain(trimmed, annualized_rates=True, seed_prior_month=True),
    }


def cpi_measures() -> dict:
    """The seven CPI inflation measures (seasonally adjusted), as index levels, from 1990."""
    ids = {"Overall": "CUSR0000SA0", "Core": "CUSR0000SA0L1E",
           "Core ex Shelter": "CUSR0000SA0L12E", "Core ex Shelter and Used Cars": "CUSR0000SA0L12E4"}
    idx = cpi_indexes(list(ids.values()))
    idx = idx[idx.index >= "1990-01-01"]
    out = {name: idx[sid].dropna() for name, sid in ids.items()}
    out["Core Services ex Shelter"] = core_services_cpi_ex_shelter()
    out["Median"] = chain(fred("MEDCPIM157SFRBCLE"))          # Cleveland Fed median CPI
    out["Trimmed Mean"] = chain(fred("TRMMEANCPIM157SFRBCLE"))  # Cleveland Fed 16% trimmed-mean CPI
    return out


def pce_equivalent_adjustments(measures: dict, windows) -> dict:
    """{measure: (adjustment, window)} against overall PCE (BEA table 2.8.4)."""
    overall_pce = pce_headline_indexes()["DPCERG"].dropna()
    return {name: pce_equivalent_adjustment(s, overall_pce, windows) for name, s in measures.items()}
