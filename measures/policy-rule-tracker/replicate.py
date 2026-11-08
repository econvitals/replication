"""Policy-Rule Tracker — rebuilds the meeting-by-meeting dataset behind the Taylor Rule tool
(econvitals.org/tools/taylor-rule/) and the featured rule's reading at every FOMC decision.

    python replicate.py        # needs FRED_API_KEY

For every FOMC decision since 1960 (scheduled meetings, plus any call or unscheduled meeting that
moved the target), the inputs are the latest unemployment month, inflation month and GDP quarter
that had been PUBLISHED by decision day, using ALFRED's first-release dates where its record
reaches and FRED's release calendar before that; the values themselves are today's vintage.

The slack input is the house hybrid: CBO's output gap for the latest quarter with a GDP estimate,
moved by Okun's law (coefficient 2) as unemployment changes from that quarter's average to the
latest month. The featured rule is the Fed's inertial rule: the balanced-approach rule
    r* + inflation + 0.5 x (inflation - 2) + 1.0 x gap
on core PCE inflation, the Laubach-Williams r* and the hybrid gap, with 0.85 a quarter on the rate
going in (0.85 ^ (days since the last meeting / 91.31)).

Writes output/meetings.csv and, for the nightly comparison, output/site_meetings.csv (the published
inputs, with the rule worked out from them by the page's own arithmetic).
"""
import datetime as dt
import json
import re
import sys
from bisect import bisect_right
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, get, key, save  # noqa: E402
from common.rates import ny_fed_rstar, published_anywhere  # noqa: E402

FRED_API = "https://api.stlouisfed.org/fred"
OKUN, TARGET, RHO, A_INFL, B_GAP = 2.0, 2.0, 0.85, 0.5, 1.0   # the featured rule


def r3(x):
    return None if x is None or pd.isna(x) else round(float(x), 3)


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def quarter_key(d):
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def period_end(k):
    p = pd.Period(k, freq="Q" if "Q" in k else "M")
    return p.end_time.date()


def latest_le(keys, k):
    i = bisect_right(keys, k) - 1
    return keys[i] if i >= 0 else None


# ---------------------------------------------------------------- the data, today's vintage
def monthly(sid, start="1947-01-01"):
    return {month_key(d): v for d, v in fred(sid, start).items()}


def twelve_month(index):
    """12-month percent change of a monthly index. October 2025 was never collected (the
    shutdown), so a year-ago October 2025 is the geometric average of September and November."""
    out = {}
    for k, v in index.items():
        base_k = f"{int(k[:4]) - 1:04d}{k[4:]}"
        base = index.get(base_k)
        if base is None and base_k == "2025-10" and "2025-09" in index and "2025-11" in index:
            base = (index["2025-09"] * index["2025-11"]) ** 0.5
        if base:
            out[k] = 100 * (v / base - 1)
    return out


u = monthly("UNRATE")                                    # BLS, unemployment rate (LNS14000000)
infl = {"core_pce": twelve_month(monthly("PCEPILFE")),   # BEA, PCE price index ex food and energy
        "pce": twelve_month(monthly("PCEPI")),
        "core_cpi": twelve_month(monthly("CPILFESL")),   # BLS, CPI-U ex food and energy, SA
        "cpi": twelve_month(monthly("CPIAUCSL"))}
gdp, pot = fred("GDPC1"), fred("GDPPOT")                 # BEA real GDP; CBO potential GDP
gap = {quarter_key(d): 100 * (gdp[d] / pot[d] - 1) for d in gdp.index if d in pot.index}
u_q = {}
for k, v in u.items():
    u_q.setdefault(quarter_key(pd.Timestamp(k + "-01")), []).append(v)
u_q = {q: sum(v) / len(v) for q, v in u_q.items() if len(v) >= 2}   # Oct 2025 never published
nrou = {quarter_key(d): v for d, v in fred("NROU").items()}           # CBO natural rate
rstar = {m: {quarter_key(d): v for d, v in ny_fed_rstar(m.upper()).items()} for m in ("lw", "hlw")}
ff = monthly("FEDFUNDS", "1954-01-01")                   # effective federal funds rate, monthly
# The target: a single rate from September 1982, the midpoint of the range from December 2008.
mid = dict(fred("DFEDTAR").items())
lo = fred("DFEDTARL")
for d, v in fred("DFEDTARU").items():
    if d in lo.index:
        mid[d] = (v + lo[d]) / 2
mid_days = sorted(mid)


def mid_at(d):
    i = bisect_right(mid_days, pd.Timestamp(d)) - 1
    return mid[mid_days[i]] if i >= 0 else None


# ---------------------------------------------------------------- when each period was out
def first_release(sid):
    """{period: the day the observation first appeared}, from ALFRED."""
    obs = json.loads(get(f"{FRED_API}/series/observations",
                         {"series_id": sid, "api_key": key("FRED_API_KEY"), "file_type": "json",
                          "output_type": 4, "realtime_start": "1776-07-04",
                          "realtime_end": "9999-12-31", "limit": 100000}))["observations"]
    to_key = quarter_key if sid == "GDPC1" else month_key
    return {to_key(pd.Timestamp(o["date"])): dt.date.fromisoformat(o["realtime_start"]) for o in obs}


def release_calendar(release_id):
    d = json.loads(get(f"{FRED_API}/release/dates",
                       {"release_id": release_id, "api_key": key("FRED_API_KEY"),
                        "file_type": "json", "include_release_dates_with_no_data": "true",
                        "sort_order": "asc", "limit": 5000}))
    return sorted({dt.date.fromisoformat(x["date"]) for x in d["release_dates"]})


def available(periods, first, calendar, rule_days):
    """[(period, the day it was available)]: ALFRED's first-release date when it is plausible
    (within 150 days of the period's end); else the release calendar's first date after the
    period ends; else a fixed publication lag."""
    out = {}
    window = dt.timedelta(days=150)
    for k in periods:
        end = period_end(k)
        fr = first.get(k)
        if fr and end < fr <= end + window:
            out[k] = fr
            continue
        if calendar and calendar[0] <= end + window:
            i = bisect_right(calendar, end)
            if i < len(calendar) and calendar[i] <= end + window:
                out[k] = calendar[i]
                continue
        out[k] = end + dt.timedelta(days=rule_days)
    return sorted(out.items())


def latest_out(avail, day):
    """The newest period out on or before `day` (an 8:30 release counts for a 2pm decision)."""
    for k, a in reversed(avail):
        if a <= day:
            return k
    return None


pce_months = sorted(set(infl["core_pce"]) | set(infl["pce"]))
cpi_months = sorted(set(infl["core_cpi"]) | set(infl["cpi"]))
avail = {
    "u": available(sorted(u), first_release("UNRATE"), release_calendar(50), 7),       # Employment Situation
    "pce": available(pce_months, first_release("PCEPILFE"), release_calendar(54), 28),  # Personal Income and Outlays
    "cpi": available(cpi_months, first_release("CPILFESL"), release_calendar(10), 15),  # CPI
    "gdp": available(sorted(gap), first_release("GDPC1"), release_calendar(53), 30),   # GDP
}
infl_keys = {k: sorted(v) for k, v in infl.items()}
nrou_keys, rstar_keys = sorted(nrou), {m: sorted(v) for m, v in rstar.items()}


# ---------------------------------------------------------------- the FOMC's decisions
def fed_calendar():
    """Meetings on the Federal Reserve's current calendar page (2021 on)."""
    months = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
    html = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    out = []
    blocks = re.split(r"(\d{4}) FOMC Meetings", html)
    for i in range(1, len(blocks) - 1, 2):
        year, body = int(blocks[i]), blocks[i + 1]
        mos = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"fomc-meeting__month[^>]*>(.*?)</div>", body, re.S)]
        das = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"fomc-meeting__date[^>]*>(.*?)</div>", body, re.S)]
        for mo, da in zip(mos, das):
            tag = " ".join(re.findall(r"\(([^)]*)\)", da + " " + mo)).lower()
            if "cancel" in tag or "notation" in tag:
                continue
            nums = [int(x) for x in re.findall(r"\d+", re.sub(r"\([^)]*\)", "", da))]
            ms = [months.get(x[:3].lower()) for x in re.split(r"[/\s]+", mo) if x]
            ms = [x for x in ms if x]
            if not nums or not ms:
                continue
            m, d = (ms[-1], nums[1]) if len(nums) >= 2 else (ms[0], nums[0])  # dated by the decision day
            kind = "unscheduled" if "unscheduled" in tag else ("call" if "conference call" in tag else "scheduled")
            out.append({"date": dt.date(year, m, d).isoformat(), "kind": kind})
    return out


history = pd.read_csv(HERE / "inputs" / "fomc_meetings_1960_2020.csv", dtype=str).to_dict("records")
meetings = sorted({m["date"]: m for m in history + fed_calendar()}.values(), key=lambda m: m["date"])


def inputs_at(day):
    """What the rule sees at a decision on `day`."""
    row = {}
    uk = latest_out(avail["u"], day)
    row["u_month"], row["u"] = uk, r3(u.get(uk))
    for name, rel in (("core_pce", "pce"), ("pce", "pce"), ("core_cpi", "cpi"), ("cpi", "cpi")):
        mk = latest_out(avail[rel], day)
        k = latest_le(infl_keys[name], mk) if mk else None
        ok = k and (int(k[:4]) * 12 + int(k[5:])) >= (int(mk[:4]) * 12 + int(mk[5:]) - 6)
        row[name] = r3(infl[name][k]) if ok else None
    gk = latest_out(avail["gdp"], day)
    row["gap_quarter"] = gk
    row["output_gap"] = r3(gap.get(gk)) if gk in gap else None
    row["u_quarter_avg"] = r3(u_q.get(gk)) if gk in gap else None
    if uk:
        k = latest_le(nrou_keys, quarter_key(pd.Timestamp(uk + "-01")))
        row["ustar_cbo"] = r3(nrou[k]) if k else None
    # r*: the latest quarter the New York Fed would have posted (about 60 days after it ends)
    q = pd.Period(day, freq="Q")
    while q.end_time.date() + dt.timedelta(days=60) > day:
        q -= 1
    for m in ("lw", "hlw"):
        k = latest_le(rstar_keys[m], str(q))
        row[f"rstar_{m}"] = r3(rstar[m][k]) if k and k >= str(q - 4) else None
    # the rate going in (the day before) and coming out (three days after)
    before, after = mid_at(day - dt.timedelta(days=1)), mid_at(day + dt.timedelta(days=3))
    if before is not None and mid_days[0].date() <= day - dt.timedelta(days=1):
        row["rate_before"], row["rate_after"], row["basis"] = r3(before), r3(after), "target"
    else:
        pm, nm = pd.Period(day, freq="M") - 1, pd.Period(day, freq="M") + 1
        row["rate_before"], row["rate_after"] = r3(ff.get(str(pm))), r3(ff.get(str(nm)))
        row["basis"] = "effective"
    return row


def target_moved(day):
    """The first day in [day, day + 2] on which the target differs from the day before."""
    base = mid_at(day - dt.timedelta(days=1))
    if base is None:
        return None
    for k in range(3):
        v = mid_at(day + dt.timedelta(days=k))
        if v is not None and abs(v - base) >= 0.01:
            return day + dt.timedelta(days=k)
    return None


today = dt.date.today()
rows, by_move = [], {}
for m in meetings:
    day = dt.date.fromisoformat(m["date"])
    if day > today:
        continue
    row = {"date": m["date"], "kind": m["kind"], **inputs_at(day)}
    if m["kind"] != "scheduled":
        # A call or unscheduled meeting counts only if it moved the target within two days; several
        # calls around one move collapse to the last of them.
        moved = target_moved(day)
        if row["basis"] != "target" or moved is None:
            continue
        row["kind"] = "intermeeting"
        by_move[moved] = row
    rows.append(row)
rows = [r for r in rows if r["kind"] != "intermeeting" or r in by_move.values()]


# ---------------------------------------------------------------- the featured rule
def featured_rule(rows):
    """The hybrid gap, the balanced-approach rule before smoothing, and the inertial rule, for
    each meeting in order, from the (rounded) inputs, as the page computes them."""
    prev = None
    for r in rows:
        days = (pd.Timestamp(r["date"]) - pd.Timestamp(prev)).days if prev else 91
        prev = r["date"]
        g = None
        if None not in (r.get("output_gap"), r.get("u"), r.get("u_quarter_avg")):
            g = r["output_gap"] - OKUN * (r["u"] - r["u_quarter_avg"])
        r["hybrid_gap"] = g
        pi, rs, lag = r.get("core_pce"), r.get("rstar_lw"), r.get("rate_before")
        if None in (pi, g, rs):
            r["rule_before_smoothing"] = r["rule"] = None
            continue
        star = rs + pi + A_INFL * (pi - TARGET) + B_GAP * g
        rho = RHO ** (min(max(days, 20), 183) / 91.31) if lag is not None else 0.0
        r["rule_before_smoothing"] = star
        r["rule"] = rho * (lag or 0) + (1 - rho) * star
    return rows


out = pd.DataFrame(featured_rule(rows)).set_index("date")
save(out, HERE, "meetings")

# The published meetings, flat, with the rule worked out from the published inputs.
site = published_anywhere("tools/taylor-rule/data.json")
flat = []
for m in site["meetings"]:
    og = m.get("og") or {}
    flat.append({"date": m["date"], "kind": m["kind"], "u": (m.get("u") or {}).get("v"),
                 **{k: (m["infl"].get(k) or {}).get("v") for k in ("core_pce", "pce", "core_cpi", "cpi")},
                 "output_gap": og.get("v"), "u_quarter_avg": og.get("u_q"),
                 "ustar_cbo": (m.get("ustar") or {}).get("cbo"),
                 "rstar_lw": (m["rstar"].get("lw") or {}).get("v"),
                 "rstar_hlw": (m["rstar"].get("hlw") or {}).get("v"),
                 "rate_before": m.get("rate_before"), "rate_after": m.get("rate_after")})
save(pd.DataFrame(featured_rule(flat)).set_index("date"), HERE, "site_meetings")

print(out[["kind", "u", "core_pce", "output_gap", "hybrid_gap", "rstar_lw", "rate_before",
           "rule"]].tail(6).round(3).to_string())
