"""The Census Bureau's Economic Indicators Time Series (EITS) API, one call for every dataset.

    from engine import eits
    eits.series("marts", "44X72", "SM")            # retail & food services sales, SA, $mn, monthly
    eits.series("vip", "ANRXX", "V")               # private nonresidential construction spending, SAAR $mn
    eits.series("mwtsadv", "42", "IM")             # ADVANCE wholesale inventories, SA, $mn
    eits.series("qss", "5112T", "QREV", freq="Q")  # software publishers' revenue, quarterly

Returns {pd.Period: float} (monthly or quarterly periods), seasonally adjusted unless
``sa="no"``. Cached on disk per (dataset, category, data type, sa) for CACHE_HOURS; a refresh
re-reads the whole history in one request (the API serves ``time=from YYYY`` in one page).

CODES VERIFIED 2026-10-18 against FRED / Census published values for June 2026:
  vip    A00XX/V  = private RESIDENTIAL spending (FRED PRRESCONS 882,120) — NOT total construction;
         ANRXX/V  = private nonresidential (PNRESCONS 758,852); AXXXX/V = total private (TLPRVCONS);
         the ``A`` prefix = seasonally adjusted annual rate; ``XXXX`` = total incl. public (not SA)
  mrts   44000/IM = retail inventories (RETAILIMSA 872,415); 4400A = retail ex motor vehicles; 441 = autos
  mwts   42/IM    = merchant wholesalers' inventories (WHLSLRIMSA 946,687); 423 durable, 424 nondurable
  mtis   TOTBUS/MNFCTR/WHLSLR/RETAIL IM = total business and the three books (BUSINV 2,782,459)
  mwtsadv, mrtsadv  the ADVANCE inventory reports (IM, MPCIM), month 3 of a quarter two days before GDP
  ftdadv CBG EXP/IMP/BAL = the advance goods trade report, Census basis, SA $mn
  marts  44X72/SM = retail & food services (RSAFS); 44W72 ex autos & gas; 44Y72 ex autos; 441 autos;
         447 gas stations; 444 building materials; 722 food services (the control group = 44X72 less
         441, 447, 444, 722)
  m3 / advm3  NXA/VS nondefense capital goods ex aircraft shipments; MDM durable total; TI inventories;
         NO new orders (advm3 = the advance report, a week ahead of the full m3)
  resconst ASTARTS/TOTAL starts (SAAR thousands); APERMITS; ACOMPLETIONS
  ressales ASOLD/TOTAL new-home sales (SAAR thousands); MEDIAN median price (not SA)
  qss    quarterly, time=YYYY-Qn, categories are NAICS + 'T' (e.g. 5112T software publishers,
         5415T computer systems design, 622T hospitals), data types QREV revenue, QEXP expenses
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

API = "https://api.census.gov/data/timeseries/eits"
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "eits"
CACHE_HOURS = float(os.environ.get("GDP_NOWCAST_EITS_CACHE_HOURS", "6"))
START_YEAR = 1992


def api_key() -> str:
    v = os.environ.get("CENSUS_API_KEY")
    if v:
        return v
    env = Path(os.environ.get("ECONVITALS_KEYS_FILE") or "keys.env")
    try:
        for ln in env.read_text().splitlines():
            if ln.strip().startswith("CENSUS_API_KEY="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    raise RuntimeError("no CENSUS_API_KEY in the environment (free: https://api.census.gov/data/key_signup.html)")


def _period(label: str, freq: str) -> pd.Period | None:
    try:
        if freq == "Q":
            y, q = label.split("-Q")
            return pd.Period(f"{y}Q{q}", freq="Q")
        return pd.Period(label[:7], freq="M")
    except Exception:  # noqa: BLE001
        return None


def _fetch_all(dataset: str, freq: str) -> list[dict]:
    """Every row of a dataset from START_YEAR: one request (the API pages the whole history)."""
    q = urllib.parse.urlencode({
        "get": "cell_value,data_type_code,category_code,seasonally_adj,time_slot_id",
        "for": "us:1", "time": f"from {START_YEAR}", "key": api_key()})
    url = f"{API}/{dataset}?{q}"
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                raw = r.read()
            if not raw.strip():
                return []
            rows = json.loads(raw)
            head = rows[0]
            return [dict(zip(head, r)) for r in rows[1:]]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"eits {dataset}: {last!r}")


def _cache_file(dataset: str) -> Path:
    return CACHE / f"{dataset}.json"


def dataset_rows(dataset: str, freq: str = "M", refresh: bool = False) -> list[dict]:
    """All rows of a dataset, from the disk cache when it is younger than CACHE_HOURS."""
    p = _cache_file(dataset)
    if not refresh and p.exists() and (time.time() - p.stat().st_mtime) < CACHE_HOURS * 3600:
        return json.loads(p.read_text())
    rows = _fetch_all(dataset, freq)
    if rows:
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rows))
    elif p.exists():
        return json.loads(p.read_text())
    return rows


def series(dataset: str, category: str, data_type: str, sa: str = "yes", freq: str = "M",
           refresh: bool = False) -> dict:
    """{Period: value} for one (category, data type) of a dataset, seasonally adjusted by default."""
    out = {}
    for r in dataset_rows(dataset, freq, refresh):
        if r.get("category_code") != category or r.get("data_type_code") != data_type:
            continue
        if (r.get("seasonally_adj") or "").lower() != sa:
            continue
        p = _period(r.get("time", ""), freq)
        v = r.get("cell_value")
        if p is None or v in (None, "", "(NA)", "(S)", "(X)"):
            continue
        try:
            out[p] = float(v)
        except (TypeError, ValueError):
            continue
    return dict(sorted(out.items()))


def latest_period(dataset: str, category: str, data_type: str, sa: str = "yes", freq: str = "M") -> pd.Period | None:
    s = series(dataset, category, data_type, sa, freq)
    return max(s) if s else None


if __name__ == "__main__":  # pragma: no cover
    import sys
    ds, cat, dtp = (sys.argv[1:4] + ["marts", "44X72", "SM"])[:3] if len(sys.argv) > 3 else ("marts", "44X72", "SM")
    s = series(ds, cat, dtp)
    items = list(s.items())
    print(f"{ds} {cat}/{dtp}: {len(items)} months {items[0][0]}..{items[-1][0]}  latest {items[-1][1]:,.0f}")
