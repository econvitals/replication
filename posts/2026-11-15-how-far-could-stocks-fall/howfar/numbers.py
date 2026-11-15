"""Rebuild every number in the post that this package can rebuild, and write output/numbers.json.

Each block says what it needs. Blocks on public data (data/) always run. Blocks that need a licensed file
(licensed/, not shipped; see licensed/README.md) run only when that file is present; otherwise their numbers
are listed in output/skipped.json with the file they need, and verify.py reports them as SKIPPED.

    python -m howfar.numbers
"""
import bisect
import datetime as dt
import json
import math
import re
import statistics as st

from .common import CAPE_NOW, D, DATA, LICENSED, NOW, OUT, daily_closes, fred, have, month_key, rows, write_json

R = {}          # metric -> rebuilt value
SKIP = {}       # metric -> the licensed file it needs


def need(files, metrics):
    """True if every licensed file is present; else record the metrics as skipped."""
    missing = [f for f in files if not have(f)]
    for m in metrics:
        if missing:
            SKIP[m] = ", ".join(missing)
    return not missing


def pct(a, b):
    """Percent change from b to a."""
    return (a / b - 1) * 100


# ---------------------------------------------------------------------------------------------- whole market
def whole_market():
    """The whole U.S. stock market, price only, daily. Ken French's daily CRSP value-weighted return
    (Mkt-RF + RF, all NYSE, AMEX and Nasdaq stocks) with the S&P 500's dividend yield taken out day by day
    (Shiller's monthly yield / 252), through September 30, 2026; extended to November 13 with the Vanguard
    Total Stock Market ETF's closes when licensed/vti_daily.csv is present."""
    tr = []
    for line in open(DATA / "french_factors_daily.csv", encoding="utf-8", errors="ignore"):
        p = [x.strip() for x in line.split(",")]
        if len(p) >= 5 and p[0].isdigit() and len(p[0]) == 8:
            tr.append((D(int(p[0][:4]), int(p[0][4:6]), int(p[0][6:])), (float(p[1]) + float(p[4])) / 100))
    dy = {month_key(r["month"]): float(r["dividend_yield"]) for r in rows(DATA / "shiller_dividend_yield_as_used.csv")}
    last = max(dy)
    px, b = {}, 100.0
    for d, r in tr:
        b *= 1 + r - dy.get((d.year, d.month), dy[last]) / 252
        px[d] = b
    if have("vti_daily.csv"):
        vti = daily_closes("vti_daily.csv")
        base_d = D(2026, 9, 30)
        base = px[base_d]
        for d in sorted(vti):
            if d > base_d:
                px[d] = base * vti[d] / vti[base_d]
    return px


def on_or_before(series, d):
    ds = sorted(series)
    j = bisect.bisect_right(ds, d) - 1
    return ds[j], series[ds[j]]


def gdp_line():
    """Nominal GDP (BEA via FRED), each quarter placed at its middle month and interpolated by day;
    extrapolated at the last quarter's growth rate past the last mid-quarter."""
    g = fred("GDP")
    mids = sorted((D(d.year, d.month + 1, 15), v) for d, v in g.items())

    def at(d):
        for (d0, v0), (d1, v1) in zip(mids, mids[1:]):
            if d0 <= d <= d1:
                return v0 + (v1 - v0) * (d - d0).days / (d1 - d0).days
        (d0, v0), (d1, v1) = mids[-2], mids[-1]
        return v1 * (v1 / v0) ** ((d - d1).days / (d1 - d0).days)
    return g, at


def block_whole_market():
    px = whole_market()
    g, gdp_at = gdp_line()
    # "the previous 6¾ years" = the span from the end of 2019 to the S&P 500's record close (October 6, 2026)
    span = (D(2026, 10, 6) - D(2019, 12, 31)).days
    R["t3_span_years"] = round(span / 365.25, 2)
    for name, ev in (("1996", D(1996, 12, 5)), ("2000", D(2000, 3, 24))):
        start = ev - dt.timedelta(days=span)
        ed, ep = on_or_before(px, ev)
        bd, bp = on_or_before(px, start)
        R[f"t3_gdp_{name}"] = pct(bp * gdp_at(ed) / gdp_at(bd), ep)
        R[f"t3_start_{name}"] = bd.strftime("%B %Y")
        later = [(px[d], d) for d in sorted(px) if ed < d <= D(2006, 12, 31)]
        lo_v, lo_d = min(later)
        R[f"t3_actual_{name}"] = pct(lo_v, ep)
        R[f"t3_low_date_{name}"] = lo_d.isoformat()
    R["t3_oct2002_vs_dec1996"] = pct(px[D(2002, 10, 9)], on_or_before(px, D(1996, 12, 5))[1])
    # nominal GDP growth, 2019Q4 to the latest quarter (2026Q3)
    q0, q1 = D(2019, 10, 1), max(g)
    R["gdp_growth_since_2019"] = ((g[q1] / g[q0]) ** (365.25 / (q1 - q0).days) - 1) * 100
    R["gdp_latest_quarter"] = f"{q1.year}Q{(q1.month - 1) // 3 + 1}"

    if need(["vti_daily.csv"], ["t2_gdp_now", "t3_gdp_now", "whole_record_date", "whole_below_record"]):
        ed, ep = on_or_before(px, NOW)
        bd, bp = on_or_before(px, D(2019, 12, 31))
        R["t2_gdp_now"] = R["t3_gdp_now"] = pct(bp * gdp_at(ed) / gdp_at(bd), ep)
        rec_v, rec_d = max((px[d], d) for d in px if d >= D(2026, 1, 1))
        R["whole_record_date"] = rec_d.isoformat()
        R["whole_below_record"] = pct(px[NOW], rec_v)


# ---------------------------------------------------------------------------------------------- Shiller ratio
def shiller():
    s = {}
    for r in rows(DATA / "shiller_monthly.csv"):
        s[month_key(r["month"])] = {k: (float(r[k]) if r[k] not in ("", "NA") else None)
                                    for k in ("price", "dividend", "earnings", "cpi", "cape")}
    return s


def block_cape():
    s = shiller()
    cape = {k: v["cape"] for k, v in s.items() if v["cape"] is not None}

    def avg(a, b):
        return st.mean(v for k, v in cape.items() if a <= k <= b)
    R["cape_now"] = CAPE_NOW
    R["cape_avg_1979_now"] = avg((1979, 1), (2026, 10))
    R["cape_avg_1979_1996"] = avg((1979, 1), (1996, 11))
    R["cape_avg_1979_2000"] = avg((1979, 1), (2000, 2))
    R["cape_dec1996"] = cape[(1996, 12)]
    R["cape_mar2000"] = cape[(2000, 3)]
    R["t2_cape"] = R["t3_cape_now"] = pct(R["cape_avg_1979_now"], CAPE_NOW)
    R["t3_cape_1996"] = pct(R["cape_avg_1979_1996"], cape[(1996, 12)])
    R["t3_cape_2000"] = pct(R["cape_avg_1979_2000"], cape[(2000, 3)])
    allc = sorted(v for k, v in cape.items() if k <= (2026, 10))
    R["cape_first_year"] = min(cape)[0]
    R["cape_percentile_now"] = bisect.bisect_left(allc, CAPE_NOW) / len(allc) * 100
    R["cape_peak_1999_2000"] = max(v for k, v in cape.items() if 1999 <= k[0] <= 2000)
    R["fig2_peak_1929"] = max(v for k, v in cape.items() if k[0] == 1929)
    # the long-run growth of stock prices: the S&P Composite's price, annual average 1945 to annual average 2019
    a0 = st.mean(s[(1945, m)]["price"] for m in range(1, 13))
    a1 = st.mean(s[(2019, m)]["price"] for m in range(1, 13))
    R["sp_price_growth_1945_2019"] = ((a1 / a0) ** (1 / 74) - 1) * 100
    # Table 1, the S&P 500 on March 24, 2000: its close that day over as-reported earnings for the four quarters
    # through 1999Q4, the last reported by then (Shiller's December 1999 row)
    if need(["sp500_daily.csv"], ["t1_sp500_trailing_2000"]):
        R["t1_sp500_trailing_2000"] = daily_closes("sp500_daily.csv")[D(2000, 3, 24)] / s[(1999, 12)]["earnings"]
    # the bottom-line range in the summary: 18 to 41 percent (the low end is the forward-ratio row, below)
    R["range_high"] = -R["t2_cape"]


# ---------------------------------------------------------------------------------------------- profits, TIPS
def block_profits_tips():
    p, g = fred("CPATAX"), fred("GDP")
    sh = {d: p[d] / g[d] * 100 for d in p if d in g}
    ds = sorted(sh)
    R["profit_share_1997"] = max(v for d, v in sh.items() if d.year == 1997)
    R["profit_share_2000q1"] = sh[D(2000, 1, 1)]
    R["profit_share_2019q4"] = sh[D(2019, 10, 1)]
    R["profit_share_now"] = sh[ds[-1]]
    R["profit_share_latest_quarter"] = f"{ds[-1].year}Q{(ds[-1].month - 1) // 3 + 1}"
    R["profit_share_now_minus_prior_max"] = sh[ds[-1]] - max(sh[d] for d in ds[:-1])
    R["profit_share_avg_1947_2019"] = st.mean(v for d, v in sh.items() if d.year <= 2019)
    t = fred("DFII10")
    pre = [v for d, v in t.items() if D(2012, 1, 1) <= d <= D(2019, 12, 31)]
    R["tips_share_below_1_2012_2019"] = sum(v < 1 for v in pre) / len(pre) * 100
    # "above 2 percent for the last six months": each monthly average, May to October 2026
    R["tips_min_monthly_may_oct_2026"] = min(st.mean(v for d, v in t.items() if (d.year, d.month) == (2026, m))
                                             for m in range(5, 11))


# ---------------------------------------------------------------------------------------------- Minneapolis Fed
def mpd():
    out = []
    for r in rows(DATA / "minneapolis_fed_sp12m.csv"):
        if r.get("prDec") not in (None, "", "NA"):
            out.append((dt.datetime.strptime(r["idt"], "%m/%d/%Y").date(), float(r["prDec"]) * 100))
    return sorted(out)


def block_mpd():
    v = mpd()
    avg = st.mean(p for _, p in v)
    R["mpd_latest"] = v[-1][1]
    R["mpd_latest_date"] = v[-1][0].isoformat()
    R["mpd_share_of_weeks_higher"] = sum(p > v[-1][1] for _, p in v) / len(v) * 100
    R["mpd_average"] = avg
    R["mpd_first_year"] = v[0][0].year
    # "below average in October 2007, February 2020 and February 2025": the first reading in each of those
    # months, the months the declines of 2007-09, 2020 and 2025 began
    for lab, (y, m) in (("2007", (2007, 10)), ("2020", (2020, 2)), ("2025", (2025, 2))):
        d, p = [x for x in v if (x[0].year, x[0].month) == (y, m)][0]
        R[f"mpd_{lab}_minus_average"] = p - avg
    if need(["sp500_daily.csv"], ["mpd_realized"]):
        sp = daily_closes("sp500_daily.csv")
        ds = sorted(sp)
        # every trading day from the series' first reading whose year-later close is known: was the S&P 500
        # 20 percent or more lower 365 days later (the first close on or after that day)?
        days = [d for d in ds if d >= v[0][0]]
        n = h = 0
        for d in days:
            j = bisect.bisect_left(ds, d + dt.timedelta(days=365))
            if j >= len(ds):
                break
            n += 1
            h += sp[ds[j]] <= 0.8 * sp[d]
        R["mpd_realized"] = h / n * 100


# ---------------------------------------------------------------------------------------------- options (Table 4)
def block_options():
    levels = (0.90, 0.80, 0.70, 0.60, 0.50)
    keys = [f"t4_options_{round((1 - l) * 100)}" for l in levels]
    if need(["spx_options_2026-11-13.json"], keys):
        d = json.load(open(LICENSED / "spx_options_2026-11-13.json"))
        x = d["data"]
        spot = float(x["current_price"])
        asof = dt.datetime.strptime(d["timestamp"][:10], "%Y-%m-%d").date()
        rate = 0.04
        puts = {}
        for o in x["options"]:
            m = re.match(r"^(SPXW?)(\d{6})([CP])(\d{8})$", o["option"])
            if not m:
                continue
            root, ymd, cp, k = m.groups()
            bid, ask = float(o.get("bid") or 0), float(o.get("ask") or 0)
            if cp != "P" or ask <= 0 or bid < 0:
                continue
            puts.setdefault((ymd, root), {})[int(k) / 1000.0] = ((bid + ask) / 2, bid)
        P = puts[("271217", "SPX")]
        T = (D(2027, 12, 17) - asof).days / 365.25
        ks = sorted(P)
        for key, l in zip(keys, levels):
            K = spot * l
            lo = [k for k in ks if k <= K * 0.985 and P[k][1] > 0]
            hi = [k for k in ks if k >= K * 1.015]
            k0, k1 = lo[-1], hi[0]
            # risk-neutral P(S_T < K) = e^{rT} dPut/dK, from the slope of put prices across neighboring strikes
            R[key] = math.exp(rate * T) * (P[k1][0] - P[k0][0]) / (k1 - k0) * 100
        R["t4_asof"] = asof.isoformat()
    hkeys = [f"t4_history_{c}" for c in (10, 20, 30, 40, 50)]
    if need(["sp500_daily.csv"], hkeys):
        sp = daily_closes("sp500_daily.csv")
        ds = [d for d in sorted(sp) if d >= D(1946, 1, 1)]
        horizon = (D(2027, 12, 17) - NOW).days          # the options' 13 months
        for key, cut in zip(hkeys, (0.10, 0.20, 0.30, 0.40, 0.50)):
            n = h = 0
            for d in ds:
                j = bisect.bisect_left(ds, d + dt.timedelta(days=horizon))
                if j >= len(ds):
                    break
                n += 1
                h += sp[ds[j]] <= sp[d] * (1 - cut)
            R[key] = h / n * 100


# ---------------------------------------------------------------------------------------------- forward P/E
def block_forward():
    """The S&P 500's price over analysts' expected earnings for the next 12 months. History: the monthly series
    (Fed Financial Stability Report data from I/B/E/S from 1988, Yardeni Research for 1979-87, FactSet from May
    2026). The readings on the three dates of Table 3 are point readings (forward_pe_on_dates.csv)."""
    keys = ["fpe_now", "fpe_avg_1979_now", "fpe_percentile_now", "fpe_peak_1999", "fpe_mar2000", "fpe_dec1996",
            "fpe_avg_1979_1996", "fpe_avg_1979_2000", "t2_fwd", "t2_fwd_earn", "t3_fwd_1996", "t3_fwd_2000",
            "t3_fwd_earn_1996", "t3_fwd_earn_2000", "t3_fwd_now", "t3_fwd_earn_now", "range_low", "dotcom_range_low",
            "dotcom_range_high", "t1_sp500_forward_now", "t1_sp500_forward_2000", "t3_fwd_1996_monthly"]
    if not need(["forward_pe_monthly.csv", "forward_pe_on_dates.csv"], keys):
        return
    f = {month_key(r["month"]): float(r["fpe"]) for r in rows(LICENSED / "forward_pe_monthly.csv")}
    on = {r["date"]: float(r["fpe"]) for r in rows(LICENSED / "forward_pe_on_dates.csv")}

    def avg(a, b):
        return st.mean(v for k, v in f.items() if a <= k <= b)
    now = f[(2026, 11)]
    R["fpe_now"] = R["t1_sp500_forward_now"] = now
    R["fpe_avg_1979_now"] = avg((1979, 1), (2026, 10))
    hist = sorted(v for k, v in f.items() if (1979, 1) <= k <= (2026, 10))
    R["fpe_percentile_now"] = bisect.bisect_left(hist, now) / len(hist) * 100
    R["fpe_peak_1999"] = max(v for k, v in f.items() if k[0] <= 2000)
    R["fpe_mar2000"] = R["t1_sp500_forward_2000"] = on["2000-03-24"]
    R["fpe_dec1996"] = on["1996-12-05"]
    R["fpe_avg_1979_1996"] = avg((1979, 1), (1996, 11))
    R["fpe_avg_1979_2000"] = avg((1979, 1), (2000, 2))
    for tag, lvl, a in (("now", on["2026-11-13"], R["fpe_avg_1979_now"]), ("1996", on["1996-12-05"], R["fpe_avg_1979_1996"]),
                        ("2000", on["2000-03-24"], R["fpe_avg_1979_2000"])):
        R[f"t3_fwd_{tag}"], R[f"t3_fwd_earn_{tag}"] = pct(a, lvl), pct(0.8 * a, lvl)
    R["t2_fwd"], R["t2_fwd_earn"] = R["t3_fwd_now"], R["t3_fwd_earn_now"]
    # the same 1996 cell on the monthly series' December 1996 reading (15.97) instead of the post's 15.9
    R["t3_fwd_1996_monthly"] = pct(R["fpe_avg_1979_1996"], f[(1996, 12)])
    R["range_low"] = -R["t2_fwd"]
    col2000 = [R["t3_fwd_2000"], R["t3_fwd_earn_2000"], R["t3_cape_2000"], R["t3_gdp_2000"]]
    R["dotcom_range_low"], R["dotcom_range_high"] = -max(col2000), -min(col2000)


# ---------------------------------------------------------------------------------------------- companies
def sec_ttm(company, end_by):
    """Revenue over the last four reported quarters ending on or before end_by, from SEC XBRL facts.
    A fourth fiscal quarter that is reported only inside the annual figure is the year less its first three."""
    q, yr = {}, {}
    for r in rows(DATA / "sec_revenue.csv"):
        if r["company"] != company:
            continue
        a, b = dt.date.fromisoformat(r["start"]), dt.date.fromisoformat(r["end"])
        days = (b - a).days
        if 80 <= days <= 100:
            q[b] = float(r["usd"])
        elif 350 <= days <= 380:
            yr[b] = (a, float(r["usd"]))
    for b, (a, v) in yr.items():
        if b not in q:
            inside = [v2 for e, v2 in q.items() if a < e < b]
            if len(inside) == 3:
                q[b] = v - sum(inside)
    last4 = [q[e] for e in sorted(q) if e <= end_by][-4:]
    return sum(last4)


def block_companies():
    # revenue: the last four reported quarters (to July 2026 for Nvidia, September 2026 for the others)
    # against the same four quarters three years earlier
    for name, end in (("Nvidia", D(2026, 7, 31)), ("Alphabet", D(2026, 9, 30)), ("Microsoft", D(2026, 9, 30))):
        now = sec_ttm(name, end)
        then = sec_ttm(name, D(end.year - 3, end.month, end.day))
        R[f"revenue_ratio_{name.lower()}"] = now / then
        R[f"revenue_growth_{name.lower()}"] = (now / then - 1) * 100
    # household stock wealth: directly and indirectly held corporate equities (Z.1), the latest quarter
    z = rows(DATA / "z1_household_equities.csv")
    R["z1_quarter"] = z[-1]["quarter"]
    R["household_stock_tn"] = float(z[-1]["LM153064475_musd"]) / 1e6
    R["household_stock_25pct_fall_tn"] = 0.25 * R["household_stock_tn"]
    # the technology-explosion example: 85 percent chance of +30 percent, 15 percent chance of -50 percent
    R["explosion_expected_return"] = 0.85 * 30 + 0.15 * -50
    # Tesla since the April 10, 2017 close, the day its market value passed General Motors' (it had passed Ford's on April 3)
    tk = ["tesla_price_gain", "tesla_value_fall_to_2017"]
    if need(["tsla_daily.csv"], tk):
        t = daily_closes("tsla_daily.csv")
        sh = {dt.date.fromisoformat(r["as_of"]): float(r["shares"]) for r in rows(DATA / "sec_tesla_shares_outstanding.csv")}
        p0, p1 = t[D(2017, 4, 10)], t[NOW]
        R["tesla_price_gain"] = pct(p1, p0)
        # market value: split-adjusted price (5-for-1 in 2020, 3-for-1 in 2022) times split-adjusted shares
        s0 = on_or_before(sh, D(2017, 4, 30))[1] * 15
        s1 = on_or_before(sh, NOW)[1]
        R["tesla_value_fall_to_2017"] = -pct(p0 * s0, p1 * s1)
    if need(["sp500_daily.csv"], ["sp500_gain_since_2019", "sp500_record_date"]):
        sp = daily_closes("sp500_daily.csv")
        R["sp500_gain_since_2019"] = pct(sp[NOW], on_or_before(sp, D(2019, 12, 31))[1])
        R["sp500_record_date"] = max((v, d) for d, v in sp.items() if d.year == 2026)[1].isoformat()
    if need(["igv_daily.csv"], ["software_fall_since_peak", "software_peak_month"]):
        ig = daily_closes("igv_daily.csv")
        pv, pdt = max((v, d) for d, v in ig.items() if d >= D(2025, 1, 1))
        R["software_fall_since_peak"] = pct(ig[NOW], pv)
        R["software_peak_month"] = pdt.strftime("%B %Y")
    if need(["ai7_market_values.csv"], ["ai7_value_tn", "ai7_share_of_market", "t2_ai7", "t3_ai7_now"]):
        mv = {r["company"]: float(r["market_value_usd_bn"]) for r in rows(LICENSED / "ai7_market_values.csv")}
        whole = mv.pop("All listed U.S. stocks")
        R["ai7_value_tn"] = sum(mv.values()) / 1000
        R["ai7_share_of_market"] = sum(mv.values()) / whole * 100
        R["t2_ai7"] = R["t3_ai7_now"] = -0.5 * R["ai7_share_of_market"]
    # Table 1
    if need(["table1_inputs.csv"], ["t1_" + x for x in ("nvidia_tr", "microsoft_tr", "alphabet_tr", "amazon_tr", "meta_tr",
            "broadcom_tr", "oracle_tr", "nvidia_fw", "microsoft_fw", "alphabet_fw", "amazon_fw", "meta_fw", "broadcom_fw",
            "oracle_fw", "cisco2000_tr", "oracle2000_tr", "microsoft2000_tr", "intel2000_tr", "ibm2000_tr", "lucent2000_tr",
            "cisco2000_fw", "oracle2000_fw", "microsoft2000_fw", "intel2000_fw", "ibm2000_fw", "lucent2000_fw",
            "nortel2000_fw", "sp500_trailing_now")]):
        ni = {r["company"]: (float(r["net_income_musd"]) if r["net_income_musd"] else None)
              for r in rows(DATA / "sec_2000_net_income.csv")}
        for r in rows(LICENSED / "table1_inputs.csv"):
            c, when = r["company"], r["date"]
            tag = c.lower().replace(" ", "").replace("networks", "") + ("2000" if when.startswith("2000") else "")
            if c == "S&P 500":
                R["t1_sp500_trailing_now"] = float(r["trailing_pe"])
                continue
            if when.startswith("2026"):
                R[f"t1_{tag}_tr"] = float(r["price"]) / float(r["trailing_eps"])
            elif ni.get(c):
                R[f"t1_{tag}_tr"] = float(r["market_value_usd_bn"]) * 1000 / ni[c]
            R[f"t1_{tag}_fw"] = float(r["forward_pe"])


def main():
    for block in (block_whole_market, block_cape, block_profits_tips, block_mpd, block_options, block_forward,
                  block_companies):
        block()
    write_json(OUT / "numbers.json", R)
    write_json(OUT / "skipped.json", SKIP)
    print(f"numbers: {len(R)} rebuilt, {len(SKIP)} skipped for want of licensed data -> output/numbers.json")


if __name__ == "__main__":
    main()
