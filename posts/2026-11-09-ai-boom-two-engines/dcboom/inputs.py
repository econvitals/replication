"""inputs.py: build the derived inputs (the model's shock and the actual series the table uses) from the
frozen raw data in data/, and check them against the derived files exactly as used for the post
(data/as_used/). Writes output/inputs/inv_excess.csv and output/inputs/actual.csv.

THE SHOCK (inv_excess.csv), quarterly 2015Q1-2026Q4, $ millions at a seasonally adjusted annual rate:
  comp  BEA private fixed investment in computers and peripheral equipment (NIPA 5.5.5U, B935RC)
  comm  BEA private fixed investment in communication equipment (5.5.5U, C275RC)
  dcc   Census private construction put in place, data centers (C30, monthly SAAR, quarterly average)
For each, a log-linear trend is fitted over 2015Q1-2022Q4 and extrapolated; the excess over the trend
counts from 2023Q1 (zero before). Software is excluded. 2026Q4 has no data yet: each series carries its
past year's average quarterly growth one more quarter, and nominal GDP for 2026Q4 is 2026Q3's actual
level times the growth from 2026Q3 to 2026Q4 in the median of the August 2026 Survey of Professional
Forecasters (survey of 2026Q3). inv_excess_share = 100 * (sum of the three excesses) / nominal GDP.

THE ACTUAL SERIES (actual.csv), quarterly 2019Q1-2026Q3, for the table and figure 10:
  rgdp, rpce, rres, rbfi, rex, rim  real GDP, consumer spending, residential and nonresidential fixed
                                    investment, exports, imports ($ trillions, chained 2017 dollars)
  ngdp, nx_share                    nominal GDP ($ trillions) and net exports (percent of GDP)
  pbfi                              implicit price of nonresidential fixed investment (ratio)
  core_pce_index                    PCE price index excluding food and energy (2017 = 100)
  unemp                             unemployment rate, quarterly mean of months (2025Q4 has two months:
                                    the October 2025 household survey was not conducted)
  ffr, t10                          effective federal funds rate and 10-year Treasury yield, quarterly
                                    mean of business days (Federal Reserve H.15)
  dollar                            real broad dollar index, quarterly mean of months (Federal Reserve H.10)
  mort                              30-year fixed mortgage rate, quarterly mean of weeks (Freddie Mac PMMS)
  mktval                            U.S. corporate equity market value at quarter end ($ trillions;
                                    data/stock_gain.csv column M)
"""
import numpy as np
import pandas as pd

from . import paths

TREND = ("2015Q1", "2022Q4")
START = pd.Period("2023Q1", freq="Q")
LAST_DATA = pd.Period("2026Q3", freq="Q")
Q4 = pd.Period("2026Q4", freq="Q")
QIDX = pd.period_range("2015Q1", Q4, freq="Q")


def bea():
    b = pd.read_csv(paths.DATA / "bea_nipa_q.csv", dtype={"quarter": str})
    b.index = pd.PeriodIndex(b.pop("quarter"), freq="Q")
    return b.astype(float)


def c30():
    c = pd.read_csv(paths.DATA / "census_c30_private_sa_m.csv", parse_dates=["month"]).set_index("month")
    return c.apply(pd.to_numeric, errors="coerce")


def fred(name):
    f = pd.read_csv(paths.DATA / "fred_series.csv", parse_dates=["date"])
    s = f[f.series == name].set_index("date")["value"].astype(float)
    return s.sort_index()


def spf_ngdp_ratio(survey=(2026, 3)):
    """Median SPF nominal GDP, 2026Q4 over 2026Q3, from the survey of 2026Q3 (August 2026).
    In that survey NGDP2 is the forecast for the survey quarter (2026Q3) and NGDP3 for the next (2026Q4)."""
    s = pd.read_csv(paths.DATA / "spf_median_ngdp_level.csv")
    r = s[(s.YEAR.astype(int) == survey[0]) & (s.QUARTER.astype(int) == survey[1])].iloc[0]
    return float(r["NGDP3"]), float(r["NGDP2"])


def trend_excess(level, name):
    """Log-linear trend over TREND, extrapolated; excess = level - trend from START (0 before)."""
    y = level.loc[TREND[0]:TREND[1]]
    t = np.array([(q - QIDX[0]).n for q in y.index], float)
    b, a = np.polyfit(t, np.log(y.values), 1)
    tt = np.array([(q - QIDX[0]).n for q in level.index], float)
    tr = pd.Series(np.exp(a + b * tt), index=level.index)
    ex = level - tr
    ex[ex.index < START] = 0.0
    return pd.DataFrame({f"{name}": level, f"{name}_trend": tr, f"{name}_excess": ex,
                         f"{name}_trend_growth": 100 * (np.exp(4 * b) - 1)})


def extend_q4(s):
    """Carry the past year's average quarterly growth one more quarter (2026Q4)."""
    s = s.copy()
    g = (s.loc[LAST_DATA] / s.loc[LAST_DATA - 4]) ** 0.25
    s.loc[Q4] = s.loc[LAST_DATA] * g
    return s.sort_index()


def build_inv_excess(B):
    comp, comm = B["B935RC"], B["C275RC"]
    vip = c30()["Data center"]                                         # $ millions, SAAR, monthly
    vip.index = vip.index.to_period("Q")
    dc = vip.groupby(level=0).mean()
    dc = dc[dc.index <= LAST_DATA]
    frames = []
    for name, s in (("comp", comp), ("comm", comm), ("dcc", dc)):
        s = extend_q4(s.loc["2015Q1":LAST_DATA])
        frames.append(trend_excess(s.reindex(QIDX), name))
    df = pd.concat(frames, axis=1)
    df["inv_excess"] = df[["comp_excess", "comm_excess", "dcc_excess"]].sum(axis=1)
    df["bea_dc_structures"] = B["LA001282"].reindex(QIDX)            # cross-check of the Census line
    ngdp = B["A191RC"].reindex(QIDX)
    n4, n3 = spf_ngdp_ratio()
    ngdp.loc[Q4] = (B.loc[LAST_DATA, "A191RC"] / 1e6 * n4 / n3) * 1e6  # same operation order as the original
    df["ngdp"] = ngdp
    df["inv_excess_share"] = 100 * df["inv_excess"] / df["ngdp"]
    df.index.name = "quarter"
    return df


def quarterly_mean(s, min_obs=1):
    s = s.dropna()
    g = s.groupby(s.index.to_period("Q"))
    m = g.mean()
    return m[g.count() >= min_obs]


def build_actual(B):
    idx = pd.period_range("2019Q1", LAST_DATA, freq="Q")
    out = pd.DataFrame(index=idx)
    out["rgdp"] = B["A191RX"] / 1e6
    out["ngdp"] = B["A191RC"] / 1e6
    out["nx_share"] = 100 * B["A019RC"] / B["A191RC"]
    out["rres"] = B["A011RX"] / 1e6
    out["rpce"] = B["DPCERX"] / 1e6
    out["rbfi"] = B["A008RX"] / 1e6
    out["pbfi"] = B["A008RC"] / B["A008RX"]
    out["rex"] = B["A020RX"] / 1e6
    out["rim"] = B["A021RX"] / 1e6
    out["core_pce_index"] = B["DPCCRG"]
    out["core4"] = 100 * (B["DPCCRG"] / B["DPCCRG"].shift(4) - 1)
    out["unemp"] = quarterly_mean(fred("UNRATE"), min_obs=2)
    out["ffr"] = quarterly_mean(fred("EFFR"))
    out["t10"] = quarterly_mean(fred("DGS10"))
    out["dollar"] = quarterly_mean(fred("RTWEXBGS"))
    out["mort"] = quarterly_mean(fred("MORTGAGE30US"))
    st = pd.read_csv(paths.DATA / "stock_gain.csv")
    st = st[st["quarter"].astype(str).str.fullmatch(r"\d{4}Q[1-4]")]
    st["q"] = pd.PeriodIndex(st["quarter"], freq="Q")
    st = st.drop_duplicates("q", keep="last").set_index("q")
    out["mktval"] = (st["M"] / 1e3).reindex(idx)                      # stock_gain.csv is in $ billions
    out.index.name = "quarter"
    return out


def check_against_as_used(inv, act):
    """The rebuilt inputs must equal the derived files used for the post (only when running on data/)."""
    worst = {}
    u = pd.read_csv(paths.AS_USED / "inv_excess.csv", index_col=0)
    u.index = pd.PeriodIndex(u.index, freq="Q")
    for c in ["comp", "comm", "dcc", "comp_excess", "comm_excess", "dcc_excess", "inv_excess", "ngdp", "inv_excess_share"]:
        worst[f"inv_excess.{c}"] = float(np.nanmax(np.abs(inv[c].values - u.loc[inv.index, c].values) /
                                                   np.maximum(1.0, np.abs(u.loc[inv.index, c].values))))
    a = pd.read_csv(paths.AS_USED / "actual.csv", index_col=0)
    a.index = pd.PeriodIndex(a.index, freq="Q")
    e = pd.read_csv(paths.AS_USED / "actual_extra.csv", index_col=0)
    e.index = pd.PeriodIndex(e.index, freq="Q")
    q = act.index
    for c in ["rgdp", "ngdp", "nx_share", "rres", "rpce", "core4", "unemp", "ffr", "t10", "dollar"]:
        worst[f"actual.{c}"] = float(np.nanmax(np.abs(act[c].values - a.loc[q, c].values)))
    for c in ["rbfi", "pbfi", "rex", "rim", "mort", "mktval"]:
        worst[f"actual_extra.{c}"] = float(np.nanmax(np.abs(act[c].values - e.loc[q, c].values)))
    bad = {k: v for k, v in worst.items() if not v < 1e-9}
    return worst, bad


def main():
    paths.ensure()
    B = bea()
    inv = build_inv_excess(B)
    act = build_actual(B)
    inv.to_csv(paths.OUT_INPUTS / "inv_excess.csv")
    act.to_csv(paths.OUT_INPUTS / "actual.csv")
    print(f"inputs: data-center investment above trend, 2026Q3 = {inv.loc[LAST_DATA, 'inv_excess_share']:.4f} percent of GDP; "
          f"2026Q4 (extrapolated) = {inv.loc[Q4, 'inv_excess_share']:.4f}")
    if paths.using_frozen_data():
        worst, bad = check_against_as_used(inv, act)
        if bad:
            raise SystemExit(f"inputs: the rebuilt inputs differ from the ones used for the post: {bad}")
        print(f"inputs: rebuilt inputs match the post's (largest difference {max(worst.values()):.1e})")
    else:
        print("inputs: running on refreshed data; no comparison with the post's inputs")


if __name__ == "__main__":
    main()
