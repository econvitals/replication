"""Readers and shared arithmetic for the labor-market replications.

    atlanta_fed_wage_tracker()   the Atlanta Fed Wage Growth Tracker, from the Bank's own workbook
    bls_ln(series_ids)           Current Population Survey series from BLS's bulk "ln" file
    cps_age_sex_cells()          the 30 age-by-sex cells behind the age-adjusted rates
    chained_decomposition(...)   the month-by-month split into behavior and composition

The last two are shared by measures/age-adjusted-labor-rates and measures/aging-counterfactual,
which are the same decomposition anchored in different places.
"""
from __future__ import annotations

import hashlib
import io
import re
import time

import pandas as pd
import requests

from common.econdata import CACHE, USER_AGENT, fred, get

# ---------------------------------------------------------------------- Atlanta Fed tracker
WGT_PAGE = "https://www.atlantafed.org/research-and-data/data/wage-growth-tracker"
WGT_FILE = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
            "research-and-data/data/wage-growth-tracker/wage-growth-data.xlsx")


def atlanta_fed_wage_tracker() -> pd.Series:
    """The overall Wage Growth Tracker (3-month moving average, percent), by month.

    Read from the Bank's workbook (sheet "data_overall", column "Overall"), which can be a few
    days ahead of FRED's copy (FRBATLWGT3MMAUMHWGO). The Bank has moved the file more than once;
    if the address above stops answering with a workbook, the link is re-read from the
    tracker's page. If the Bank cannot be reached at all, FRED's copy is used instead.
    """
    def workbook(url):
        try:
            data = get(url if url.startswith("http") else "https://www.atlantafed.org" + url,
                       binary=True)
        except Exception:                          # moved (404) or the network is down
            return None
        return data if data[:4] == b"PK\x03\x04" else None   # a real .xlsx is a zip file

    data = workbook(WGT_FILE)
    if data is None:
        try:
            links = re.findall(r'href="([^"]+wage-growth-data\.xlsx)"', get(WGT_PAGE))
        except Exception:
            links = []
        data = next((d for d in map(workbook, links) if d), None)
    if data is None:
        print("  Atlanta Fed workbook unavailable; using FRED's copy of the tracker")
        return fred("FRBATLWGT3MMAUMHWGO")
    sheet = pd.read_excel(io.BytesIO(data), sheet_name="data_overall", header=None)
    header = sheet.index[sheet.eq("Overall").any(axis=1)][0]
    col = sheet.columns[sheet.loc[header].eq("Overall")][0]
    rows = sheet.loc[header + 1:]
    s = pd.Series(pd.to_numeric(rows[col], errors="coerce").values,
                  index=pd.to_datetime(rows[sheet.columns[0]], errors="coerce"))
    s = s[s.index.notna()].dropna()
    s.index = s.index.to_period("M").to_timestamp().rename("date")
    return s.rename("WGT")


# ---------------------------------------------------------------------- BLS household survey
LN_FILE = "https://download.bls.gov/pub/time.series/ln/ln.data.1.AllData"


def bls_ln(series_ids) -> pd.DataFrame:
    """Monthly values for Current Population Survey (LN) series, one column each.

    BLS publishes the whole household-survey database as one bulk file (about 400 MB; there
    are no smaller pieces for this survey, and FRED carries only some of these series). The
    file is streamed and only the requested series are kept. The kept rows are cached with
    the file's Last-Modified date, so the 400 MB is downloaded again only when BLS posts a
    new version (roughly once a month, with the jobs report), not on every run.
    """
    ids = sorted(set(series_ids))
    head = requests.head(LN_FILE, headers={"User-Agent": USER_AGENT}, timeout=60)
    head.raise_for_status()
    stamp = head.headers.get("Last-Modified", "")
    tag = re.sub(r"\W+", "", stamp) + "_" + hashlib.sha1(" ".join(ids).encode()).hexdigest()[:10]
    cached = CACHE / f"ln_subset_{tag}.tsv"
    if not cached.exists():
        keep, want = [], set(ids)
        for attempt in range(3):
            try:
                with requests.get(LN_FILE, stream=True, timeout=300,
                                  headers={"User-Agent": USER_AGENT}) as r:
                    r.raise_for_status()
                    r.encoding = "utf-8"
                    lines = r.iter_lines(decode_unicode=True)
                    keep = [next(lines)]                      # the header row
                    keep += [ln for ln in lines if ln.split("\t", 1)[0].strip() in want]
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(10 * (attempt + 1))
        CACHE.mkdir(parents=True, exist_ok=True)
        for old in CACHE.glob("ln_subset_*.tsv"):             # keep only the current vintage
            if old.name.split("_")[2] != tag.split("_")[0]:
                old.unlink()
        cached.write_text("\n".join(keep))
    df = pd.read_csv(cached, sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda c: c.str.strip())
    df = df[df["period"].str.match(r"M(0[1-9]|1[0-2])")]
    df = df.assign(date=pd.to_datetime(df["year"] + "-" + df["period"].str[1:] + "-01"),
                   value=pd.to_numeric(df["value"], errors="coerce"))
    out = df.pivot_table(index="date", columns="series_id", values="value", aggfunc="first")
    missing = set(ids) - set(out.columns)
    if missing:
        raise RuntimeError(f"BLS's LN file has no rows for {sorted(missing)}")
    return out[ids]


# ---------------------------------------------------------------------- age-by-sex cells
# The Current Population Survey's 15 age bins x 2 sexes. Each code is the demographic part of a
# BLS series id: LNU00<code> is population, LNU01<code> the labor force and LNU02<code> employment,
# all not seasonally adjusted (BLS publishes these fine cells only unadjusted).
AGE_BINS = ["16_17", "18_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54",
            "55_59", "60_61", "62_64", "65_69", "70_74", "75plus"]
FINE_CODES = {
    "m": ["000152", "000154", "000037", "000163", "000171", "000172", "000179", "000181",
          "000188", "000189", "000196", "000198", "000203", "024939", "015346"],
    "f": ["000317", "000319", "000038", "000326", "000332", "000333", "000338", "000340",
          "000345", "000346", "000351", "000353", "000358", "024940", "015349"],
}
# The broader groups BLS does publish seasonally adjusted: LNS11<code> (labor force) and
# LNS12<code> (employment). Each fine bin is scaled to agree with its group (see below).
SA_CODES = {
    "m": {"16_17": "000152", "18_19": "000154", "20_24": "000037", "25_34": "000164",
          "35_44": "000173", "45_54": "000182", "55plus": "024231"},
    "f": {"16_17": "000317", "18_19": "000319", "20_24": "000038", "25_34": "000327",
          "35_44": "000334", "45_54": "000341", "55plus": "024232"},
}
SA_PARENT = {"16_17": "16_17", "18_19": "18_19", "20_24": "20_24", "25_29": "25_34",
             "30_34": "25_34", "35_39": "35_44", "40_44": "35_44", "45_49": "45_54",
             "50_54": "45_54", "55_59": "55plus", "60_61": "55plus", "62_64": "55plus",
             "65_69": "55plus", "70_74": "55plus", "75plus": "55plus"}
BANDS = {"16plus": AGE_BINS, "16_24": AGE_BINS[:3], "25_54": AGE_BINS[3:9],
         "55plus": AGE_BINS[9:]}
CELLS_START = "1990-01-01"      # BLS's detailed cells are complete from 1990


def cps_age_sex_cells():
    """Seasonally consistent participation and employment rates for the 30 age-by-sex cells.

    Returns (pop, lfpr, epop): three DataFrames indexed by month with one column per cell
    ("m16_17", "f75plus", ...). `pop` is the cell's population (thousands); `lfpr` and `epop`
    are fractions (0-1).

    The seasonal adjustment follows the Peterson Institute method: each fine cell's unadjusted
    rate is multiplied by (the published seasonally adjusted rate of its broader group) /
    (that group's unadjusted rate), where both group rates use the group's unadjusted
    population, since BLS publishes no adjusted population. A month the household survey did
    not collect (October 2025) is simply absent.
    """
    fine = {f"{sex}{age}": code for sex in "mf" for age, code in zip(AGE_BINS, FINE_CODES[sex])}
    ids = [f"LNU0{k}{c}" for c in fine.values() for k in "012"]
    ids += [f"LNS1{k}{c}" for sex in "mf" for c in SA_CODES[sex].values() for k in "12"]
    raw = bls_ln(ids).loc[CELLS_START:].dropna(how="all")

    pop = pd.DataFrame({cell: raw[f"LNU00{c}"] for cell, c in fine.items()})
    lf = pd.DataFrame({cell: raw[f"LNU01{c}"] for cell, c in fine.items()})
    em = pd.DataFrame({cell: raw[f"LNU02{c}"] for cell, c in fine.items()})
    lfpr, epop = lf / pop, em / pop
    for sex in "mf":
        for grp, code in SA_CODES[sex].items():
            members = [f"{sex}{a}" for a in AGE_BINS if SA_PARENT[a] == grp]
            gpop = pop[members].sum(axis=1)
            for rate, level, sa in ((lfpr, lf, raw[f"LNS11{code}"]),
                                    (epop, em, raw[f"LNS12{code}"])):
                nsa_rate = level[members].sum(axis=1) / gpop
                factor = (sa / gpop) / nsa_rate
                factor = factor.where(factor.notna() & (nsa_rate > 0), 1.0)
                rate[members] = rate[members].mul(factor, axis=0)
    keep = pop.notna().all(axis=1)
    return pop[keep], lfpr[keep], epop[keep]


def chained_decomposition(band: str = "16plus"):
    """The month-by-month split of the participation and employment rates of an age band.

    Returns (frame, within): `frame` has, by month, the actual rates ("lfpr_actual",
    "epop_actual", in percent) and the cumulative behavior term ("lfpr_cumw", "epop_cumw");
    `within` maps "lfpr"/"epop" to a DataFrame of each cell's monthly behavior contribution
    in percentage points.

    For shares s_i (cell population / band population) and rates r_i, the actual rate is
    sum_i s_i r_i, and its change from one month to the next splits exactly into

        behavior     sum_i  0.5 (s_i,t + s_i,t-1) (r_i,t - r_i,t-1)
        composition  sum_i  0.5 (r_i,t + r_i,t-1) (s_i,t - s_i,t-1)

    (a chained Tornqvist-style split: the weights follow the population as it changes). Only the
    behavior part is cumulated. A band other than 16plus uses only its own cells, so its
    adjustment holds the age-and-sex mix within the band, not the whole population.
    """
    pop, lfpr, epop = cps_age_sex_cells()
    cells = [f"{sex}{a}" for sex in "mf" for a in BANDS[band]]
    pop = pop[cells]
    share = pop.div(pop.sum(axis=1), axis=0)
    frame, within = {}, {}
    for name, rate in (("lfpr", lfpr[cells]), ("epop", epop[cells])):
        frame[f"{name}_actual"] = 100 * (share * rate).sum(axis=1)
        within[name] = 100 * 0.5 * (share + share.shift()) * rate.diff()
        frame[f"{name}_cumw"] = within[name].sum(axis=1).cumsum()
    return pd.DataFrame(frame), within
