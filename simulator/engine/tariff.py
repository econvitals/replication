"""The tariff construction: how a tariff on non-oil imports enters FRB/US. build.py's tariff shock calls channels().

Who pays the duty E (the incidence assumption, 2026-11-08): consumers half, through consumer prices; businesses buying
equipment half of the duty on capital goods, through the price of investment; company profits the rest -- so companies
bear half in all, and a lasting tariff lowers GDP in the long run.
  revenue  E, $ billions at an annual rate, is booked as what it is, federal customs receipts: the residual receipts
           line (gfrecn_aerr) and the surplus (gfsrpn_aerr) move by E.
  prices   the consumer price level moves by L = log(1 + PASS_THROUGH x E / consumer spending), with E spread over
           three quarters (LAG_WEIGHTS: the Fed staff's finding that about half of a tariff reaches consumer prices in
           three months and all of it in about seven). PASS_THROUGH, the share of the duties that ends up in consumer
           prices, is calibrated so the model's effect of the 2025-26 tariffs on core PCE inflation matches published
           estimates (below). Two add factors do it: the desired consumer price level (`qpcnia`) moves by L, and core
           inflation (`picxfe_aerr`) by enough to move the price level by L on that schedule, net of the inflation
           equation's own momentum and expectations (inflation_add). `qpcnia` alone would not do: FRB/US closes a gap
           between actual and desired consumer prices very slowly (a 1.3 percent move in the desired level moved core
           PCE prices 0.1 percent after a year).
  equipment  the price of business investment relative to output (the user-cost price pkbfir*pxp/pxb) is held on its
           own path (PBFIR_EQUATION replaces the pbfir equation) and moved by Lk = log(1 + EQUIPMENT_PASS_THROUGH x
           CAPITAL_SHARE x E / nominal business investment), on the same schedule: half of the duty on imported capital
           goods reaches what businesses pay for equipment. Holding the price on its path matters as much as the shift:
           left alone, pbfir is measured against the output price pxp, which the consumer-price add factors push up, so
           the tariff LOWERED the relative price of investment about 2 percent, raised business investment 2.8 percent
           and turned a lasting tariff's ten-year GDP effect positive (found 2026-11-08).
  profits  corporate profits (ynicpn_aerr) move by PROFIT_SHARE x E, the part of the duty passed on to nobody.
  imports  FRB/US's import equation for non-oil goods and services pulls the dollar value of imports toward a trend
           share of GDP through the lagged import price `pmo`. The tariff-inclusive price is pmo x (1 + w), with
           w = E / non-oil imports (`emon`); a tariff adds y_emo_2 x log(1 + w(-1)) to that equation's residual --
           exactly the change the tariff-inclusive price would make there. `pmo` itself is left alone: it is BEA's import
           price measured before duties, and moving it also changes the dollar value of imports, which the model books
           against domestic income, counting the duty twice.

The model must be built with capital_price=True (build.make_model: the pbfir equation replaced by PBFIR_EQUATION) and
the frame must come from prepare(). channels() takes a sign, so the same construction puts a tariff in (+1) or takes
one out of history (-1).
"""
import functools
import math

import pandas as pd

from engine_paths import FED       # the Board's packages (engine_paths.py; FRBUS_FED overrides)

# The share of the duties that reaches consumer prices (consumers pay PASS_THROUGH x E more), calibrated in
# backward-looking runs of the 2025-26 tariffs with the Fed on its actual path so the model's effect on core PCE
# inflation over the four quarters to 2026Q1 is about 0.6 point -- the middle of the published range (Federal Reserve
# Board staff, 0.8 percent on the core PCE price level through February 2026, 0.4 without time effects; Chair Powell,
# March 2026, "between a half and three-quarters" of about 3 percent core inflation; St. Louis Fed, 0.4 point of
# annualized core PCE inflation over June-August 2025; Minneapolis Fed, 0.2 to 0.4 point as of July 2026). Measured
# 2026-11-07: 0.63 point backward-looking, 0.70 forward-looking; peak 0.64 / 0.71 in 2025Q4. Forward-looking under the
# rules of 2026-11-08 (200 quarters, r* learning): 0.71, peak 0.72.
PASS_THROUGH = 0.5
# Capital goods' share of the duties (Census end-use, imports for consumption, read 2026-11-08): capital goods except
# automotive were 29.2% of 2024 goods imports and 27.8% of the extra duties collected January 2025 - September 2026 over
# the 2024 rate (their own rate was 2.0% in 2024).
CAPITAL_SHARE = 0.29
EQUIPMENT_PASS_THROUGH = 0.5            # the share of the duty on capital goods that reaches equipment prices, as for consumers
PROFIT_SHARE = 1 - PASS_THROUGH - EQUIPMENT_PASS_THROUGH * CAPITAL_SHARE     # 0.355: passed on to nobody, out of profits
# The relative price of business investment (pbfir, measured against pxp) on its own path: while dpbfix = 1 the user-cost
# relative price pkbfir*pxp/pxb = (upkbfir*) pbfir*pxp/pxb stays on rkbase, its path in the data, times exp(lkbfi).
PBFIR_EQUATION = ("log(pbfir) - pbfir_aerr = (1-dpbfix)*(log(pbfir(-1)) + pipxnc/400 + dpadj - (log(pxp) - log(pxp(-1))))"
                  " + dpbfix*(log(rkbase) + lkbfi + log(pxb) - log(pxp))")
# The timing of pass-through to consumer prices (Minton, Ray and Somale 2026: about half three months after a tariff
# change, all of it after about seven): the share of a quarter's duties that has reached prices in that quarter and the
# next two (a quarter, then 70 percent, then all of it, for a tariff that starts at the beginning of a quarter).
LAG_WEIGHTS = (0.25, 0.45, 0.30)


def prepare(d):
    """The series PBFIR_EQUATION reads, added to a copy of the data: rkbase (the data's own user-cost relative price),
    dpbfix = 1, lkbfi = 0."""
    d = d.copy()
    d["rkbase"] = (d["pbfir"] * d["pxp"] / d["pxb"]).values
    d["dpbfix"] = 1.0
    d["lkbfi"] = 0.0
    return d


@functools.lru_cache(maxsize=None)
def _coef(name):
    """One equation's coefficients from the Board's model.xml (the same file build.py reads)."""
    import xml.etree.ElementTree as ET
    for v in ET.parse(FED / "pyfrbus" / "models" / "model.xml").getroot().findall("variable"):
        if (v.findtext("name") or "").strip() == name:
            return {c.findtext("cf_name").replace("(", "_").replace(")", ""): float(c.findtext("cf_value")) for c in v.iter("coeff")}
    raise KeyError(name)


def price_shift(e, frame, pt=None):
    """L, the move in the log consumer price level from a tariff whose duties are `e`: PASS_THROUGH x the duties, spread
    over LAG_WEIGHTS, as a share of consumer spending (ecnian)."""
    pt = PASS_THROUGH if pt is None else pt
    lagged = sum(w * e.shift(k).fillna(0.0) for k, w in enumerate(LAG_WEIGHTS))
    return (pt * lagged / frame.loc[e.index, "ecnian"]).map(math.log1p)


def inflation_add(L, forward=False):
    """The core inflation add factor (picxfe_aerr, annualized points) that moves the core price level by L on schedule,
    net of the inflation equation's own momentum and its expectation of next quarter's inflation, with everything else
    held at the baseline. Backward-looking, that expectation is FRB/US's VAR forecast (zpicxfe, four lags of inflation);
    forward-looking, it is next quarter's inflation itself, so the factor is netted against the quarter ahead rather
    than the quarters behind (a backward-looking factor in a forward-looking run doubled the price effect and brought it
    forward a year). The desired price level moves by L too (qpcnia_aerr), so the equation's pull toward it is unchanged."""
    cx, cz = _coef("picxfe"), _coef("zpicxfe")
    y1, y3 = cx["y_picxfe_1"], cx["y_picxfe_3"]
    dpi = -400 * (L - L.shift(1).fillna(0.0))           # the wanted change in core inflation, quarter by quarter
    lag = lambda j: dpi.shift(j).fillna(0.0)
    if forward:
        expected = lag(-1)
    else:
        expected = sum(cz[f"y_zpicxfe_{j}"] * lag(j) for j in (1, 2, 3, 4))
    return dpi - (y1 * lag(1) + y3 * expected) / (1 + y1 * y3)


def channels(s, wa, e, sign, forward):
    """Put a tariff in (sign = +1) or take one out (sign = -1): E = `e`, $ billions at an annual rate, indexed from the
    first quarter of the change through the end of the solve (zero where no duty is collected). `forward` =
    forward-looking expectations (the core-inflation add factor is netted against the quarter ahead). Needs the model
    built with capital_price=True and the frame from prepare()."""
    idx = e.index
    # revenue: federal customs receipts
    s.loc[idx, "gfrecn_aerr"] = s.loc[idx, "gfrecn_aerr"].values + sign * e.values
    s.loc[idx, "gfsrpn_aerr"] = s.loc[idx, "gfsrpn_aerr"].values + sign * e.values
    # profits: the part of the duty passed on to nobody
    s.loc[idx, "ynicpn_aerr"] = s.loc[idx, "ynicpn_aerr"].values - sign * PROFIT_SHARE * e.values
    # consumer prices: the desired level moves by L, and core inflation by enough to get there on schedule
    L = price_shift(e, wa)
    s.loc[idx, "qpcnia_aerr"] = s.loc[idx, "qpcnia_aerr"].values + sign * L.values
    s.loc[idx, "picxfe_aerr"] = s.loc[idx, "picxfe_aerr"].values - sign * inflation_add(L, forward=forward).values
    # equipment prices: the duty on capital goods passed on to businesses that invest, same schedule
    lag = sum(w * (CAPITAL_SHARE * e).shift(k).fillna(0.0) for k, w in enumerate(LAG_WEIGHTS))
    s.loc[idx, "lkbfi"] = s.loc[idx, "lkbfi"].values + sign * (EQUIPMENT_PASS_THROUGH * lag / wa.loc[idx, "ebfin"]).map(math.log1p).values
    # imports: the tariff-inclusive price in the import equation, a quarter later
    w = (e / wa.loc[idx, "emon"]).map(math.log1p)
    nxt = pd.period_range(idx[0] + 1, idx[-1], freq="Q")
    s.loc[nxt, "emo_aerr"] = s.loc[nxt, "emo_aerr"].values + sign * _coef("emo")["y_emo_2"] * w.loc[nxt - 1].values
