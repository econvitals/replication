"""Policy-Cycle Phase — rebuilds the Cycle Phase column of the Global Central Bank Stance Matrix
(econvitals.org/tools/central-bank-stance/) and of the policy-rate table on International › Global.

    python replicate.py        # needs FRED_API_KEY (for the Fed's target range); the rest is keyless

Writes output/stance.csv (each bank today) and output/stance_check.csv (each bank as of the moment
the published matrix was built, for the nightly comparison), plus output/site_stance.csv (what the
published matrix says, laid out flat).

The rule, for each of twelve central banks:
  * the policy rate is the BIS daily series, topped up with each bank's own same-day feed where
    one exists (the Fed, the ECB, the Bank of England and the Bank of Canada), but only after the
    feed agrees with the BIS on the BIS's own last date;
  * the last move is the most recent day the rate changed;
  * a move in the last 6 months makes the bank Hiking or Cutting; a last move 6 to 12 months old
    makes it On Hold; older than a year, Paused (a month is 30.44 days).
"""
import io
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, get, save  # noqa: E402
from common.rates import bis_policy_rate, published_anywhere  # noqa: E402

BANKS = {"US": "Federal Reserve", "XM": "European Central Bank", "JP": "Bank of Japan",
         "GB": "Bank of England", "CA": "Bank of Canada", "AU": "Reserve Bank of Australia",
         "CH": "Swiss National Bank", "SE": "Sveriges Riksbank", "NO": "Norges Bank",
         "NZ": "Reserve Bank of New Zealand", "CN": "People's Bank of China",
         "IN": "Reserve Bank of India"}
LOOKBACK_MONTHS = 6
AGREE = 0.011          # a feed must match the BIS this closely on the BIS's last date
# Phases as numbers, so the nightly check can compare them exactly.
PHASE_CODE = {"Hiking": 1, "Cutting": 2, "On Hold": 3, "Paused": 4}


# ---------------------------------------------------------------- each bank's own same-day feed
def fed_feed(start):
    """The midpoint of the federal funds target range (the BIS's U.S. number)."""
    hi, lo = fred("DFEDTARU", start), fred("DFEDTARL", start)
    return ((hi + lo) / 2).dropna()


def ecb_feed(start):
    """The ECB's deposit facility rate (the BIS's euro-area number)."""
    url = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV"
    df = pd.read_csv(io.StringIO(get(url, {"format": "csvdata", "startPeriod": start})))
    return pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"])).dropna()


def boe_feed(start):
    """Bank Rate, from the Bank of England's statistical database."""
    frm = pd.Timestamp(start).strftime("%d/%b/%Y")
    to = pd.Timestamp.today().strftime("%d/%b/%Y")
    url = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    params = {"csv.x": "yes", "Datefrom": frm, "Dateto": to, "SeriesCodes": "IUDBEDR",
              "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N"}
    df = pd.read_csv(io.StringIO(get(url, params)))
    return pd.Series(pd.to_numeric(df["IUDBEDR"], errors="coerce").values,
                     index=pd.to_datetime(df["DATE"], format="%d %b %Y")).dropna()


def boc_feed(start):
    """The Bank of Canada's target for the overnight rate (Valet series V39079)."""
    import json
    obs = json.loads(get("https://www.bankofcanada.ca/valet/observations/V39079/json",
                         {"start_date": start}))["observations"]
    return pd.Series({pd.Timestamp(o["d"]): float(o["V39079"]["v"]) for o in obs
                      if (o.get("V39079") or {}).get("v") not in (None, "")})


FEEDS = {"US": fed_feed, "XM": ecb_feed, "GB": boe_feed, "CA": boc_feed}


def policy_rate(code):
    """(daily series, where its last observation came from)."""
    s = bis_policy_rate(code)
    feed = FEEDS.get(code)
    if not feed:
        return s, "BIS"
    start = min(pd.Timestamp.today().normalize() - pd.DateOffset(days=120), s.index[-1])
    start = start.strftime("%Y-%m-%d")
    try:
        f = feed(start).sort_index()
    except Exception as exc:  # noqa: BLE001 — a feed that is down leaves the BIS series
        print(f"  {code}: own feed unavailable ({exc}); BIS only")
        return s, "BIS"
    on_bis_day = f[f.index <= s.index[-1]]
    if on_bis_day.empty or abs(on_bis_day.iloc[-1] - s.iloc[-1]) > AGREE:
        print(f"  {code}: own feed disagrees with the BIS on {s.index[-1].date()}; BIS only")
        return s, "BIS"
    newer = f[f.index > s.index[-1]]
    return pd.concat([s, newer]), ("own feed" if len(newer) else "BIS")


# ---------------------------------------------------------------- the rule
def stance(s, today):
    """Rate, last move, phase and year-to-date change for one bank, as of `today`."""
    s = s[s.index <= today]
    changes = s[s.diff().fillna(0) != 0]
    out = {"rate": s.iloc[-1], "as_of": s.index[-1].date()}
    if changes.empty:
        out.update(last_move_date=None, last_move_bps=None, phase="Paused")
    else:
        when = changes.index[-1]
        bps = round((s.loc[when] - s[s.index < when].iloc[-1]) * 100)
        age_months = (today - when).days / 30.44
        if age_months <= LOOKBACK_MONTHS:
            phase = "Cutting" if bps < 0 else "Hiking"
        elif age_months <= 12:
            phase = "On Hold"
        else:
            phase = "Paused"
        out.update(last_move_date=when.date(), last_move_bps=bps, phase=phase)
    jan1 = s[s.index <= pd.Timestamp(today.year, 1, 1)]
    out["ytd_bps"] = round((out["rate"] - jan1.iloc[-1]) * 100) if len(jan1) else None
    out["phase_code"] = PHASE_CODE[out["phase"]]
    return out


def as_number(d):
    """A date as an 8-digit number (2026-09-17 -> 20260917), so it can be compared exactly."""
    return None if d is None else int(pd.Timestamp(d).strftime("%Y%m%d"))


series, source = {}, {}
for code in BANKS:
    series[code], source[code] = policy_rate(code)

# 1. Each bank today.
today = pd.Timestamp.today().normalize()
rows = []
for code, name in BANKS.items():
    st = stance(series[code], today)
    rows.append({"code": code, "bank": name, **st, "source": source[code]})
live = pd.DataFrame(rows).set_index("code")
save(live, HERE, "stance")

# 2. The same rule run on the published matrix's own cut-offs: each bank's rate as of the date the
#    published row is current through, and the phase as of the day the matrix was built. A bank is
#    left blank when the site saw something this script cannot: a published move dated after this
#    script's last observation, or a series here that ends more than 30 days before the published
#    row (the matrix reads the Reserve Bank of India's own web pages when the BIS relay stalls).
site = published_anywhere("tools/central-bank-stance/data.json")
built = pd.Timestamp(site["meta"]["generated_at"][:10])
check, flat = [], []
for b in site["banks"]:
    code = b["code"]
    if code not in series:
        continue
    cut = min(pd.Timestamp(b["as_of"]), built)
    st = stance(series[code][series[code].index <= cut], built)
    last_seen = series[code].index[-1]
    site_move = pd.Timestamp((b.get("last_move") or {}).get("date") or "1900-01-01")
    if (cut - last_seen).days > 30 or site_move > last_seen:
        st = {k: None for k in st}
    check.append({"code": code, "rate": st["rate"], "ytd_bps": st["ytd_bps"],
                  "phase_code": st["phase_code"], "last_move_bps": st["last_move_bps"],
                  "last_move_date": as_number(st["last_move_date"])})
    mv = b.get("last_move") or {}
    flat.append({"code": code, "rate": b.get("rate"), "ytd_bps": b.get("ytd_bps"),
                 # a phase set by hand in the matrix's config is not the rule's, so it is not compared
                 "phase_code": PHASE_CODE.get(b.get("phase")) if b.get("phase_source") == "auto" else None,
                 "last_move_bps": mv.get("delta_bps"), "last_move_date": as_number(mv.get("date"))})
save(pd.DataFrame(check).set_index("code"), HERE, "stance_check")
save(pd.DataFrame(flat).set_index("code"), HERE, "site_stance")

print(live[["rate", "as_of", "last_move_date", "last_move_bps", "phase", "ytd_bps", "source"]]
      .to_string())
