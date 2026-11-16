"""Every past version of the engine's inputs, from ALFRED (the St. Louis Fed's vintage archive), so
the real-time back-test can feed the engine each series exactly as it stood on a given morning.

    python -m engine.vintages --refresh     # download every twin's full vintage history
    from engine import vintages as V
    V.as_of("retail_total", "2019-07-17")        # pd.Series of the months published by that day

TWINS maps a `sources.MONTHLY` / `sources.QUARTERLY` name to the FRED series that carries the same
figure from the same report (checked 2026-10-19: same agency, same units or a pure rescale, first
prints on the report's own release day). ANXAVS and AMDMTI are revised by both M3 reports, so the
full and the advance names share one twin. Where a source has no twin — the BLS price indexes,
Census HS gold and end-use capital goods, the current-dollar levels behind the shares — the
back-test keeps today's values on the release calendar, and the summary says so (`no_vintage`).

A twin's history begins with its first ALFRED vintage; before that date `as_of` returns None and
the caller falls back to today's values on the calendar (the first pass's rule). The binding cases:
BEA's quarterly growth rates (vintages from 2014-09-26, so the back-test's first two quarters fit
their bridges on today's history) and the advance indicators report (vintages from 2017-11-28, when
FRED's archive of it begins — before that the report is simply absent, as in the first pass).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request

import numpy as np
import pandas as pd

from . import sources as S
from .calendar import _key

VINT = S.RAW / "vintages"
TWINS = {
    # monthly
    "retail_total": "RSAFS", "retail_autos": "RSMVPD", "retail_gas": "RSGASS",
    "retail_building": "RSBMGESD", "retail_food_services": "RSFSDP",
    "real_pce": "PCEC96", "real_pce_goods": "DGDSRX1", "real_pce_services": "PCESC96",
    "core_capgoods_shipments": "ANXAVS", "adv_core_capgoods_shipments": "ANXAVS",
    "construction_private_nonres": "PNRESCONS", "construction_private_res": "PRRESCONS",
    "inv_manufacturing": "AMTMTI", "adv_inv_manufacturing": "AMDMTI",
    "inv_wholesale": "WHLSLRIMSA", "inv_retail": "RETAILIMSA", "inv_total_business": "BUSINV",
    "adv_inv_wholesale": "AMINVTS", "adv_inv_retail": "ARINVTS",
    "inv_retail_autos": "MRTSIM441USS", "inv_retail_xauto": "MRTSIM4400AUSS",
    "adv_inv_retail_autos": "ARIMVPS", "adv_inv_retail_xauto": "ARIEAPS",
    "exports_goods_services": "BOPTEXP", "imports_goods_services": "BOPTIMP",
    "adv_exports_goods": "AITGEXS", "adv_imports_goods": "AITGIXS",
    "emp_state": "CES9092000001", "emp_local": "CES9093000001", "construction_public": "TLPBLCONS",
    "hours_services": "CES0800000016",
    "exports_goods": "BOPGEXP", "imports_goods": "BOPGIMP", "exports_services": "BOPSEXP",
    "imports_services": "BOPSIMP", "inv_mfg_durable": "AMDMTI",
    "inv_mfg_nondurable": "AMNMTI",
    # quarterly (BEA's printed growth rates, contributions and the inventory anchor's levels)
    "gdp_growth": "A191RL1Q225SBEA", "pce_goods_growth": "DGDSRL1Q225SBEA",
    "pce_services_growth": "DSERRL1Q225SBEA", "equipment_growth": "Y033RL1Q225SBEA",
    "ipp_growth": "Y001RL1Q225SBEA", "structures_growth": "A009RL1Q225SBEA",
    "residential_growth": "A011RL1Q225SBEA", "federal_growth": "A823RL1Q225SBEA",
    "state_local_growth": "A829RL1Q225SBEA", "contrib_inventories": "A014RY2Q224SBEA",
    "contrib_net_exports": "A019RY2Q224SBEA", "real_inventories": "CBIC1", "real_gdp": "GDPC1",
    # the growth components' printed contributions (Econvitals' tracking of BEA's later estimates)
    "contrib_pce_goods": "DGDSRY2Q224SBEA", "contrib_pce_services": "DSERRY2Q224SBEA",
    "contrib_equipment": "Y033RY2Q224SBEA", "contrib_ipp": "Y001RY2Q224SBEA",
    "contrib_structures": "A009RY2Q224SBEA", "contrib_residential": "A011RY2Q224SBEA",
    "contrib_federal": "A823RY2Q224SBEA", "contrib_state_local": "A829RY2Q224SBEA",
}
QUARTERLY_NAMES = {n for n in TWINS if n in S.QUARTERLY}
#: FRED keeps only the NEWEST month of the advance goods report live (each month's row ends when the
#: next report prints), so "as published on a day" would hold one month and the engine could not
#: splice month 3 onto the full report. For these, a month's value is the last one PUBLISHED on or
#: before the day, ended or not — month 2 then comes from the previous month's advance report, a
#: first print the current report revises slightly.
STICKY = {"AITGEXS", "AITGIXS"}
OBS_START = "1992-01-01"
_ARR: dict = {}


def _fetch(sid: str) -> list[list]:
    """Every (observation date, realtime_start, realtime_end, value) row ALFRED holds for a series."""
    out, offset = [], 0
    while True:
        url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={_key()}"
               f"&file_type=json&realtime_start=1776-07-04&realtime_end=9999-12-31"
               f"&observation_start={OBS_START}&limit=100000&offset={offset}")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gdp-nowcast"}),
                                            timeout=120) as r:
                    got = json.loads(r.read())
                break
            except Exception:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
        rows = got.get("observations", [])
        out += [[x["date"], x["realtime_start"], x["realtime_end"], x["value"]] for x in rows if x.get("value") not in (None, ".")]
        if len(rows) < 100000:
            return out
        offset += 100000


def refresh(names=None) -> dict:
    """Download (or re-download) the vintage history of every twin; {fred id: rows}."""
    done = {}
    for sid in sorted({TWINS[n] for n in (names or TWINS)}):
        try:
            rows = _fetch(sid)
            VINT.mkdir(parents=True, exist_ok=True)
            (VINT / f"{sid}.json").write_text(json.dumps(rows))
            done[sid] = len(rows)
        except Exception as e:  # noqa: BLE001
            done[sid] = f"ERR {type(e).__name__}: {str(e)[:80]}"
        _ARR.pop(sid, None)
    return done


def refresh_stale(names, since: str) -> dict:
    """Download again the twins of `names` whose copy on disk holds no version from `since` (an ISO
    date: BEA's latest advance estimate) or later, so the newest quarter's first print is in them;
    {fred id: rows, or 'ERR ...'} for those it tried. The live fit reads first prints
    (`bridge.FIRST_PRINT_TARGETS`): a copy made before a quarter's advance estimate lacks that quarter,
    and `first_prints` would then leave it to BEA's revised value (2026-11-15: the copies in use
    dated from 2026-10-19, so 2026Q3 would have been fit on its second estimate)."""
    stale = []
    for n in names:
        sid = TWINS.get(n)
        if not sid:
            continue
        p = VINT / f"{sid}.json"
        try:
            newest = max(r[1] for r in json.loads(p.read_text()))
        except (OSError, ValueError):
            newest = ""
        if newest < since:
            stale.append(n)
    if not stale:
        return {}
    got = refresh(stale)
    for n in stale:
        _FP.pop(n, None)
    return got


def _arrays(sid: str):
    """(observation periods as ints, realtime start, realtime end, values, first vintage date)."""
    if sid not in _ARR:
        p = VINT / f"{sid}.json"
        if not p.exists():
            refresh([n for n, s in TWINS.items() if s == sid][:1])
        rows = json.loads(p.read_text())
        obs = np.array([r[0] for r in rows])
        rs = np.array([r[1] for r in rows])
        re_ = np.array([r[2] for r in rows])
        val = np.array([float(r[3]) for r in rows])
        _ARR[sid] = (obs, rs, re_, val, min(rs.tolist()) if len(rs) else "9999")
    return _ARR[sid]


def first_vintage(name: str) -> str | None:
    sid = TWINS.get(name)
    return _arrays(sid)[4] if sid else None


def as_of(name: str, day) -> pd.Series | None:
    """The series as published on `day` (ISO date), or None when the name has no twin or the day
    is before the twin's first vintage."""
    sid = TWINS.get(name)
    if not sid:
        return None
    day = str(day)[:10]
    obs, rs, re_, val, first = _arrays(sid)
    if day < first:
        return None
    freq = "Q" if name in QUARTERLY_NAMES else "M"
    if sid in STICKY:
        m = rs <= day
        latest: dict = {}
        for o, r, v in zip(obs[m], rs[m], val[m]):
            if o not in latest or r > latest[o][0]:
                latest[o] = (r, v)
        return pd.Series({pd.Period(o, freq=freq): v for o, (r, v) in latest.items()}, dtype=float).sort_index()
    m = (rs <= day) & (re_ >= day)
    idx = [pd.Period(d, freq=freq) for d in obs[m]]
    return pd.Series(val[m], index=idx, dtype=float).sort_index()


_FP: dict = {}


def advance_dates() -> dict:
    """{quarter: date of BEA's advance estimate}: Atlanta's track record (2011Q3 on, actual dates,
    the 2025 shutdown included; the Atlanta Fed reader takes them from the TrackingArchives sheet, since
    TrackRecord misdates 2024Q3 and 2026Q3), the FRED schedule before it."""
    if "dates" not in _FP:
        from . import calendar as cal
        out = {}
        try:
            from .public_doors import atlfed
            out = {pd.Period(k, freq="Q"): v["release_date"] for k, v in atlfed.gdpnow_track_record().items()}
        except Exception:  # noqa: BLE001
            pass
        for q in pd.period_range("1993Q1", pd.Timestamp.today().to_period("Q"), freq="Q"):
            if q not in out:
                d = cal.advance_gdp_date(q)
                if d:
                    out[q] = d
        _FP["dates"] = out
    return _FP["dates"]


def first_prints(name: str) -> pd.Series:
    """BEA's FIRST PRINT of a quarterly series for every quarter its ALFRED twin reaches: the value
    as of that quarter's advance estimate. Quarters before the twin's first vintage are absent."""
    if name not in _FP:
        out = {}
        first = first_vintage(name)
        for q, d in advance_dates().items():
            if first is None or d < first:
                continue
            s = as_of(name, d)
            if s is not None and q in s.index:
                out[q] = float(s.loc[q])
        _FP[name] = pd.Series(out, dtype=float).sort_index()
    return _FP[name]


if __name__ == "__main__":  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    if a.refresh:
        for k, v in refresh().items():
            print(f"{k:18s} {v}")
    for n in ("retail_total", "gdp_growth"):
        s = as_of(n, "2019-07-17")
        print(n, "as of 2019-07-17:", None if s is None else f"{len(s)} obs through {s.index[-1]}, last {s.iloc[-1]:,.1f}")
