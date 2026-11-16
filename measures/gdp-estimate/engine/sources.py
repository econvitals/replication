"""Every source series the engine reads, by name, with where it comes from and a cached fetch.

    from engine import sources as S
    S.monthly("retail_total")          # pd.Series indexed by monthly Period, SA, as published
    S.quarterly("gdp_growth")          # pd.Series indexed by quarterly Period (BEA's percent changes)
    S.refresh(names=[...])             # re-read sources live and rewrite their saved copies

The doors (in this public copy, public_doors.py says where each reads):
  * **Census** — `eits.py` (retail sales, factory shipments and inventories and their advance report,
    construction spending, the wholesale, retail and total business inventory books and their
    ADVANCE reports, the advance goods-trade report, the services survey).
  * **BEA** — the monthly real PCE table T20806 and the quarterly percent changes T10101,
    contributions T10102, current dollars T10105 and chained dollars T10106, from BEA's API.
  * **BLS** — the price indexes that turn nominal sources into real ones, and payrolls and hours,
    from FRED's copies of BLS's series.
  * **Census international trade, HS** — nonmonetary gold (7108 + 7115), to strip from goods trade.
  * **FRED** — the failure-only fallback for public construction spending (`FRED_FALLBACK`), read
    only when Census's spreadsheet cannot be; the two are the same series.
  * **Census international trade, end use** — capital goods except automotive (end-use 2),
    imports and exports, NSA, for the equipment component's commodity flow (imported computers
    and chips are equipment investment; `components.py` seasonally adjusts them).
  * **Census construction spending, spreadsheets** (door "c30") — the release's own time-series
    spreadsheets; the estimate reads one column, total public construction (`pubsatime`), which the
    economic-indicators API does not carry seasonally adjusted.
  * The door "exhibit" (the trade report's Exhibit 1) and the other "c30" columns (`privsatime`,
    `slsatime`) serve Econvitals' tracking of BEA's later estimates of a quarter, which this folder
    does not include; the estimate never reads them.

Everything monthly is seasonally adjusted and in the agency's own units (Census $ millions,
BEA $ billions at annual rates, BLS index levels). Nothing here converts units — `components.py`
does, where the arithmetic is readable in one place.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from . import eits

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "ref"

# ── the catalog ────────────────────────────────────────────────────────────────────────────────
#: name -> (door, address). Census addresses are (dataset, category, data type[, freq]);
#: BEA addresses are "TABLE/CODE" (monthly) or "TABLE/CODE@Q"; BLS addresses are series ids.
MONTHLY = {
    # consumption
    "real_pce":            ("bea", "T20806/DPCERX"),
    "real_pce_goods":      ("bea", "T20806/DGDSRX"),
    "real_pce_services":   ("bea", "T20806/DSERRX"),
    "real_pce_durables":   ("bea", "T20806/DDURRX"),
    "real_pce_nondurables": ("bea", "T20806/DNDGRX"),
    "retail_total":        ("census", ("marts", "44X72", "SM")),
    "retail_autos":        ("census", ("marts", "441", "SM")),
    "retail_gas":          ("census", ("marts", "447", "SM")),
    "retail_building":     ("census", ("marts", "444", "SM")),
    "retail_food_services": ("census", ("marts", "722", "SM")),
    # equipment
    "core_capgoods_shipments": ("census", ("m3", "NXA", "VS")),
    "durable_shipments":   ("census", ("m3", "MDM", "VS")),
    "adv_core_capgoods_shipments": ("census", ("advm3", "NXA", "VS")),
    "adv_durable_shipments": ("census", ("advm3", "MDM", "VS")),
    # structures and residential
    "construction_private_nonres": ("census", ("vip", "ANRXX", "V")),
    "construction_private_res":    ("census", ("vip", "A00XX", "V")),
    "construction_private_total":  ("census", ("vip", "AXXXX", "V")),
    "construction_single_family":  ("c30", ("privsatime", "New single family")),
    "construction_multifamily":    ("c30", ("privsatime", "New multifamily")),
    "construction_state_local":    ("c30", ("slsatime", "Total")),
    "housing_starts":      ("census", ("resconst", "ASTARTS", "TOTAL")),
    "new_home_sales":      ("census", ("ressales", "ASOLD", "TOTAL")),
    # inventories (book values, $mn)
    "inv_manufacturing":   ("census", ("m3", "MTM", "TI")),     # total manufacturing (ANM is one industry)
    "inv_mfg_durable":     ("census", ("m3", "MDM", "TI")),
    "inv_mfg_nondurable":  ("census", ("m3", "MNM", "TI")),
    "inv_wholesale":       ("census", ("mwts", "42", "IM")),
    "inv_wholesale_durable": ("census", ("mwts", "423", "IM")),
    "inv_wholesale_nondurable": ("census", ("mwts", "424", "IM")),
    "inv_retail":          ("census", ("mrts", "44000", "IM")),
    "inv_total_business":  ("census", ("mtis", "TOTBUS", "IM")),
    "adv_inv_wholesale":   ("census", ("mwtsadv", "42", "IM")),
    "adv_inv_retail":      ("census", ("mrtsadv", "44000", "IM")),
    "adv_inv_manufacturing": ("census", ("advm3", "MDM", "TI")),    # durables only, the advance report
    "inv_retail_autos":    ("census", ("mrts", "441", "IM")),
    "inv_retail_xauto":    ("census", ("mrts", "4400A", "IM")),
    "adv_inv_retail_autos": ("census", ("mrtsadv", "441", "IM")),
    "adv_inv_retail_xauto": ("census", ("mrtsadv", "4400A", "IM")),
    # trade ($mn, BOP basis from the FT900 JSON; Census basis from the advance report)
    "exports_goods_services": ("census", ("ftd", "BOPGS", "EXP")),
    "imports_goods_services": ("census", ("ftd", "BOPGS", "IMP")),
    # the seasonally adjusted goods/services split, which the EITS feed does not carry (its BOPG is
    # unadjusted): the FT900's Exhibit 1 (read only by Econvitals' tracking of BEA's later estimates)
    "exports_goods":       ("exhibit", "EXP/GOODS"),
    "imports_goods":       ("exhibit", "IMP/GOODS"),
    "exports_services":    ("exhibit", "EXP/SERVICES"),
    "imports_services":    ("exhibit", "IMP/SERVICES"),
    "adv_exports_goods":   ("census", ("ftdadv", "CBG", "EXP")),
    "adv_imports_goods":   ("census", ("ftdadv", "CBG", "IMP")),
    # prices (BLS index levels)
    "cpi_all":             ("bls", "CUSR0000SA0"),
    "cpi_goods_ex_food_energy": ("bls", "CUSR0000SACL1E"),     # commodities less food and energy
    "cpi_food_home":       ("bls", "CUSR0000SAF11"),
    "cpi_gasoline":        ("bls", "CUSR0000SETB01"),
    # government (BLS payrolls; public construction from Census's own spreadsheet, see the doors above)
    "emp_state":           ("bls", "CES9092000001"),
    "emp_local":           ("bls", "CES9093000001"),
    "construction_public": ("c30", ("pubsatime", "Total")),
    "hours_services":      ("bls", "CES0800000016"),           # aggregate weekly hours, private service-providing
    # hours for Econvitals' productivity tracker: BLS's recipe from public series
    "hours_all_emp":       ("bls", "CES0500000001"),           # all employees, total private
    "hours_pns_awh":       ("bls", "CES0500000007"),           # production and nonsupervisory average weekly hours
    "hours_ehs_emp":       ("bls", "CES6500000006"),           # education and health, production and nonsupervisory
    "hours_ehs_awh":       ("bls", "CES6500000007"),
    "hours_other_emp":     ("bls", "CES8000000006"),           # other services, production and nonsupervisory
    "hours_other_awh":     ("bls", "CES8000000007"),
    "self_employed_at_work": ("bls", "LNU02033371"),           # unincorporated nonfarm self-employed at work, NSA
    "ppi_capital_equipment": ("bls", "WPSFD41312"),           # private capital equipment
    "ppi_construction_inputs": ("bls", "WPUIP2300001"),        # inputs to construction industries
    "ppi_finished_goods":  ("bls", "WPSFD49207"),
    "ppi_finished_core":   ("bls", "WPSFD4131"),            # finished goods less foods and energy
    "import_prices":       ("bls", "EIUIR"),
    "export_prices":       ("bls", "EIUIQ"),
    "import_prices_capital": ("bls", "EIUIR2"),              # capital goods except automotive
}
#: a source whose publisher read failed -> the FRED copy of the same series, read instead (and said so).
#: Proven value-equal before it was listed: TLPBLCONS against pubsatime's "Total Public Construction",
#: 405 of 405 months identical, 1993-01..2026-09, max |diff| 0 (2026-11-15). Never the first door.
FRED_FALLBACK = {"construction_public": "TLPBLCONS"}

#: monthly sources from the Census international-trade API rather than a catalog door
INTLTRADE = ("gold_exports", "gold_imports", "capgoods_imports", "capgoods_exports")

QUARTERLY = {
    # BLS's output for nonfarm business IS this line of table 1.3.3 (Econvitals' productivity tracker)
    "nfb_output_index":    ("bea", "T10303/B358RA@Q"),
    # BEA's printed real growth rates (percent, annual rate) — the targets of the bridges
    "gdp_growth":          ("bea", "T10101/A191RL@Q"),
    "pce_growth":          ("bea", "T10101/DPCERL@Q"),
    "pce_goods_growth":    ("bea", "T10101/DGDSRL@Q"),
    "pce_services_growth": ("bea", "T10101/DSERRL@Q"),
    "equipment_growth":    ("bea", "T10101/Y033RL@Q"),
    "ipp_growth":          ("bea", "T10101/Y001RL@Q"),
    "structures_growth":   ("bea", "T10101/A009RL@Q"),
    "residential_growth":  ("bea", "T10101/A011RL@Q"),
    "exports_growth":      ("bea", "T10101/A020RL@Q"),
    "imports_growth":      ("bea", "T10101/A021RL@Q"),
    "federal_growth":      ("bea", "T10101/A823RL@Q"),
    "state_local_growth":  ("bea", "T10101/A829RL@Q"),
    # contributions (percentage points); the eight growth components' are where Econvitals'
    # tracking of BEA's second and third estimates starts (T10102 codes verified 2026-10-27)
    "contrib_inventories": ("bea", "T10102/A014RY@Q"),
    "contrib_net_exports": ("bea", "T10102/A019RY@Q"),
    "contrib_pce":         ("bea", "T10102/DPCERY@Q"),
    "contrib_pce_goods":   ("bea", "T10102/DGDSRY@Q"),
    "contrib_pce_services": ("bea", "T10102/DSERRY@Q"),
    "contrib_equipment":   ("bea", "T10102/Y033RY@Q"),
    "contrib_ipp":         ("bea", "T10102/Y001RY@Q"),
    "contrib_structures":  ("bea", "T10102/A009RY@Q"),
    "contrib_residential": ("bea", "T10102/A011RY@Q"),
    "contrib_federal":     ("bea", "T10102/A823RY@Q"),
    "contrib_state_local": ("bea", "T10102/A829RY@Q"),
    # nominal levels for the shares ($bn SAAR)
    "nominal_gdp":         ("bea", "T10105/A191RC@Q"),
    "nominal_pce_goods":   ("bea", "T10105/DGDSRC@Q"),
    "nominal_pce_services": ("bea", "T10105/DSERRC@Q"),
    "nominal_equipment":   ("bea", "T10105/Y033RC@Q"),
    "nominal_ipp":         ("bea", "T10105/Y001RC@Q"),
    "nominal_structures":  ("bea", "T10105/B009RC@Q"),
    "nominal_residential": ("bea", "T10105/A011RC@Q"),
    "nominal_federal":     ("bea", "T10105/A823RC@Q"),
    "nominal_state_local": ("bea", "T10105/A829RC@Q"),
    "nominal_exports":     ("bea", "T10105/B020RC@Q"),
    "nominal_imports":     ("bea", "T10105/B021RC@Q"),
    "nominal_inventories": ("bea", "T10105/A014RC@Q"),
    # chained-dollar inventories and trade (for the contribution bridges)
    "real_inventories":    ("bea", "T10106/A014RX@Q"),
    "real_exports":        ("bea", "T10106/A020RX@Q"),
    "real_imports":        ("bea", "T10106/A021RX@Q"),
    "real_gdp":            ("bea", "T10106/A191RX@Q"),
}

GOLD_HS = ("7108", "7115")
CENSUS_HS_START = "2013-01"


# ── the fetchers ───────────────────────────────────────────────────────────────────────────────
def _bea_series(addr: str, start: str = "1992-01-01") -> pd.Series:
    from .public_doors import bea
    s = bea.series(addr, start=start)
    freq = "Q" if addr.endswith("@Q") else "M"
    idx = [pd.Period(o.d, freq=freq) for o in s.obs if o.v is not None]
    return pd.Series([o.v for o in s.obs if o.v is not None], index=idx, name=addr, dtype=float)


def _bls_levels(ids: list[str], start_year: int = 1992) -> dict[str, pd.Series]:
    from .public_doors import bls_client
    got = bls_client.fetch(ids, start_year, dt.date.today().year)
    out = {}
    for sid in ids:
        obs = sorted(got.get(sid) or [], key=lambda o: o.d)
        out[sid] = pd.Series([o.v for o in obs], index=[pd.Period(o.d, freq="M") for o in obs], name=sid, dtype=float)
    return out


def _fred_series(door: str, addr: str) -> pd.Series:
    """A FRED id (door "fred") or an in-house provider key (door "provider", unused here), monthly."""
    if door == "fred":
        from .public_doors import fred
        s = fred.series(addr, start="1992-01-01")
    else:
        from .public_doors import providers
        s = providers.series(addr)
    obs = [o for o in s.obs if o.v is not None]
    return pd.Series([float(o.v) for o in obs], index=[pd.Period(o.d, freq="M") for o in obs], name=addr, dtype=float)


def _publisher_or_fred(name: str, fetch) -> pd.Series:
    """`fetch()` — the publisher's own door — or, only when that raises and `name` has a proven FRED
    copy (FRED_FALLBACK), the FRED copy, with `.attrs["fallback"]` saying so. The number served is the
    same one, but `refresh()` still reports the source as failed (an "ERR" naming the fallback), so a
    publisher door that breaks is red the same day instead of quietly turning into FRED for good."""
    try:
        return fetch()
    except Exception as e:  # noqa: BLE001
        sid = FRED_FALLBACK.get(name)
        if not sid:
            raise
        s = _fred_series("fred", sid)
        s.attrs["fallback"] = (f"the publisher's read failed ({type(e).__name__}: {str(e)[:80]}); "
                               f"served FRED {sid}, the same series")
        return s


def _census_series(addr: tuple, refresh: bool = False) -> pd.Series:
    ds, cat, dtp = addr[:3]
    freq = addr[3] if len(addr) > 3 else "M"
    d = eits.series(ds, cat, dtp, freq=freq, refresh=refresh)
    return pd.Series(list(d.values()), index=list(d.keys()), name=f"{ds}:{cat}/{dtp}", dtype=float)


C30 = "https://www.census.gov/construction/c30/xlsx/{}.xlsx"
_DOWNLOADS: dict = {}            # one download per file per process (several sources share one)


def _c30(addr: tuple) -> pd.Series:
    """One column of a Census construction-spending time-series spreadsheet ($mn SAAR, SA): the
    file (privsatime, slsatime) and the start of the column's header ("New single family",
    "Total"). Rows are dated "Aug-26p" / "Jul-26r" / "May-26", newest first."""
    import subprocess
    import openpyxl
    name, col = addr
    if ("c30", name) not in _DOWNLOADS:
        tmp = RAW / f"c30_{name}.xlsx"
        RAW.mkdir(parents=True, exist_ok=True)
        # census.gov serves curl's user agent the file (Python's default client is refused)
        subprocess.run(["curl", "-s", "-f", "-L", "-A", "curl/8.7.1", "--max-time", "60", "-o", str(tmp),
                        C30.format(name)], check=True, capture_output=True)
        wb = openpyxl.load_workbook(tmp, read_only=True, data_only=True)
        _DOWNLOADS[("c30", name)] = list(wb.worksheets[0].iter_rows(values_only=True))
    rows = _DOWNLOADS[("c30", name)]
    head_i = next(i for i, r in enumerate(rows) if r and str(r[0] or "").strip() == "Date")
    j = next(k for k, h in enumerate(rows[head_i]) if str(h or "").replace("\n", " ").replace("_x000D_", "").strip()
             .startswith(col))
    out = {}
    for r in rows[head_i + 1:]:
        lab = str(r[0] or "").strip().rstrip("pr")
        try:
            m = pd.Period(dt.datetime.strptime(lab, "%b-%y"), freq="M")
        except ValueError:
            continue
        if isinstance(r[j], (int, float)):
            out[m] = float(r[j])
    return pd.Series(out, dtype=float).sort_index()


def _exhibit(addr: str) -> pd.Series:
    """One FT900 Exhibit 1 series ($mn, SA), "EXP/GOODS" etc.: Census's history
    workbook, plus the month after its last from the current release's exh1.xlsx if it is out."""
    from .public_doors import census_direct, census_ftd
    obs = census_direct.series(f"exhibit:{addr}")
    s = pd.Series({pd.Period(o.d.strftime("%Y-%m"), freq="M"): float(o.v) for o in obs}, dtype=float).sort_index()
    nxt = s.index[-1] + 1
    if ("exh1", nxt) not in _DOWNLOADS:
        try:
            _DOWNLOADS[("exh1", nxt)] = census_ftd.fetch_exh1((nxt.year, nxt.month))
        except Exception:  # noqa: BLE001 — the history alone; the month arrives with its next refresh
            _DOWNLOADS[("exh1", nxt)] = {}
    v = _DOWNLOADS[("exh1", nxt)].get(f"exhibit:{addr}")
    if v is not None:
        s.loc[nxt] = v
    return s


def gold_trade(flow: str, refresh: bool = False) -> pd.Series:
    """Nonmonetary gold, HS 7108 + 7115, Census basis, NSA, $mn — {'exports'|'imports'}."""
    p = RAW / f"gold_{flow}.json"
    if not refresh and p.exists() and (time.time() - p.stat().st_mtime) < 6 * 3600:
        d = json.loads(p.read_text())
    else:
        key = eits.api_key()
        prefix, value = ("E", "ALL_VAL_MO") if flow == "exports" else ("I", "GEN_VAL_MO")
        d = {}
        for hs in GOLD_HS:
            q = urllib.parse.urlencode({"get": value, "COMM_LVL": "HS4", f"{prefix}_COMMODITY": hs,
                                        "time": f"from {CENSUS_HS_START}", "key": key})
            url = f"https://api.census.gov/data/timeseries/intltrade/{flow}/hs?{q}"
            with urllib.request.urlopen(url, timeout=120) as r:
                rows = json.load(r)
            head = rows[0]
            for row in rows[1:]:
                rec = dict(zip(head, row))
                d[rec["time"]] = d.get(rec["time"], 0.0) + float(rec[value]) / 1e6
        RAW.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d))
    return pd.Series({pd.Period(k[:7], freq="M"): v for k, v in d.items()}, dtype=float).sort_index()


def capgoods_trade(flow: str, refresh: bool = False) -> pd.Series:
    """Capital goods except automotive (end-use 2), Census basis, NSA, $mn — {'exports'|'imports'}."""
    p = RAW / f"capgoods_{flow}.json"
    if not refresh and p.exists() and (time.time() - p.stat().st_mtime) < 6 * 3600:
        d = json.loads(p.read_text())
    else:
        var, value = ("E_ENDUSE", "ALL_VAL_MO") if flow == "exports" else ("I_ENDUSE", "GEN_VAL_MO")
        q = urllib.parse.urlencode({"get": value, var: "2", "time": f"from {CENSUS_HS_START}", "key": eits.api_key()})
        url = f"https://api.census.gov/data/timeseries/intltrade/{flow}/enduse?{q}"
        with urllib.request.urlopen(url, timeout=120) as r:
            rows = json.load(r)
        head = rows[0]
        d = {}
        for row in rows[1:]:
            rec = dict(zip(head, row))
            d[rec["time"]] = float(rec[value]) / 1e6
        RAW.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d))
    return pd.Series({pd.Period(k[:7], freq="M"): v for k, v in d.items()}, dtype=float).sort_index()


# ── the public face, with one disk cache per door ─────────────────────────────────────────────
_MEM: dict = {}


def _load_cache(name: str) -> dict | None:
    p = RAW / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _save_cache(name: str, obj: dict) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{name}.json").write_text(json.dumps(obj))


def _to_series(d: dict, freq: str) -> pd.Series:
    return pd.Series({pd.Period(k, freq=freq): float(v) for k, v in d.items()}, dtype=float).sort_index()


def refresh(bls_too: bool = True, names=None) -> dict:
    """Re-pull sources live and rewrite the caches — all of them, or only `names` (MONTHLY /
    QUARTERLY / the intltrade four; a report's morning run refreshes just what it carries).
    Each Census dataset is downloaded once however many sources share it. Returns {name: latest
    period, or 'ERR ...'}."""
    want = None if names is None else set(names)
    pick = lambda n: want is None or n in want  # noqa: E731
    latest = {}
    bea = {n: a for n, (door, a) in {**MONTHLY, **QUARTERLY}.items() if door == "bea" and pick(n)}
    for n, a in bea.items():
        try:
            s = _bea_series(a)
            _save_cache(n, {str(k): v for k, v in s.items()})
            latest[n] = str(s.index[-1]) if len(s) else None
        except Exception as e:  # noqa: BLE001
            latest[n] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    census = {n: a for n, (door, a) in MONTHLY.items() if door == "census" and pick(n)}
    fetched: dict = {}
    for n, a in census.items():
        ds, freq = a[0], (a[3] if len(a) > 3 else "M")
        try:
            if ds not in fetched:
                eits.dataset_rows(ds, freq, refresh=True)
                fetched[ds] = True
            s = _census_series(a)
            _save_cache(n, {str(k): v for k, v in s.items()})
            latest[n] = str(s.index[-1]) if len(s) else None
        except Exception as e:  # noqa: BLE001
            fetched[ds] = True
            latest[n] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    for n, (door, a) in MONTHLY.items():
        if door in ("fred", "provider", "c30", "exhibit") and pick(n):
            try:
                s = _publisher_or_fred(n, lambda: _c30(a) if door == "c30" else _exhibit(a) if door == "exhibit"
                                       else _fred_series(door, a))
                _save_cache(n, {str(k): v for k, v in s.items()})
                latest[n] = f"ERR {s.attrs['fallback']}" if s.attrs.get("fallback") else (
                    str(s.index[-1]) if len(s) else None)
            except Exception as e:  # noqa: BLE001
                latest[n] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    bls = {n: a for n, (door, a) in MONTHLY.items() if door == "bls" and pick(n)}
    if bls_too and bls:
        try:
            got = _bls_levels(list(bls.values()))
            for n, a in bls.items():
                s = got[a]
                _save_cache(n, {str(k): v for k, v in s.items()})
                latest[n] = str(s.index[-1]) if len(s) else None
        except Exception as e:  # noqa: BLE001
            for n in bls:
                latest[n] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    for name in INTLTRADE:
        if not pick(name):
            continue
        kind, flow = name.split("_")
        try:
            s = (gold_trade if kind == "gold" else capgoods_trade)(flow, refresh=True)
            latest[name] = str(s.index[-1]) if len(s) else None
        except Exception as e:  # noqa: BLE001
            latest[name] = f"ERR {type(e).__name__}: {str(e)[:80]}"
    _MEM.clear()
    return latest


def monthly(name: str) -> pd.Series:
    """A monthly source from the cache (run refresh() first on a fresh Mac or a release morning)."""
    if name in INTLTRADE:
        kind, flow = name.split("_")
        if name in _MEM:
            return _MEM[name]
        try:
            return (gold_trade if kind == "gold" else capgoods_trade)(flow)
        except OSError:
            # Census's intltrade API down or hanging (2026-11-04: every query timed out). refresh()
            # has already recorded the failure, so the run still exits FAILED; the estimate goes
            # ahead on the last copy on disk rather than dying with the source.
            p = RAW / f"{kind}_{flow}.json"
            if not p.exists():
                raise
            d = json.loads(p.read_text())
            _MEM[name] = pd.Series({pd.Period(k[:7], freq="M"): v for k, v in d.items()},
                                   dtype=float).sort_index()   # one timeout per run, not one per call
            return _MEM[name]
    if name not in MONTHLY:
        raise KeyError(f"unknown monthly source {name!r}; known: {sorted(MONTHLY)}")
    if name not in _MEM:
        d = _load_cache(name)
        if d is None:
            door, a = MONTHLY[name]
            s = _publisher_or_fred(name, {"bea": lambda: _bea_series(a), "census": lambda: _census_series(a),
                                          "bls": lambda: _bls_levels([a])[a],
                                          "fred": lambda: _fred_series("fred", a),
                                          "provider": lambda: _fred_series("provider", a),
                                          "c30": lambda: _c30(a), "exhibit": lambda: _exhibit(a)}[door])
            _save_cache(name, {str(k): v for k, v in s.items()})
            d = {str(k): v for k, v in s.items()}
        _MEM[name] = _to_series(d, "M")
    return _MEM[name]


def quarterly(name: str) -> pd.Series:
    if name not in QUARTERLY:
        raise KeyError(f"unknown quarterly source {name!r}; known: {sorted(QUARTERLY)}")
    if name not in _MEM:
        d = _load_cache(name)
        if d is None:
            s = _bea_series(QUARTERLY[name][1])
            _save_cache(name, {str(k): v for k, v in s.items()})
            d = {str(k): v for k, v in s.items()}
        _MEM[name] = _to_series(d, "Q")
    return _MEM[name]


def retail_control() -> pd.Series:
    """BEA's 'other goods' indicator: retail & food services less autos, gas, building materials
    and food services — the control group, $mn SA."""
    t = monthly("retail_total")
    out = t.copy()
    for n in ("retail_autos", "retail_gas", "retail_building", "retail_food_services"):
        out = out.sub(monthly(n), fill_value=float("nan"))
    return out.dropna()


if __name__ == "__main__":  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-bls", action="store_true")
    a = ap.parse_args()
    if a.refresh:
        for k, v in refresh(bls_too=not a.no_bls).items():
            print(f"{k:32s} {v}")
    else:
        for n in list(MONTHLY)[:6]:
            s = monthly(n)
            print(f"{n:32s} {len(s)} obs {s.index[0]}..{s.index[-1]} latest {s.iloc[-1]:,.1f}")
