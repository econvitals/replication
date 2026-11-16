"""Release calendars: which months of which source a given date could see.

The pseudo-real-time back-test needs, for every past release day, the set of months each
monthly source had published by then. FRED's release schedules (release/dates) carry every
past and scheduled date of each report; the reference month of a monthly report is the month
before its release month (two before for the trade report and the full M3 / inventory books,
which run a month further behind).

    from engine import calendar as cal
    cal.dates("retail")                         # every release date FRED knows, ascending
    cal.month_map("retail")                     # {Period('2026-08','M'): '2026-09-16', ...}
    cal.available_through("retail", "2026-10-18")   # Period('2026-08') — the last month out by then
    cal.releases_on("2026-10-29")               # the reports that print that day
    cal.advance_gdp_date(Period('2026Q3'))      # date of the quarter's advance estimate
    cal.gdp_estimate_dates("2026Q3")            # {"advance": "2026-10-29", "second": ..., "third": ...}

FRED release ids (looked up 2026-10-18): retail 9 (MARTS), m3 95, inventories 25 (manufacturing
and trade), wholesale 290, retail_trade 436, construction 229, starts 27, new_home_sales 97,
trade 51, advance_indicators 435, pce 54, ip 13, cpi 10, ppi 46, trade_prices 188 (import and
export price indexes), qss 288, gdp 53, employment 50.

FRED lists BOTH M3 reports under 95: the advance durable-goods report late in month p (reference
month p-1) and the full report early in month p (reference month p-2). `m3_adv` and `m3_full`
split the one schedule by day of month (DAY_SPLIT); the shutdown winter of 2025-26, when both ran
off their usual days, is the one stretch where the split can misfile a print by a week.

Mapping reference months to release dates (`month_map`) has two sources, best first:
  1. **ALFRED first prints.** For the reports FIRST_PRINT names, FRED's vintage archive says on
     which day each month of a marker series first appeared — the truth, shutdown backlogs and
     cancelled months included (October 2025 CPI never printed; September 2025 retail printed on
     November 25). Months inside the series' initial ALFRED vintage are not first prints and are
     dropped.
  2. **The release schedule**, for months ALFRED does not reach (before its coverage, and the
     scheduled dates still ahead): release month minus the report's lag, a second print of a
     month already mapped skipped (revision days, benchmarks, the M3 full report).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "releases"
FRED = "https://api.stlouisfed.org/fred/release/dates"

RELEASE_IDS = {
    "retail": 9, "m3": 95, "inventories": 25, "wholesale": 290, "retail_trade": 436,
    "construction": 229, "starts": 27, "new_home_sales": 97,
    "trade": 51, "advance_indicators": 435, "pce": 54, "ip": 13, "cpi": 10, "ppi": 46,
    "qss": 288, "gdp": 53, "employment": 50, "trade_prices": 188,
    "m3_adv": 95, "m3_full": 95,
}
#: dates only: a release no estimate of GDP reads, so `releases_on` must not list it
DATES_ONLY_IDS = {"productivity": 47}
#: reports that share a FRED id, told apart by the day of the month they print
DAY_SPLIT = {"m3_adv": lambda day: day >= 15, "m3_full": lambda day: day < 15}
#: report -> a FRED series that first appears in that report (its ALFRED first prints = the map)
FIRST_PRINT = {"retail": "RSAFS", "m3_adv": "DGORDER", "m3_full": "AMTMNO", "inventories": "BUSINV",
               "retail_trade": "RETAILIMSA", "construction": "TTLCONS", "trade": "BOPGSTB",
               "advance_indicators": "AITGCBS", "pce": "PCEC96", "cpi": "CPIAUCSL", "ppi": "PPIFIS",
               "trade_prices": "IR", "employment": "PAYEMS"}
#: months between a report's reference month and its release month, by report
LAG_MONTHS = {"retail": 1, "m3": 1, "m3_adv": 1, "m3_full": 2, "inventories": 2, "wholesale": 2,
              "retail_trade": 2, "construction": 2, "starts": 1, "new_home_sales": 1,
              "trade": 2, "advance_indicators": 1, "pce": 1, "ip": 1, "cpi": 1, "ppi": 1,
              "employment": 1, "trade_prices": 1}
#: the sources (sources.MONTHLY names) each report carries
CARRIES = {
    "retail": ["retail_total", "retail_autos", "retail_gas", "retail_building", "retail_food_services"],
    "m3_adv": ["adv_core_capgoods_shipments", "adv_durable_shipments", "adv_inv_manufacturing"],
    "m3_full": ["core_capgoods_shipments", "durable_shipments", "inv_manufacturing",
                "inv_mfg_durable", "inv_mfg_nondurable"],
    "inventories": ["inv_total_business"],
    "retail_trade": ["inv_retail", "inv_retail_autos", "inv_retail_xauto"],
    "wholesale": ["inv_wholesale", "inv_wholesale_durable", "inv_wholesale_nondurable"],
    "construction": ["construction_private_nonres", "construction_private_res", "construction_private_total",
                     "construction_public", "construction_single_family", "construction_multifamily",
                     "construction_state_local"],
    "employment": ["emp_state", "emp_local", "hours_services"],
    "starts": ["housing_starts"], "new_home_sales": ["new_home_sales"],
    "trade": ["exports_goods_services", "imports_goods_services", "gold_exports", "gold_imports",
              "capgoods_imports", "capgoods_exports", "exports_goods", "imports_goods", "exports_services",
              "imports_services"],
    "advance_indicators": ["adv_exports_goods", "adv_imports_goods", "adv_inv_wholesale", "adv_inv_retail",
                           "adv_inv_retail_autos", "adv_inv_retail_xauto"],
    "pce": ["real_pce", "real_pce_goods", "real_pce_services", "real_pce_durables", "real_pce_nondurables"],
    "cpi": ["cpi_all", "cpi_goods_ex_food_energy", "cpi_food_home", "cpi_gasoline"],
    "ppi": ["ppi_capital_equipment", "ppi_construction_inputs", "ppi_finished_goods", "ppi_finished_core"],
    "trade_prices": ["import_prices", "export_prices", "import_prices_capital"],
}


def _key() -> str | None:
    v = os.environ.get("FRED_API_KEY")
    if v:
        return v
    env = Path(os.environ.get("ECONVITALS_KEYS_FILE") or "keys.env")
    try:
        for ln in env.read_text().splitlines():
            if ln.strip().startswith("FRED_API_KEY="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


def dates(report: str, refresh: bool = False) -> list[str]:
    """Every release date FRED lists for the report, ascending ISO strings; cached a day."""
    rid = {**RELEASE_IDS, **DATES_ONLY_IDS}[report]
    if report in DAY_SPLIT:
        keep = DAY_SPLIT[report]
        return [d for d in dates("m3", refresh) if keep(int(d[8:10]))]
    p = RAW / f"{rid}.json"
    if not refresh and p.exists() and (time.time() - p.stat().st_mtime) < 24 * 3600:
        return json.loads(p.read_text())
    key = _key()
    if not key:
        return json.loads(p.read_text()) if p.exists() else []
    url = (f"{FRED}?release_id={rid}&api_key={key}&file_type=json&include_release_dates_with_no_data=true"
           f"&realtime_start=1990-01-01&realtime_end={dt.date.today().year + 1}-12-31&sort_order=asc&limit=10000")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gdp-nowcast"}), timeout=30) as r:
            got = sorted({x["date"] for x in json.loads(r.read()).get("release_dates", [])})
    except Exception:  # noqa: BLE001
        return json.loads(p.read_text()) if p.exists() else []
    RAW.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(got))
    return got


def first_prints(report: str, refresh: bool = False) -> dict:
    """{reference month: first-print date} from ALFRED for the report's marker series, cached a
    day; {} when the report has no marker or FRED is unreachable with no cache."""
    sid = FIRST_PRINT.get(report)
    if not sid:
        return {}
    p = RAW / f"alfred_{sid}.json"
    if not refresh and p.exists() and (time.time() - p.stat().st_mtime) < 24 * 3600:
        return {pd.Period(k, freq="M"): v for k, v in json.loads(p.read_text()).items()}
    key = _key()
    got = None
    if key:
        url = (f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}"
               f"&file_type=json&realtime_start=1776-07-04&realtime_end=9999-12-31"
               f"&observation_start=1992-01-01&limit=100000")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "gdp-nowcast"}),
                                        timeout=60) as r:
                rows = json.loads(r.read()).get("observations", [])
            first: dict = {}
            for row in rows:
                if row.get("value") in (None, "."):
                    continue
                m = row["date"][:7]
                if m not in first or row["realtime_start"] < first[m]:
                    first[m] = row["realtime_start"]
            if first:
                floor = min(first.values())              # the initial vintage: not first prints,
                initial = [m for m, d in first.items() if d == floor]   # except its newest month
                keep_from = max(initial)
                got = {m: d for m, d in sorted(first.items()) if m >= keep_from}
        except Exception:  # noqa: BLE001
            got = None
    if got is None:
        return {pd.Period(k, freq="M"): v for k, v in json.loads(p.read_text()).items()} if p.exists() else {}
    RAW.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(got))
    return {pd.Period(k, freq="M"): v for k, v in got.items()}


_MM: dict = {}


def month_map(report: str) -> dict:
    """{reference month: release date}, ascending: ALFRED's first prints where they reach, the
    release schedule (release month minus the lag, second prints skipped) before and after."""
    ds = dates(report)
    fp = first_prints(report)
    key = (report, len(ds), ds[-1] if ds else None, len(fp))
    if key in _MM:
        return _MM[key]
    lag = LAG_MONTHS.get(report, 1)
    sched: dict = {}
    last = None
    for d in ds:
        cand = pd.Period(d[:7], freq="M") - lag
        if last is not None and cand <= last:
            continue
        sched[cand] = d
        last = cand
    if fp:
        lo, hi = min(fp), max(fp)
        out = {m: d for m, d in sched.items() if m < lo}
        out.update(fp)
        out.update({m: d for m, d in sched.items() if m > hi and d > fp[hi]})
    else:
        out = sched
    out = dict(sorted(out.items()))
    _MM[key] = out
    return out


def available_through(report: str, asof) -> pd.Period | None:
    """The last reference month of `report` published on or before `asof` (a date or ISO string)."""
    asof = str(asof)[:10]
    out = None
    for m, d in month_map(report).items():      # ascending in both month and date
        if d > asof:
            break
        out = m
    return out


def report_of(source: str) -> str | None:
    """The report that carries a sources.MONTHLY name (None for one no report carries)."""
    for r, names in CARRIES.items():
        if source in names:
            return r
    return None


def releases_on(day) -> list[str]:
    day = str(day)[:10]
    return [r for r in RELEASE_IDS if day in dates(r)]


def gdp_dates() -> list[str]:
    return dates("gdp")


def advance_gdp_date(quarter: pd.Period) -> str | None:
    """The advance estimate's date for a quarter: the first GDP release at least two weeks after
    the quarter ends (the prior quarter's third estimate falls on or before quarter end)."""
    qe = quarter.asfreq("M", "end").to_timestamp(how="end").date()
    floor = (qe + dt.timedelta(days=14)).isoformat()
    for d in gdp_dates():
        if d >= floor:
            return d
    return None


def gdp_estimate_dates(quarter) -> dict:
    """{"advance", "second", "third"}: the dates of a quarter's first three estimates — the first
    three GDP releases on or after the advance estimate's floor (two weeks after the quarter ends).
    Quarters whose releases a shutdown displaced (2018Q4-2019Q1, 2025Q3-Q4) read wrong here."""
    q = pd.Period(quarter, freq="Q")
    qe = q.asfreq("M", "end").to_timestamp(how="end").date()
    floor = (qe + dt.timedelta(days=14)).isoformat()
    return dict(zip(("advance", "second", "third"), [d for d in gdp_dates() if d >= floor][:3]))


def release_days_for(quarter: pd.Period, end: str | None = None) -> list[str]:
    """Every day from the quarter's start until its advance estimate (`end`, default the
    schedule's date; pass the actual one for a quarter BEA delayed) on which a report the engine
    reads prints — the back-test's as-of dates."""
    start = (quarter - 1).asfreq("M", "end").to_timestamp(how="end").date().isoformat()
    end = end or advance_gdp_date(quarter)
    if not end:
        return []
    days = set()
    for r in CARRIES:                       # only the reports that move an input
        days.update(d for d in dates(r) if start < d < end)
    prior = advance_gdp_date(quarter - 1)   # the prior quarter's advance moves the shares and trends
    if prior and start < prior < end:
        days.add(prior)
    return sorted(days)


if __name__ == "__main__":  # pragma: no cover
    import sys
    for r in (sys.argv[1:] or ["retail", "advance_indicators", "trade", "gdp"]):
        ds = dates(r)
        print(f"{r:20s} {len(ds)} dates {ds[0] if ds else ''}..{ds[-1] if ds else ''}; "
              f"through {available_through(r, dt.date.today())} as of today")
