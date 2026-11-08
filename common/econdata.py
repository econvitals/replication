"""Small, dependable readers for the public data the replication scripts start from.

Every function returns plain pandas objects and caches what it downloads for a few hours, so
rerunning a script while you read it does not hit the publisher again.

Keys (all free; set them as environment variables):

    FRED_API_KEY    https://fred.stlouisfed.org/docs/api/api_key.html
    BEA_API_KEY     https://apps.bea.gov/API/signup/
    EIA_API_KEY     https://www.eia.gov/opendata/register.php
    CENSUS_API_KEY  https://api.census.gov/data/key_signup.html   (optional for most calls)

A script only needs the keys for the sources it reads; each folder's README says which.

Most scripts read agency series through FRED, which republishes the Bureau of Labor Statistics',
the Bureau of Economic Analysis' and the Federal Reserve's numbers unchanged. Econvitals itself
reads the agencies directly; the numbers are the same.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("ECONVITALS_CACHE", Path.home() / ".cache" / "econvitals-replication"))
CACHE_HOURS = float(os.environ.get("ECONVITALS_CACHE_HOURS", "6"))
USER_AGENT = os.environ.get("ECONVITALS_USER_AGENT",
                            "econvitals-replication (feedback@econvitals.org)")

# The published data behind every chart on econvitals.org. `published()` reads from here.
PUBLISHED_BASE = os.environ.get(
    "ECONVITALS_PUBLISHED_BASE",
    "https://raw.githubusercontent.com/econvitals/econvitals-data/main/")

KEY_NAMES = ("FRED_API_KEY", "BEA_API_KEY", "EIA_API_KEY", "CENSUS_API_KEY")


# ------------------------------------------------------------------------------ plumbing
def key(name: str) -> str:
    """An API key from the environment, or a clear message about where to get one."""
    _load_keys_file()
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is not set. It is free; see the top of common/econdata.py.")
    return value


_KEYS_LOADED = False


def _load_keys_file() -> None:
    """If ECONVITALS_KEYS_FILE names a KEY=value file, take the four known keys from it.

    Only the names in KEY_NAMES are read; nothing else in that file is touched or exported.
    """
    global _KEYS_LOADED
    if _KEYS_LOADED:
        return
    _KEYS_LOADED = True
    path = os.environ.get("ECONVITALS_KEYS_FILE")
    if not path or not Path(path).expanduser().exists():
        return
    for line in Path(path).expanduser().read_text().splitlines():
        name, _, value = line.strip().partition("=")
        if name in KEY_NAMES and value and not os.environ.get(name):
            os.environ[name] = value.strip().strip('"').strip("'")


def _cache_path(url: str, params: dict | None) -> Path:
    clean = {k: v for k, v in (params or {}).items() if "key" not in k.lower()}
    tag = hashlib.sha1((url + json.dumps(clean, sort_keys=True)).encode()).hexdigest()[:16]
    return CACHE / tag


def get(url: str, params: dict | None = None, *, binary: bool = False, tries: int = 3,
        timeout: int = 60):
    """GET with a cache, a contact User-Agent and a few polite retries."""
    path = _cache_path(url, params)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_HOURS * 3600:
        data = path.read_bytes()
        return data if binary else data.decode("utf-8", "replace")
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers={"User-Agent": USER_AGENT})
            if r.status_code == 200:
                CACHE.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                return r.content if binary else r.text
            last = f"HTTP {r.status_code} from {url}"
            if r.status_code in (400, 401, 403, 404):
                break
        except requests.RequestException as exc:   # network blips: wait and retry
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last or f"could not fetch {url}")


# ------------------------------------------------------------------------------ FRED
def fred(series_id: str, start: str | None = None) -> pd.Series:
    """One FRED series as floats on a DatetimeIndex (missing values dropped)."""
    params = {"series_id": series_id, "api_key": key("FRED_API_KEY"), "file_type": "json"}
    if start:
        params["observation_start"] = start
    obs = json.loads(get("https://api.stlouisfed.org/fred/series/observations", params))
    if "observations" not in obs:
        raise RuntimeError(f"FRED {series_id}: {obs.get('error_message', obs)}")
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs["observations"]},
                  name=series_id)
    return pd.to_numeric(s, errors="coerce").dropna()


def fred_many(series_ids, start: str | None = None) -> pd.DataFrame:
    """Several FRED series side by side, one column each."""
    return pd.concat([fred(s, start) for s in series_ids], axis=1)


# ------------------------------------------------------------------------------ BEA
def bea_nipa(table: str, frequency: str = "M", year: str = "ALL",
             dataset: str = "NIPA") -> pd.DataFrame:
    """A BEA NIPA (or NIUnderlyingDetail) table, long form, from the BEA API.

    Columns: line (int), code (BEA series code), label, date (Timestamp), value (float).
    `table` is BEA's TableName, e.g. "T20804" or "U20404".
    """
    params = {"UserID": key("BEA_API_KEY"), "method": "GetData", "datasetname": dataset,
              "TableName": table, "Frequency": frequency, "Year": year, "ResultFormat": "JSON"}
    raw = json.loads(get("https://apps.bea.gov/api/data", params, timeout=180))
    res = raw.get("BEAAPI", {}).get("Results", {})
    if isinstance(res, list):
        res = res[0]
    rows = res.get("Data")
    if not rows:
        raise RuntimeError(f"BEA {table}: {res.get('Error', raw)}")
    df = pd.DataFrame(rows)

    def when(p: str) -> pd.Timestamp:
        if "M" in p:
            return pd.Timestamp(year=int(p[:4]), month=int(p[5:]), day=1)
        if "Q" in p:
            return pd.Timestamp(year=int(p[:4]), month=3 * int(p[5:]) - 2, day=1)
        return pd.Timestamp(year=int(p[:4]), month=1, day=1)

    out = pd.DataFrame({
        "line": pd.to_numeric(df["LineNumber"]).astype(int),
        "code": df["SeriesCode"],
        "label": df["LineDescription"],
        "date": df["TimePeriod"].map(when),
        "value": pd.to_numeric(df["DataValue"].str.replace(",", ""), errors="coerce"),
    })
    return out.dropna(subset=["value"])


def bea_wide(table: str, frequency: str = "M", year: str = "ALL", by: str = "line",
             dataset: str = "NIPA") -> pd.DataFrame:
    """The same table, one column per line number (or per series code with by="code")."""
    long = bea_nipa(table, frequency, year, dataset)
    return long.pivot_table(index="date", columns=by, values="value", aggfunc="first")


# ------------------------------------------------------------------------------ BLS
def bls_flat(survey: str, filename: str) -> pd.DataFrame:
    """A file from BLS's public bulk download (download.bls.gov/pub/time.series/<survey>/).

    No key and no daily quota. BLS asks that scripts identify themselves, which `get` does.
    """
    text = get(f"https://download.bls.gov/pub/time.series/{survey}/{filename}", timeout=300)
    df = pd.read_csv(io.StringIO(text), sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda c: c.str.strip() if c.dtype == object else c)


def bls_series(survey: str, data_file: str, series_ids) -> pd.DataFrame:
    """Monthly values for the named series from a BLS bulk data file, one column each."""
    df = bls_flat(survey, data_file)
    df = df[df["series_id"].isin(set(series_ids)) & df["period"].str.match(r"M(0[1-9]|1[0-2])")]
    df = df.assign(date=pd.to_datetime(df["year"] + "-" + df["period"].str[1:] + "-01"),
                   value=pd.to_numeric(df["value"], errors="coerce"))
    return df.pivot_table(index="date", columns="series_id", values="value", aggfunc="first")


# ------------------------------------------------------------------------------ EIA
def eia(route: str, params: dict) -> pd.DataFrame:
    """EIA open-data API v2: `route` like "petroleum/pri/gnd/data", `params` as EIA documents."""
    p = dict(params)
    p["api_key"] = key("EIA_API_KEY")
    raw = json.loads(get(f"https://api.eia.gov/v2/{route}", p))
    return pd.DataFrame(raw.get("response", {}).get("data", []))


# ------------------------------------------------------------------------------ Econvitals
def published(path: str) -> dict:
    """A published Econvitals data file (e.g. "data/underlying-inflation-pce.json")."""
    local = os.environ.get("ECONVITALS_PUBLISHED_DIR")
    if local and (Path(local) / path).exists():
        return json.loads((Path(local) / path).read_text())
    return json.loads(get(PUBLISHED_BASE + path))


def published_frame(path: str) -> pd.DataFrame:
    """A published chart's data as a DataFrame indexed by date."""
    d = published(path)
    df = pd.DataFrame(d["data"])
    col = d.get("date_col") or "date"
    df[col] = pd.to_datetime(df[col])
    return df.set_index(col)


def save(df, folder: str | Path, name: str) -> Path:
    """Write a result to <folder>/output/<name>.csv and return the path."""
    out = Path(folder) / "output"
    out.mkdir(exist_ok=True)
    path = out / f"{name}.csv"
    frame = df.to_frame() if isinstance(df, pd.Series) else df
    if isinstance(frame.index, pd.DatetimeIndex):
        name = frame.index.name or "date"
        frame = frame.copy()
        frame.index = frame.index.strftime("%Y-%m-%d")
        frame.index.name = name
    frame.to_csv(path, float_format="%.6f")
    return path
