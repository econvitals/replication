"""Market-Implied Expectations — rebuilds the Kalshi “market expects” numbers on econvitals.org
(What Forecasters Expect, the GDP pages, Financial › Prediction Markets).

    python replicate.py        # keyless: Kalshi's public market data needs no account

Kalshi lists each economic release as a ladder of yes/no markets (“real GDP above 2.5%”, “above
3.0%” …) or as a set of ranges. The prices across the ladder are a probability distribution over
the print; the number Econvitals shows is its mean. This script:

  1. reads today's order books and prints the market's expected print for the next GDP quarter,
     this year's GDP, the next CPI and core CPI, the unemployment rate and payrolls
     (output/expected.csv, output/distribution.csv, output/path_<id>.csv);
  2. rebuilds, from Kalshi's daily candles, the daily history behind each card on the published
     site (output/check_history.csv), and lays the published history beside it
     (output/site_history.csv).
     Today's order book cannot be re-read tomorrow, but a day's closing candle can, so the nightly
     check compares every closed day.

ECONVITALS_CACHE_HOURS=0 python replicate.py forces a fresh read of the order books.
"""
import datetime as dt
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import save  # noqa: E402
from common.rates import kalshi, published_anywhere  # noqa: E402

ET = ZoneInfo("America/New_York")
# id, Kalshi series, the print's rounding (Kalshi settles on a print rounded to this), the scale
# the page shows it in (payrolls: thousands of jobs), and whether it is a calendar-year market.
SPECS = [
    {"id": "gdp_q", "series": "KXGDP", "res": 0.1, "scale": 1, "label": "Real GDP growth, next quarter (%)"},
    {"id": "gdp_year", "series": "KXGDPYEAR", "res": 0.1, "scale": 1, "year": True, "label": "Real GDP growth, this year (%)"},
    {"id": "cpi", "series": "KXCPI", "res": 0.1, "scale": 1, "label": "CPI, monthly change (%)"},
    {"id": "core_cpi", "series": "KXCPICORE", "res": 0.1, "scale": 1, "label": "Core CPI, monthly change (%)"},
    {"id": "unemployment", "series": "KXU3", "res": 0.1, "scale": 1, "label": "Unemployment rate (%)"},
    {"id": "payrolls", "series": "KXPAYROLLS", "res": 1000, "scale": 1000, "label": "Payrolls, monthly change (thousands)"},
]
TIGHT = 0.10          # a book this tight (in dollars) is priced at its midpoint, else at its last trade
CORE = (0.10, 0.90)   # a ladder needs a tight book somewhere in this range to count as a view
STALE_DAYS = 7        # in the daily history, a rung's last firm price is carried this long
CROSSED = 0.15        # a ladder out of order by more than this is not a distribution at all


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- pricing one ladder
def price(bid, ask, last):
    """Midpoint of bid and ask when the book is within 10 cents (or there is no usable last
    trade); otherwise the last trade."""
    if bid is not None and ask is not None and ask >= bid and ask > 0:
        if ask - bid <= TIGHT or last is None or not (0 < last < 1):
            return (bid + ask) / 2
    return last


def rung(m, p=None, bid=None, ask=None):
    """One market as a rung of the ladder: its type (greater / between / less), strikes, price."""
    if m.get("strike_type") not in ("greater", "between", "less"):
        return None
    if p is None:
        bid, ask = num(m.get("yes_bid_dollars")), num(m.get("yes_ask_dollars"))
        p = price(bid, ask, num(m.get("last_price_dollars")))
    if p is None:
        return None
    return {"ticker": m["ticker"], "type": m["strike_type"], "floor": num(m.get("floor_strike")),
            "cap": num(m.get("cap_strike")), "p": min(1.0, max(0.0, p)), "bid": bid, "ask": ask}


def pool_decreasing(ps):
    """The closest non-increasing sequence (pool adjacent violators): an out-of-order ladder
    would otherwise put negative probability between two rungs."""
    blocks = []
    for p in ps:
        blocks.append([p, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] < blocks[-1][0] / blocks[-1][1]:
            s, n = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += n
    return [s / n for s, n in blocks for _ in range(n)]


def distribution(rungs, res):
    """(mean, [(print, probability)]) from priced rungs, or None.

    A "greater" ladder: P(print > strike) at each strike. The probability between two strikes is
    placed at the midpoint of the prints it covers — Kalshi pays on a print strictly above the
    strike, rounded to `res`, so "above 2.0%" less "above 2.5%" covers 2.1 ... 2.5, midpoint 2.3.
    The two open tails sit half a rung beyond the end strikes. A set of ranges: each range at its
    midpoint, the open-ended tails half a typical range beyond their edge."""
    rungs = [r for r in rungs if r]
    if len(rungs) < 3:
        return None
    if all(r["type"] == "greater" for r in rungs):
        rs = sorted(rungs, key=lambda r: r["floor"])
        s = [r["floor"] for r in rs]
        p = pool_decreasing([r["p"] for r in rs])
        dist = [(s[0] - max(s[1] - s[0] - res, 0) / 2, 1 - p[0])]
        for i in range(len(s)):
            step = s[i + 1] - s[i] if i + 1 < len(s) else s[i] - s[i - 1]
            dist.append((s[i] + (step + res) / 2, p[i] - (p[i + 1] if i + 1 < len(s) else 0)))
    else:
        widths = sorted(r["cap"] - r["floor"] for r in rungs if r["type"] == "between"
                        and r["floor"] is not None and r["cap"] is not None)
        w = widths[len(widths) // 2] if widths else 0.0
        dist = []
        for r in rungs:
            if r["type"] == "between" and r["floor"] is not None and r["cap"] is not None:
                dist.append(((r["floor"] + r["cap"]) / 2, r["p"]))
            elif r["type"] == "less" and r["cap"] is not None:
                dist.append((r["cap"] - res - w / 2, r["p"]))
            elif r["type"] == "greater" and r["floor"] is not None:
                dist.append((r["floor"] + res + w / 2, r["p"]))
        total = sum(m for _, m in dist)
        if total <= 0:
            return None
        dist = [(x, m / total) for x, m in dist]
    dist = [(x, max(0.0, m)) for x, m in dist]
    mean = sum(x * m for x, m in dist) / (sum(m for _, m in dist) or 1.0)
    return mean, sorted(dist)


def has_view(rungs):
    """A rung priced between 10% and 90% with a two-sided book within 10 cents."""
    return any(r and CORE[0] <= r["p"] <= CORE[1] and r["bid"] is not None
               and r["ask"] is not None and 0 <= r["ask"] - r["bid"] <= TIGHT for r in rungs)


def crossed(rungs):
    if not rungs or not all(r["type"] == "greater" for r in rungs):
        return False
    ps = [r["p"] for r in sorted(rungs, key=lambda r: r["floor"])]
    return any(ps[j] - ps[i] > CROSSED for i in range(len(ps)) for j in range(i + 1, len(ps)))


# ---------------------------------------------------------------- Kalshi reads
def open_events(series):
    return kalshi("events", {"series_ticker": series, "status": "open",
                             "with_nested_markets": "true", "limit": 200}).get("events", [])


def closes(ev):
    times = [m["close_time"] for m in ev.get("markets", []) if m.get("close_time")]
    return min(times) if times else None


def next_event(spec, now):
    """The event a card shows: the soonest-closing open event (the next print), this year's event
    for a calendar-year market, and for GDP the next quarter BEA has not yet published (Kalshi's
    GDP market stays open until the morning after the advance estimate; the ticker carries the
    estimate's date, e.g. KXGDP-27JAN28)."""
    evs = open_events(spec["series"])
    if spec.get("year"):
        mine = [e for e in evs if e["event_ticker"].endswith(f"-{now.year % 100:02d}")]
        if mine:
            return mine[0]
    stamp = now.astimezone(dt.timezone.utc).isoformat()
    evs = [e for e in evs if closes(e) and closes(e) > stamp]
    if spec["id"] == "gdp_q":
        def published(e):
            m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})$", e["event_ticker"])
            if not m:
                return False
            day = dt.datetime.strptime(m.group(0)[1:], "%y%b%d").date()
            return day < now.date() or (day == now.date() and now.hour * 60 + now.minute >= 510)
        evs = [e for e in evs if not published(e)]
    return min(evs, key=closes) if evs else None


def event_markets(event_ticker):
    out = []
    for m in kalshi("markets", {"event_ticker": event_ticker, "limit": 200}).get("markets", []):
        if m.get("yes_bid_dollars") is None and m.get("last_price_dollars") is None:
            m = kalshi(f"markets/{m['ticker']}").get("market") or m
        out.append(m)
    return out


def daily_closes(series, ticker, start, end):
    """{day: (price, firm)} from a market's daily candles between two Unix times. A day's price is
    firm when the closing book was within 10 cents or the market traded that day."""
    d = kalshi(f"series/{series}/markets/{ticker}/candlesticks",
               {"start_ts": start, "end_ts": end, "period_interval": 1440})
    out = {}
    for c in d.get("candlesticks", []):
        bid = num((c.get("yes_bid") or {}).get("close_dollars"))
        ask = num((c.get("yes_ask") or {}).get("close_dollars"))
        last = num((c.get("price") or {}).get("close_dollars"))
        if last is None:
            last = num((c.get("price") or {}).get("previous_dollars"))
        p = price(bid, ask, last)
        if p is None:
            continue
        tight = bid is not None and ask is not None and 0 <= ask - bid <= TIGHT
        traded = (num(c.get("volume_fp", c.get("volume"))) or 0) > 0
        # A daily candle ends at midnight Eastern, so it belongs to the day just ended.
        day = dt.datetime.fromtimestamp(int(c["end_period_ts"]) - 1, ET).date().isoformat()
        out[day] = (min(1.0, max(0.0, p)), tight or traded)
    time.sleep(0.1)    # be polite to a public endpoint
    return out


def daily_history(spec, markets, start, end):
    """The expected print at each day's close, using firm prices only. A rung with no firm price
    that day carries its last firm price for up to 7 days. A day counts only when some rung
    between 10% and 90% was firm that day, and the ladder is not badly out of order."""
    shape = {m["ticker"]: rung(m, p=0.5) for m in markets}
    shape = {t: r for t, r in shape.items() if r}
    per = {t: daily_closes(spec["series"], t, start, end) for t in shape}
    last = {t: None for t in per}
    out = {}
    for d in sorted({d for rows in per.values() for d in rows}):
        live = False
        for t in per:
            if d in per[t] and per[t][d][1]:
                last[t] = (per[t][d][0], d)
                live = live or CORE[0] <= per[t][d][0] <= CORE[1]
        if not live:
            continue
        cutoff = (dt.date.fromisoformat(d) - dt.timedelta(days=STALE_DAYS)).isoformat()
        rungs = [{**shape[t], "p": last[t][0]} for t in per if last[t] and last[t][1] >= cutoff]
        if crossed(rungs):
            continue
        res = distribution(rungs, spec["res"])
        if res:
            out[d] = round(res[0] / spec["scale"], 4)
    return pd.Series(out, dtype=float)


def week_change(path):
    """Today's mean less the history's point on or before seven days earlier."""
    if len(path) < 2:
        return None
    target = (dt.date.fromisoformat(path.index[-1]) - dt.timedelta(days=7)).isoformat()
    before = path[path.index <= target]
    return None if before.empty else round(path.iloc[-1] - before.iloc[-1], 4)


# ---------------------------------------------------------------- 1. today
now = dt.datetime.now(ET)
today = now.date().isoformat()
rows, dists = [], []
for spec in SPECS:
    ev = next_event(spec, now)
    if not ev:
        print(f"  {spec['id']}: no open event")
        continue
    markets = event_markets(ev["event_ticker"])
    rungs = [r for r in (rung(m) for m in markets) if r]
    res = distribution(rungs, spec["res"])
    if not res or not has_view(rungs):
        print(f"  {spec['id']}: {ev['event_ticker']} has no tight book in the middle — no view")
        continue
    mean, dist = res[0] / spec["scale"], res[1]
    end = int(time.time())
    path = daily_history(spec, markets, end - 120 * 86400, end)
    path = pd.concat([path[path.index < today], pd.Series({today: round(mean, 4)})])
    save(path.rename("v").rename_axis("date"), HERE, f"path_{spec['id']}")
    rows.append({"id": spec["id"], "label": spec["label"], "event": ev["event_ticker"],
                 "title": ev.get("title"), "expected": round(mean, 4),
                 "change_1w": week_change(path), "read_at": now.isoformat(timespec="seconds")})
    dists += [{"id": spec["id"], "print": round(x / spec["scale"], 4), "probability": round(p, 4)}
              for x, p in dist]
expected = pd.DataFrame(rows).set_index("id")
save(expected, HERE, "expected")
save(pd.DataFrame(dists).set_index("id"), HERE, "distribution")

# ---------------------------------------------------------------- 2. the published history
# Each published card names its event and was built at a known time with a known window (45 days
# for most cards; 120 for the quarter's GDP, which carries its full path). The same window, read
# from Kalshi's candles, gives the same daily history; the card's newest point is the live book
# at the minute it was built, so only the days before that are compared.
site = published_anywhere("data/predictions-macro.json")
built = dt.datetime.fromisoformat(site["updated"].replace("Z", "+00:00"))
built_day = built.astimezone(ET).date().isoformat()
by_id = {s["id"]: s for s in SPECS}
ours, theirs = {}, {}
for card in site["cards"]:
    spec = by_id.get(card["id"])
    if not spec:
        continue
    window = 120 if card["id"] == "gdp_q" else 45
    end = int(built.timestamp())
    hist = daily_history(spec, event_markets(card["ticker"]), end - window * 86400, end)
    for day, v in hist[hist.index < built_day].items():
        ours[f"{card['id']} {day}"] = v
    for p in card.get("path") or card["spark"]:
        theirs[f"{card['id']} {p['date']}"] = p["v"]
# One row per card and day ("cpi 2026-11-06"), so a card the site is not showing simply drops out.
save(pd.Series(ours, name="v").rename_axis("card_day"), HERE, "check_history")
save(pd.Series(theirs, name="v").rename_axis("card_day"), HERE, "site_history")

print(expected[["event", "expected", "change_1w", "read_at"]].to_string())
