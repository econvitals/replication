"""Term Premium — rebuilds our estimate of the term premium by the Adrian–Crump–Moench method, the
third layer of the Interest Rate Decomposer (econvitals.org/tools/interest-rate-decomposer/).

    python replicate.py              # the United States, Germany, Japan and Canada; keyless
    python replicate.py us           # one economy (us, de, jp or ca)

A bond yield is what investors expect short rates to average over the bond's life (the expected
policy path) plus extra pay for holding a long bond (the term premium). The method, on each
economy's own curve of zero-coupon yields at maturities of 1 to 120 months:

  1. the five principal components of the monthly (end-of-month) curve are the pricing factors;
  2. a VAR(1) on the factors gives their one-step-ahead forecasts and the forecast errors;
  3. one-month excess returns on bonds of 6, 12, ..., 120 months are regressed on a constant, the
     forecast errors and the lagged factors (the three-step regressions);
  4. the prices of risk come from those coefficients, and bond prices follow from the standard
     recursion twice: with the prices of risk (fitted yields) and without (risk-neutral yields).

The model is re-estimated once a month; each day's values apply the month's coefficients to that
day's curve. The term premium is the OBSERVED yield minus the risk-neutral yield, so the two
pieces add up to the yield exactly; the expected policy path is the risk-neutral yield.

Writes output/<cc>.csv (yields, path and premium at 2, 5, 10 and 30 years, daily) and, for the
nightly comparison, output/site_<cc>.csv (the same columns from the published files). France, Italy
and the euro area carry Germany's model plus their spread over Germany on the site; the United
Kingdom's own fit is not rebuilt here (see the README).
"""
import datetime as dt
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import get, save  # noqa: E402
from common.rates import gsw_parameters, published_anywhere, svensson  # noqa: E402

MONTHS = np.arange(1, 121)                   # the model's maturities, in months
GRID = list(MONTHS) + [180, 240, 360]        # 15, 20 and 30 years are priced by the recursion
TENORS = {"2y": 24, "5y": 60, "10y": 120, "30y": 360}
K = 5                                        # five factors
RX_MATS = list(range(6, 121, 6))             # maturities whose excess returns are regressed
FIT_START = {"us": "1961-06-01", "de": "1997-08-01", "ca": "1986-01-01", "jp": "1990-01-01",
             "uk": "1979-01-01"}
NAMES = {"us": "United States", "de": "Germany", "ca": "Canada", "jp": "Japan",
         "uk": "United Kingdom"}


# ---------------------------------------------------------------- small curve arithmetic
def par_to_zero(par, freq):
    """Zero-coupon yields (percent, continuously compounded) from par yields {years: percent} by
    bootstrapping, par yields interpolated linearly to every coupon date; `freq` coupons a year."""
    pts = sorted((m, v) for m, v in par.items() if v is not None and not math.isnan(v) and m > 0)
    xs, ys = [m for m, _ in pts], [v for _, v in pts]
    out, cum = {}, 0.0
    for i in range(1, int(round(xs[-1] * freq)) + 1):
        t = i / freq
        c = float(np.interp(t, xs, ys)) / 100 / freq
        df = (1 - c * cum) / (1 + c)
        if df <= 0:
            break
        cum += df
        out[t] = -100 * math.log(df) / t
    return out


def on_grid(points):
    """A sparse {years: yield} curve on the monthly grid: linear in maturity, flat below the
    shortest point, blank beyond the longest."""
    xs = np.array(sorted(points))
    ys = np.array([points[x] for x in xs])
    return [float(ys[0]) if m / 12 < xs[0] else (np.nan if m / 12 > xs[-1] else
            float(np.interp(m / 12, xs, ys))) for m in GRID]


def par_tail(curve, par, freq, min_points):
    """Days after an official curve's last row, from a same-day par curve bootstrapped to zeros and
    shifted, maturity by maturity, by the average official-minus-bootstrap gap over the last 20
    days the two share, so the tail joins the official curve without a step."""
    boot = {}
    for day, row in par.iterrows():
        pts = {t: v for t, v in row.items() if pd.notna(v)}
        if len(pts) >= min_points:
            boot[day] = on_grid(par_to_zero(pts, freq))
    boot = pd.DataFrame(boot, index=GRID).T.sort_index()
    overlap = [d for d in curve.index[-20:] if d in boot.index]
    if len(overlap) < 5:
        return curve
    gap = (curve.loc[overlap] - boot.loc[overlap]).mean()
    tail = boot[boot.index > curve.index[-1]] + gap
    return pd.concat([curve, tail])


# ---------------------------------------------------------------- each economy's zero curve
TREASURY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve"
            "&field_tdr_date_value={y}&page&_format=csv")
UST_TENORS = {"1 Mo": 1 / 12, "2 Mo": 2 / 12, "3 Mo": 0.25, "4 Mo": 4 / 12, "6 Mo": 0.5,
              "1 Yr": 1, "2 Yr": 2, "3 Yr": 3, "5 Yr": 5, "7 Yr": 7, "10 Yr": 10, "20 Yr": 20,
              "30 Yr": 30}


def curve_us():
    """The Federal Reserve Board's zero curve (Gürkaynak, Sack and Wright), from its daily Svensson
    parameters. The Board updates the file weekly, so the days after its last row come from
    Treasury's same-day par curve, joined as `par_tail` describes."""
    p = gsw_parameters()
    curve = pd.DataFrame(svensson(p.values[:, None, :], np.array(GRID) / 12), index=p.index,
                         columns=GRID)
    since = curve.index[-1] - pd.DateOffset(days=45)
    frames = []
    for year in range(since.year, dt.date.today().year + 1):
        df = pd.read_csv(io.StringIO(get(TREASURY.format(y=year))))
        df.index = pd.to_datetime(df.pop("Date"), format="%m/%d/%Y")
        frames.append(df[[c for c in UST_TENORS if c in df.columns]].rename(columns=UST_TENORS))
    par = pd.concat(frames).sort_index()
    return par_tail(curve, par[par.index >= since], freq=2, min_points=8)


def curve_de():
    """The Bundesbank's zero curve for listed Federal securities (Bunds), from its six daily
    Svensson parameters; Germany's model is the euro-area model on the site."""
    params = pd.DataFrame({p: bundesbank_series(f"D.I.ZST.{p}.EUR.S1311.B.A604._Z.R.A.A._Z._Z.A")
                           for p in ("B0", "B1", "B2", "B3", "T1", "T2")}).dropna()
    return pd.DataFrame(svensson(params.values[:, None, :], np.array(GRID) / 12),
                        index=params.index, columns=GRID)


def bundesbank_series(key):
    """One daily series from the Bundesbank's statistics API; metadata rows above the data are
    skipped by shape and "." (no value) is dropped."""
    text = get(f"https://api.statistiken.bundesbank.de/rest/data/BBSIS/{key}",
               {"format": "csv", "lang": "en"}, timeout=120)
    df = pd.read_csv(io.StringIO(text.lstrip("\ufeff")), header=None, usecols=[0, 1], dtype=str)
    dates = pd.to_datetime(df[0], format="%Y-%m-%d", errors="coerce")
    s = pd.Series(pd.to_numeric(df[1], errors="coerce").values, index=dates)
    return s[s.index.notna()].dropna()


MOF = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"


def curve_jp():
    """Japan's Ministry of Finance par yield curve (1-10, 15, 20, 25, 30 and 40 years; the history
    file and the current month's file), bootstrapped to zero-coupon yields with annual coupons and
    held flat below one year, MoF's shortest maturity."""
    frames = []
    for url in (MOF + "historical/jgbcme_all.csv", MOF + "jgbcme.csv"):
        df = pd.read_csv(io.StringIO(get(url, timeout=120)), skiprows=1, index_col=0, dtype=str)
        df.index = pd.to_datetime(df.index, format="%Y/%m/%d", errors="coerce")
        frames.append(df[df.index.notna()].apply(pd.to_numeric, errors="coerce"))
    par = pd.concat(frames)
    par = par[~par.index.duplicated(keep="last")].sort_index()
    par.columns = [float(c.strip().rstrip("Y")) for c in par.columns]
    rows = {}
    for day, row in par.iterrows():
        pts = {t: v for t, v in row.items() if pd.notna(v)}
        if 1.0 in pts and 10.0 in pts:
            rows[day] = on_grid(par_to_zero(pts, freq=1))
    return pd.DataFrame(rows, index=GRID).T


BOC_BENCHMARKS = {"TB.CDN.90D.MID": 0.25, "TB.CDN.1Y.MID": 1, "BD.CDN.2YR.DQ.YLD": 2,
                  "BD.CDN.3YR.DQ.YLD": 3, "BD.CDN.5YR.DQ.YLD": 5, "BD.CDN.7YR.DQ.YLD": 7,
                  "BD.CDN.10YR.DQ.YLD": 10, "BD.CDN.LONG.DQ.YLD": 30}


def curve_ca():
    """The Bank of Canada's zero-coupon curve (every quarter-year from 3 months to 30 years, one CSV
    since 1986, in decimals), linear between the Bank's points and flat below three months. The
    file runs about two weeks behind, so the days after its last row come from the Bank's daily
    benchmark bond and bill yields (Valet), joined as `par_tail` describes."""
    text = get("https://www.bankofcanada.ca/stats/results/csv",
               {"lookupPage": "lookup_yield_curve.php", "startRange": "1986-01-01",
                "rangeType": "dates", "dFrom": "1986-01-01", "dTo": dt.date.today().isoformat(),
                "rangeValue": "1", "ByDate_frequency": "daily", "submit_button": "Submit"},
               timeout=300)
    df = pd.read_csv(io.StringIO(text), index_col=0, na_values=["na", "n/a", "."])
    df = df.loc[:, [c for c in df.columns if str(c).strip().upper().startswith("ZC")]]
    df.columns = [int(str(c).strip().upper()[2:-2]) / 100 for c in df.columns]   # ZC025YR -> 0.25
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()].apply(pd.to_numeric, errors="coerce").dropna(how="all") * 100
    curve = pd.DataFrame({day: on_grid({t: v for t, v in row.items() if pd.notna(v)})
                          for day, row in df.iterrows()}, index=GRID).T
    since = (curve.index[-1] - pd.DateOffset(days=45)).strftime("%Y-%m-%d")
    obs = json.loads(get("https://www.bankofcanada.ca/valet/observations/" + ",".join(BOC_BENCHMARKS)
                         + "/json", {"start_date": since}))["observations"]
    par = pd.DataFrame({pd.Timestamp(o["d"]): {t: float(o[c]["v"]) for c, t in BOC_BENCHMARKS.items()
                                               if (o.get(c) or {}).get("v") not in (None, "")}
                        for o in obs}).T.sort_index()
    return par_tail(curve, par, freq=2, min_points=6)


CURVES = {"us": curve_us, "de": curve_de, "jp": curve_jp, "ca": curve_ca}


# ---------------------------------------------------------------- the model
def end_of_month(curve, start, end):
    """The last available day of each month from `start` to `end`, maturities 1-120 months."""
    c = curve.loc[start:end, list(MONTHS)].dropna()
    return c.groupby(c.index.to_period("M")).tail(1)


def fit(monthly):
    """The three-step regressions on monthly zero yields (T x 120, percent). Returns everything
    needed to price any day's curve."""
    Y = monthly.values / 100                        # decimal, annual, continuously compounded
    T, N = Y.shape
    n = np.arange(1, N + 1)
    mean = Y.mean(axis=0)
    w, V = np.linalg.eigh((Y - mean).T @ (Y - mean) / T)
    W = V[:, np.argsort(w)[::-1][:K]]
    W = W * np.where(W.sum(axis=0) < 0, -1, 1)      # sign: loadings that sum to a positive number
    X = (Y - mean) @ W                              # the five factors, T x K
    # step 1: a VAR(1) on the factors
    Z = np.hstack([np.ones((T - 1, 1)), X[:-1]])
    coef = np.linalg.lstsq(Z, X[1:], rcond=None)[0]
    mu, Phi = coef[0], coef[1:].T
    v = X[1:] - Z @ coef                            # forecast errors
    Sigma = v.T @ v / (T - 1)
    # step 2: one-month excess returns on the n-month bond, regressed on [1, v, lagged X]
    logp = -(n / 12) * Y
    r = Y[:, 0] / 12
    rx = np.column_stack([logp[1:, m - 2] - logp[:-1, m - 1] - r[:-1] for m in RX_MATS])
    Z2 = np.hstack([np.ones((T - 1, 1)), v, X[:-1]])
    c2 = np.linalg.lstsq(Z2, rx, rcond=None)[0]
    a, beta, c = c2[0], c2[1:1 + K], c2[1 + K:]
    e = rx - Z2 @ c2
    sigma2 = float((e ** 2).sum() / e.size)
    # step 3: the prices of risk
    BB = beta @ beta.T
    Bstar = np.array([np.outer(beta[:, i], beta[:, i]).ravel() for i in range(beta.shape[1])])
    lam0 = np.linalg.solve(BB, beta @ (a + 0.5 * (Bstar @ Sigma.ravel() + sigma2)))
    lam1 = np.linalg.solve(BB, beta @ c.T)
    # the short rate on the factors
    d = np.linalg.lstsq(np.hstack([np.ones((T, 1)), X]), r, rcond=None)[0]
    d0, d1 = d[0], d[1:]

    def recursion(l0, l1):
        A, B = np.zeros(361), np.zeros((361, K))
        for m in range(1, 361):
            A[m] = A[m - 1] + B[m - 1] @ (mu - l0) + 0.5 * (B[m - 1] @ Sigma @ B[m - 1] + sigma2) - d0
            B[m] = B[m - 1] @ (Phi - l1) - d1
        return A[1:], B[1:]

    AP, BP = recursion(lam0, lam1)                  # with the prices of risk
    AQ, BQ = recursion(np.zeros(K), np.zeros((K, K)))   # risk neutral
    return {"mean": mean, "W": W, "AP": AP, "BP": BP, "AQ": AQ, "BQ": BQ, "n_months": T}


def decompose(coef, curve):
    """Daily yields, expected policy path (risk-neutral yield) and term premium at four tenors."""
    X = (curve[list(MONTHS)].values / 100 - coef["mean"]) @ coef["W"]
    out = pd.DataFrame(index=curve.index)
    for name, m in TENORS.items():
        rn = -(12 / m) * (coef["AQ"][m - 1] + X @ coef["BQ"][m - 1]) * 100
        out[f"yield_{name}"] = curve[m]
        out[f"path_{name}"] = rn
        out[f"premium_{name}"] = curve[m] - rn
    return out


# ---------------------------------------------------------------- run
index = published_anywhere("tools/interest-rate-decomposer/data/index.json")
samples = {e["cc"]: e.get("model_sample") for e in index["economies"]}
todo = [a for a in sys.argv[1:] if a in CURVES] or list(CURVES)
for cc in todo:
    curve = CURVES[cc]()
    # Re-estimated once a month. To rebuild what the site shows today, fit on the same months as
    # the site's current fit (its sample is in the published index); without one, use every month.
    end = (samples.get(cc) or [None, curve.index[-1].strftime("%Y-%m-%d")])[1]
    monthly = end_of_month(curve, FIT_START[cc], end)
    coef = fit(monthly)
    result = decompose(coef, curve)
    result.index.name = "date"
    save(result.round(6), HERE, cc)
    print(f"{NAMES[cc]}: fit on {coef['n_months']} months, {monthly.index[0].date()} to "
          f"{monthly.index[-1].date()}; daily through {curve.index[-1].date()}")
    print(result[["yield_10y", "path_10y", "premium_10y"]].tail(3).round(3).to_string())

    # The published series, laid out flat for the nightly comparison (the last two years). Days
    # after the official curve's last row (the U.S. and Canadian tails) are left out: the site
    # rebuilds them every evening, and the two runs can see different weeks of the official file.
    pub = published_anywhere(f"tools/interest-rate-decomposer/data/{cc}.json")
    flat = pd.DataFrame({f"{piece}_{t}": pub[piece][t]
                         for piece in ("yield", "path", "premium") for t in TENORS},
                        index=pd.to_datetime(pub["dates"]))
    flat.index.name = "date"
    official = (pub.get("meta") or {}).get("official_last")
    if official:
        flat = flat[flat.index <= official]
    save(flat[flat.index >= flat.index[-1] - pd.DateOffset(years=2)], HERE, f"site_{cc}")
