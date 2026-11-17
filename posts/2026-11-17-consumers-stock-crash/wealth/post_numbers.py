"""The post's numbers that do not come from the consumption-function scripts: the stock market declines since 1946
(Figure 1), house prices over those declines, the 2001 recession (Figures 2 and 3), 1987, the value of U.S. stocks
relative to GDP (Figure 4), who owns stock, and the ten richest Americans. Run from the package folder after
build_panel.py. Writes output/post_numbers.json (and output/bear_markets.csv, output/recession_contributions.csv).

The S&P 500 itself is licensed data and is not in this package. Two sentences rest on it: the 20.5 percent fall on
October 19, 1987 (a matter of record) and the correlation of yearly changes in real stock and house prices (0.16),
which used S&P 500 quarter-end closes. The correlation is computed here when licensed/sp500_daily.csv (columns
date, close) is present and skipped otherwise; the same correlation using the whole market from public data is
reported alongside as a check (it is not the number in the post).
"""
import csv
import io
import json
import statistics as st
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT, LIC = ROOT / "data", ROOT / "output", ROOT / "licensed"
N = {}

# ---------------------------------------------------------------- 1. stock market declines of 20% or more since 1946
# The whole U.S. market, price only: Ken French's daily value-weighted return (Mkt-RF + RF) less the S&P 500's
# dividend yield (Shiller, as downloaded November 14, 2026; months after June 2024 use the June 2024 yield) / 252.
tr = []
for line in open(DATA / "french_factors_daily.csv", encoding="utf-8", errors="ignore"):
    p = [x.strip() for x in line.split(",")]
    if len(p) >= 5 and p[0].isdigit() and len(p[0]) == 8:
        tr.append((date(int(p[0][:4]), int(p[0][4:6]), int(p[0][6:])), (float(p[1]) + float(p[4])) / 100))
dy = {}
for r in csv.DictReader(open(DATA / "shiller_dividend_yield_as_used.csv")):
    y, m = r["month"].split("-")
    dy[(int(y), int(m))] = float(r["dividend_yield"])
last = max(dy)
px, b = [], 100.0
for d, r in tr:
    b *= 1 + r - dy.get((d.year, d.month), dy[last]) / 252
    px.append((d, b))


def months_between(d0, d1):
    return (d1 - d0).days / 30.4375


def zigzag(px, down, up):
    """A decline starts when the index is `down` below its running peak and ends at its lowest close once the index
    is `up` above that low."""
    legs, (pk_d, pk), bear = [], px[0], False
    tr_d, trv = px[0]
    for d, x in px[1:]:
        if not bear:
            if x > pk:
                pk_d, pk = d, x
            elif x <= pk * (1 - down):
                bear, tr_d, trv = True, d, x
        else:
            if x < trv:
                tr_d, trv = d, x
            elif x >= trv * (1 + up):
                legs.append(dict(peak=pk_d, pk=pk, trough=tr_d, tr=trv))
                bear, pk_d, pk = False, d, x
    if bear:
        legs.append(dict(peak=pk_d, pk=pk, trough=tr_d, tr=trv))
    return legs


def merge(legs):
    """Two legs are one decline when the rally between them lasted under six months and made no new high."""
    out = []
    for L in legs:
        if out and months_between(out[-1]["trough"], L["peak"]) < 6 and L["pk"] < out[-1]["pk"]:
            if L["tr"] < out[-1]["tr"]:
                out[-1]["trough"], out[-1]["tr"] = L["trough"], L["tr"]
            continue
        out.append(dict(L))
    return out


NBER_PEAKS = [(1948, 11), (1953, 7), (1957, 8), (1960, 4), (1969, 12), (1973, 11), (1980, 1), (1981, 7), (1990, 7),
              (2001, 3), (2007, 12), (2020, 2)]


def recession(peak_d):
    """The recession a decline goes with: an NBER peak from six months before the stock peak to 13 after."""
    k = peak_d.year * 12 + peak_d.month - 1
    for y, m in NBER_PEAKS:
        if -6 <= (y * 12 + m - 1) - k <= 13:
            return f"{y}-{m:02d}"
    return ""


eps = [L for L in merge(zigzag(px, 0.20, 0.20)) if L["peak"] >= date(1946, 1, 1)]
rows = [dict(peak=str(L["peak"]), trough=str(L["trough"]), decline=round((L["tr"] / L["pk"] - 1) * 100, 1),
             recession=recession(L["peak"])) for L in eps]
pd.DataFrame(rows).to_csv(OUT / "bear_markets.csv", index=False)
hit = sorted({r["recession"] for r in rows if r["recession"]})
N["bear_declines_since_1946"] = len(rows)
N["bear_recessions_with_decline"] = len(hit)
N["bear_recessions_since_1946"] = 12          # NBER recessions with peaks from 1948 to 2020; 1980 and 1981-82 separate
N["bear_recessions_missed"] = 12 - len(hit)
N["bear_declines_since_1980"] = sum(1 for r in rows if r["peak"] >= "1980")
for r in rows:
    N[f"fig1_decline_{r['peak'][:7]}"] = r["decline"]
N["bear_2000_decline"] = next(r["decline"] for r in rows if r["peak"].startswith("2000"))

# ---------------------------------------------------------------- 2. house prices over the declines since 1980
fh = pd.read_csv(DATA / "fred_ussthpi.csv", index_col=0)["USSTHPI"]
fh.index = pd.PeriodIndex(pd.to_datetime(fh.index), freq="Q")
cpi = pd.read_csv(DATA / "fred_cpiaucsl.csv", index_col=0)["CPIAUCSL"]
cpi.index = pd.PeriodIndex(pd.to_datetime(cpi.index), freq="M")
hp = []
for r in rows:
    if r["peak"] < "1980":
        continue
    p0, p1 = pd.Timestamp(r["peak"]), pd.Timestamp(r["trough"])
    nom = fh[p1.to_period("Q")] / fh[p0.to_period("Q")] - 1
    real = (1 + nom) / (cpi[p1.to_period("M")] / cpi[p0.to_period("M")]) - 1
    hp.append(dict(peak=r["peak"], nominal=100 * nom, real=100 * real))
    N[f"house_nominal_{r['peak'][:4]}"] = round(100 * nom, 1)
    N[f"house_real_{r['peak'][:4]}"] = round(100 * real, 1)
N["house_nominal_falls_since_1980"] = sum(1 for h in hp if h["nominal"] < -0.05)
N["house_real_falls_since_1980"] = sum(1 for h in hp if h["real"] < -0.05)


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5


def real_q(series_q, k):
    return series_q[k] / cpi[pd.Period(f"{k.year}-{k.quarter * 3:02d}", "M")]


def yearly_corr(stock_q):
    qs = [k for k in fh.index if k.year >= 1976 and k in stock_q.index and (k - 4) in stock_q.index and (k - 4) in fh.index]
    xs = [real_q(stock_q, k) / real_q(stock_q, k - 4) - 1 for k in qs]
    ys = [real_q(fh, k) / real_q(fh, k - 4) - 1 for k in qs]
    return corr(xs, ys), len(qs)


wm = pd.Series({pd.Period(d, "Q"): x for d, x in px})          # last close in each quarter (later days overwrite)
N["house_stock_corr_whole_market_check"], _ = yearly_corr(wm)
if (LIC / "sp500_daily.csv").exists():
    sp = pd.read_csv(LIC / "sp500_daily.csv", parse_dates=["date"]).sort_values("date")
    spq = sp.groupby(sp["date"].dt.to_period("Q"))["close"].last()
    N["house_stock_corr_1976"], _ = yearly_corr(spq)

# ---------------------------------------------------------------- 3. the 2001 recession
bq = pd.read_csv(DATA / "bea_gdp_quarterly.csv", index_col=0)
bq.columns = [c.split(" [")[0] for c in bq.columns]
# business investment: BEA's quantity index (table 1.1.3), since its chained-dollar series start only in 2007
bfi, pce, gdp_r, gdp_n = bq["bfi_quantity_index"], bq["pce_real"], bq["gdp_real"], bq["gdp_nominal"]
run_, best = 0, 0
for a, b_ in zip(bfi.loc["2000Q1":"2004Q4"].index[:-1], bfi.loc["2000Q1":"2004Q4"].index[1:]):
    run_ = run_ + 1 if bfi[b_] < bfi[a] else 0
    best = max(best, run_)
N["bfi_quarters_falling_2001"] = best
N["bfi_fall_2000q4_2002q4"] = 100 * (bfi["2002Q4"] / bfi["2000Q4"] - 1)
g4 = (pce / pce.shift(4) - 1) * 100
N["pce_worst_four_quarters_2000_2003"] = float(g4.loc["2000Q4":"2003Q4"].min())
N["pce_growth_2001_q4q4"] = 100 * (pce["2001Q4"] / pce["2000Q4"] - 1)
N["bfi_growth_2001_q4q4"] = 100 * (bfi["2001Q4"] / bfi["2000Q4"] - 1)
N["gdp_growth_1988_q4q4"] = 100 * (gdp_r["1988Q4"] / gdp_r["1987Q4"] - 1)
N["pce_growth_1988_q4q4"] = 100 * (pce["1988Q4"] / pce["1987Q4"] - 1)
N["gdp_growth_1987q3_1988q3"] = 100 * (gdp_r["1988Q3"] / gdp_r["1987Q3"] - 1)
N["pce_growth_1987q3_1988q3"] = 100 * (pce["1988Q3"] / pce["1987Q3"] - 1)
ur = pd.read_csv(DATA / "fred_unrate.csv", index_col=0)["UNRATE"]
N["unrate_dec_2000"] = float(ur["2000-12-01"])
N["unrate_dec_2001"] = float(ur["2001-12-01"])
ft = pd.read_csv(DATA / "fred_fed_funds_target_2000_2002.csv", index_col=0)["DFEDTAR"]
N["fed_target_end_2000"] = float(ft["2000-12-31"])
N["fed_target_end_2001"] = float(ft["2001-12-31"])

# contributions to GDP growth in each recession, against the pace of the previous ten years (Figure 2)
t = pd.read_csv(DATA / "bea_t10102_contributions.csv", index_col=0)
t.columns = [c.split(" [")[0] for c in t.columns]
SIX = ["C", "BFI", "Res", "Inv", "G", "NX"]
RECS = [("1953–54", "1953Q2", "1954Q2"), ("1957–58", "1957Q3", "1958Q2"), ("1960–61", "1960Q2", "1961Q1"),
        ("1969–70", "1969Q4", "1970Q4"), ("1973–75", "1973Q4", "1975Q1"), ("1980–82", "1980Q1", "1982Q4"),
        ("1990–91", "1990Q3", "1991Q1"), ("2001", "2001Q1", "2001Q4"), ("2007–09", "2007Q4", "2009Q2"),
        ("2020", "2019Q4", "2020Q2")]
qs = list(t.index); idx = {k: i for i, k in enumerate(qs)}


def gq(k):
    return (1 + t.loc[k, "GDP"] / 100) ** 0.25 - 1


def qc(k, x):
    tot = sum(t.loc[k, s] for s in SIX) / 100
    c = t.loc[k, x] / 100
    return c * gq(k) / tot if abs(tot) > 0.002 else c / 4


def shortfall(p, tr_):
    s, e = idx[p], idx[tr_]
    I, cum = 1.0, {x: 0.0 for x in SIX}
    for i in range(s + 1, e + 1):
        for x in SIX:
            cum[x] += qc(qs[i], x) * I
        I *= 1 + gq(qs[i])
    lo, hi = max(0, s - 39), s
    nrm = {x: sum(qc(qs[i], x) for i in range(lo, hi + 1)) / (hi - lo + 1) for x in SIX}
    v = {x: (cum[x] - (e - s) * nrm[x]) * 100 for x in SIX}
    v["total"] = sum(v[x] for x in SIX)
    return v


rc = {n: shortfall(p, tr_) for n, p, tr_ in RECS}
pd.DataFrame(rc).T.to_csv(OUT / "recession_contributions.csv")
for n, v in rc.items():
    N[f"fig2_consumer_drag_{n[:4]}"] = round(v["C"], 1)
others = [n for n in rc if n != "2001"]
N["recession_consumer_drag_2001"] = rc["2001"]["C"]
N["recession_consumer_drag_median_others"] = st.median(rc[n]["C"] for n in others)
N["recession_consumer_share_2001"] = 100 * rc["2001"]["C"] / rc["2001"]["total"]
N["recession_consumer_share_median_others"] = st.median(100 * rc[n]["C"] / rc[n]["total"] for n in others)
N["recessions_consumer_less_than_bfi"] = ",".join(n for n in rc if rc[n]["C"] > rc[n]["BFI"])
N["recession_2001_smallest_consumer_drag"] = int(max(rc, key=lambda n: rc[n]["C"]) == "2001")

# the December 2000 Greenbook (Part 1, p. I-6, 2001 Q4/Q4) against the Philadelphia Fed's real-time data
GB = {"GDP": 3.1, "PCE": 3.0, "RES": -0.4, "BFI": 7.1, "GOV": 3.6}
for k, v in GB.items():
    N[f"greenbook_2001_{k.lower()}"] = v
RT = {"GDP": "routput", "PCE": "rcon", "RES": "rinvresid", "BFI": "rinvbf", "GOV": "rg"}


def rtdsm(v):
    zin = zipfile.ZipFile(DATA / "greenbook" / f"{v}.xlsx"); buf = io.BytesIO(); zout = zipfile.ZipFile(buf, "w")
    for it in zin.infolist():
        if it.filename != "docProps/core.xml":      # openpyxl cannot parse these files' date properties
            zout.writestr(it, zin.read(it.filename))
    zout.close(); buf.seek(0)
    df = pd.read_excel(buf)
    return df.set_index(df.columns[0])


for k, v in RT.items():
    df = rtdsm(v)
    c02 = [c for c in df.columns if str(c).upper().endswith("02Q1")][0]
    g = lambda c: float(100 * (pd.to_numeric(df[c], errors="coerce").loc["2001:Q4"] / pd.to_numeric(df[c], errors="coerce").loc["2000:Q4"] - 1))
    N[f"rtdsm_first_2001_{k.lower()}"] = g(c02)
    N[f"rtdsm_latest_2001_{k.lower()}"] = g(df.columns[-1])

# ---------------------------------------------------------------- 4. the value of U.S. stocks relative to GDP (Figure 4)
f = pd.read_csv(DATA / "z1_f511_corporate_equities.csv", index_col=0)
f.index = pd.PeriodIndex(f.index, freq="Q")
gq_n = pd.Series(gdp_n.values, index=pd.PeriodIndex(gdp_n.index, freq="Q"))
allus = f["LM103164105"] + f["LM793164105"] - f["LM554090005"].fillna(0) - f["LM564090005"].fillna(0)
ratio = (allus / gq_n * 100).dropna()
pan = pd.read_csv(OUT / "panel.csv", index_col=0)
S = pd.Series(pan["S"].values, index=pd.PeriodIndex(pan.index, freq="Q"))
hh = (S / gq_n * 100).dropna()
pd.DataFrame({"all_us_stock_pct_gdp": ratio, "household_stock_pct_gdp": hh}).to_csv(OUT / "stocks_gdp.csv")
N["stocks_gdp_avg_1952_1995"] = float(ratio.loc["1952Q1":"1995Q4"].mean())
N["stocks_gdp_2000q1"] = float(ratio["2000Q1"])
N["stocks_gdp_2026q2"] = float(ratio["2026Q2"])
N["stocks_gdp_record_2026q2"] = int(ratio.idxmax() == pd.Period("2026Q2", "Q"))
N["foreign_share_2000q1"] = float(100 * f.loc["2000Q1", "LM263064105"] / allus["2000Q1"])
N["foreign_share_2026q2"] = float(100 * f.loc["2026Q2", "LM263064105"] / allus["2026Q2"])
N["household_stock_gdp_2000q1"] = float(hh["2000Q1"])
N["household_stock_gdp_2026q2"] = float(hh["2026Q2"])
N["loss_25pct_today_pct_gdp"] = 0.25 * float(hh["2026Q2"])
N["loss_2000_2002_pct_gdp"] = float(100 * (S["2000Q1"] - S["2002Q3"]) / gq_n["2000Q1"])

# ---------------------------------------------------------------- 5. who owns stock (Distributional Financial Accounts)
g = pd.read_csv(DATA / "dfa_corporate_equities_and_mutual_funds_by_wealth.csv", index_col=0)
tot = g.sum(axis=1)
N["dfa_top01_share_2026q2"] = float(100 * g.loc["2026Q2", "TopPt1"] / tot["2026Q2"])
N["dfa_top01_share_1989q3"] = float(100 * g.loc["1989Q3", "TopPt1"] / tot["1989Q3"])
N["dfa_top10_share_2026q2"] = float(100 * (g.loc["2026Q2", ["TopPt1", "RemainingTop1", "Next9"]].sum()) / tot["2026Q2"])

# ---------------------------------------------------------------- 6. the ten richest Americans (Forbes)
fb = pd.read_csv(DATA / "forbes_top10.csv")
N["forbes_top10_2019_bn"] = float(fb["oct_2019_bn"].sum())
N["forbes_top10_2026_bn"] = float(fb["sep_2026_bn"].sum())
N["forbes_top10_gain_tn"] = (N["forbes_top10_2026_bn"] - N["forbes_top10_2019_bn"]) / 1000
N["forbes_3pct_of_avg_gain_bn"] = 0.03 * (N["forbes_top10_2026_bn"] - N["forbes_top10_2019_bn"]) / len(fb)

(OUT / "post_numbers.json").write_text(json.dumps(N, indent=1, default=float))
show = ["bear_declines_since_1946", "bear_recessions_with_decline", "bear_recessions_missed", "bear_declines_since_1980",
        "house_nominal_falls_since_1980", "house_nominal_2007", "house_real_1980", "house_real_1989",
        "house_stock_corr_whole_market_check", "bfi_quarters_falling_2001", "bfi_fall_2000q4_2002q4",
        "pce_worst_four_quarters_2000_2003", "pce_growth_2001_q4q4", "bfi_growth_2001_q4q4", "gdp_growth_1988_q4q4",
        "pce_growth_1988_q4q4", "gdp_growth_1987q3_1988q3", "pce_growth_1987q3_1988q3", "recession_consumer_drag_2001",
        "recession_consumer_drag_median_others", "recession_consumer_share_2001", "recession_consumer_share_median_others",
        "recessions_consumer_less_than_bfi", "stocks_gdp_avg_1952_1995", "stocks_gdp_2000q1", "stocks_gdp_2026q2",
        "foreign_share_2000q1", "foreign_share_2026q2", "household_stock_gdp_2000q1", "household_stock_gdp_2026q2",
        "loss_25pct_today_pct_gdp", "loss_2000_2002_pct_gdp", "dfa_top01_share_2026q2", "dfa_top01_share_1989q3",
        "dfa_top10_share_2026q2", "forbes_top10_gain_tn", "forbes_3pct_of_avg_gain_bn"]
for k in show:
    v = N.get(k)
    print(f"  {k:44s} {v:.2f}" if isinstance(v, float) else f"  {k:44s} {v}")
