"""Per-component translation: monthly source data -> the quarter's indicator growth (or contribution).

    from engine import components as C
    v = C.View("2026-10-18")                    # what the sources had published by that day
    C.indicator("pce_goods", pd.Period("2026Q3"), v)   # {'value': 2.9, 'months': 3, 'filled': [...]}
    C.history("equipment")                      # complete-data indicator for every past quarter

THE TEN COMPONENTS:
  pce_goods     BEA's monthly real PCE goods; months BEA has not printed yet extended by retail
                sales less food services, deflated by a CPI goods composite (corr 0.92 with real
                PCE goods month to month, 2012-2026); later months on the 12-month trend.
  pce_services  BEA's monthly real PCE services; later months on the trailing-12-month trend,
                moved by aggregate weekly hours in private service-providing industries (BLS)
                where the jobs report has them (SVC_HOURS; real-time back-test 2026-10-19: last
                day 0.931 vs 0.942, services' own miss 0.365 vs 0.373 pp).
  equipment     two regressors, BEA's commodity flow in miniature: `indicator` = core capital
                goods shipments (full M3, extended by the advance report) deflated by the PPI for
                private capital equipment, and `imports` = imports of capital goods except autos
                (Census end use, seasonally adjusted here, month 3 moved by the advance goods
                report) deflated by their import price index — imported computers and chips are
                equipment investment, and without them the import surge of 2026 read as a pure
                trade drag (R² 0.59 against 0.45, 2013-2026). The import series starts in 2013;
                a bridge with fewer than bridge.MIN_OBS quarters of it fits on shipments alone.
                Later months on the 12-month trend. Tested and rejected 2026-10-19:
                BEA's unit sales of light
                vehicles and heavy trucks, here and in the goods extension — a better fit to the
                revised history (R² 0.70) but a worse real-time back-test (last day 1.005 vs 0.942).
  structures    private nonresidential construction spending, NOMINAL — the bridge's intercept
                carries average inflation (deflating by the PPI for construction inputs, a
                commodity index, made the fit worse: R² 0.34 against 0.60 nominal, 2012-2026);
                later months on the 12-month trend. The Baker Hughes rig count, for the oil and
                gas wells VIP leaves out, was a second regressor 2026-10-19 to 10-28 and is gone:
                the publisher blocks scripted downloads and EIA's copy runs months behind.
  residential   private residential construction spending's nominal growth less the trend of
                BEA's own residential deflator (the mean of its last four published quarters;
                R² 0.44 against 0.37 with the construction-inputs PPI); later months
                on the 12-month trend. Tested and rejected
                2026-10-19: housing starts (no gain) and new-home sales (real-time last day 0.944
                vs 0.942). Existing-home sales, which drive brokers' commissions, are NAR's and not
                published in a free, machine-readable form.
  ipp, federal  the mean of the last four published quarterly growth rates (the README's
                "trend" fill). Tested and rejected for federal (2026-10-19): the Treasury
                statement's defense outlays (correlation 0.03 with BEA's federal growth — payment
                timing swamps them) and federal payrolls (worse out of sample).
  state_local   the same trend PLUS state and local payrolls (BLS) and public construction
                spending (Census, via FRED), each's quarterly growth with missing months held
                (R² 0.78 against 0.32 for the trend alone, 2012-2026).
  inventories   CONTRIBUTION, from two regressors: `indicator` = the quarter's real change in
                book values as a share of GDP (manufacturing from the full M3, month 3 from the
                advance durables report with nondurables held; wholesale and retail from the full
                reports, month 3 from the advance indicators report; deflated by the PPI for
                finished goods less food and energy at the prior quarter's prices) and `anchor` =
                BEA's own real inventory change in the last quarter it has published, as a share
                of real GDP. The contribution is a change in the change, so knowing where BEA left
                the level matters as much as the books: R² 0.46 with the anchor against 0.10
                without (2012-2026; the all-goods PPI, energy included, gave 0.37).
  net_exports   CONTRIBUTION from the change in real net exports: BOP goods and services less
                nonmonetary gold (HS 7108 + 7115, NSA, trailing three-month mean), deflated by the
                import and export price indexes at the prior quarter's prices; month 3 goods moved
                by the advance goods report, services held.

Each component's `x` is a dict of regressors for its bridge (`indicator`, plus `anchor` for
inventories); `value` is the indicator. Quarterly growth = (mean of the quarter's three monthly
levels / mean of the prior quarter's)^4 - 1, in percent. Contributions are in percentage points at an annual rate, scaled to nominal GDP of
the prior quarter. A month a source has not published is FILLed by the component's rule (FILL):
"hold" (carry the last level), "trend12" (the trailing-twelve-month mean monthly growth).

`View(asof)` truncates every monthly source to the last month `calendar.available_through` says
its report had printed by `asof` (None = everything on hand, the live run). Quarterly BEA data
count as known once the quarter's advance estimate is out. That is current-vintage data: a month's
VALUE is today's, only its AVAILABILITY is real-time (the first pass).

`View(asof, vintage=True)` is the real-time pass: every source with an ALFRED twin
(`vintages.TWINS`) is read exactly as it stood on `asof` — values and the months available both —
and BEA's printed growth rates, contributions and inventory levels likewise (the bridges' targets,
the trends and the inventory anchor). Sources without a twin, and any day before a twin's first
vintage, fall back to the first pass's rule. The current-dollar shares and the residential
deflator trend stay on today's figures (`current_quarterly`): they move little with revisions,
and mixing a vintage real series with today's nominal one would make the deflator noise.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import calendar as cal
from . import sources as S
from . import vintages as V

COMPONENTS = ("pce_goods", "pce_services", "equipment", "ipp", "structures", "residential",
              "federal", "state_local", "inventories", "net_exports")
CONTRIBUTIONS = ("inventories", "net_exports")
#: what BEA prints for each component — the target of its bridge
TARGET = {"pce_goods": "pce_goods_growth", "pce_services": "pce_services_growth",
          "equipment": "equipment_growth", "ipp": "ipp_growth", "structures": "structures_growth",
          "residential": "residential_growth", "federal": "federal_growth",
          "state_local": "state_local_growth", "inventories": "contrib_inventories",
          "net_exports": "contrib_net_exports"}
#: current-dollar level for each growth component's share of GDP
NOMINAL = {"pce_goods": "nominal_pce_goods", "pce_services": "nominal_pce_services",
           "equipment": "nominal_equipment", "ipp": "nominal_ipp", "structures": "nominal_structures",
           "residential": "nominal_residential", "federal": "nominal_federal",
           "state_local": "nominal_state_local"}
#: how a month not yet published is filled. The growth lines carry their trailing-12-month trend
#: (real-time back-test 2026-10-19 against holding the last level: 61+ days 1.63 vs 1.76, 31-60
#: days 1.43 vs 1.50, the last two weeks unchanged); inventories and trade hold the level.
FILL = {"pce_goods": "trend12", "pce_services": "trend12", "equipment": "trend12", "structures": "trend12",
        "residential": "trend12", "inventories": "hold", "net_exports": "hold",
        "ipp": "trend", "federal": "trend", "state_local": "trend"}
LABEL = {"pce_goods": "Consumer spending on goods", "pce_services": "Consumer spending on services",
         "equipment": "Equipment investment", "ipp": "Intellectual property investment",
         "structures": "Nonresidential structures", "residential": "Residential investment",
         "federal": "Federal government", "state_local": "State and local government",
         "inventories": "Inventories", "net_exports": "Net exports"}
#: the CPI goods composite that deflates retail sales: core goods, food at home, gasoline, at
#: roughly their weights in PCE goods (durables + other nondurables, food off premises, motor fuel)
GOODS_CPI_WEIGHTS = {"cpi_goods_ex_food_energy": 0.70, "cpi_food_home": 0.22, "cpi_gasoline": 0.08}
TREND_QUARTERS = 4
#: inventories as four books (manufacturing, wholesale, retail autos, retail ex autos), each its own
#: regressor — real-time back-test 2026-10-19: last-day MAE 0.94 vs 1.00 as one book, 8-14 days 0.86
#: vs 0.97. Per-book deflators (CPI new vehicles for autos, CPI core goods for retail) did worse
#: (0.96 / 0.89) and were dropped. GDP_NOWCAST_INV_SPLIT=0 restores one book, for comparison.
import os as _os
INV_SPLIT = _os.environ.get("GDP_NOWCAST_INV_SPLIT", "1") == "1"
#: monthly sources a trend component adds as regressors: {component: {regressor: (sources summed)}}
EXTRA_X = {"state_local": {"employment": ("emp_state", "emp_local"), "public": ("construction_public",)}}
#: services months BEA has not printed: the trailing-12-month trend moved by service-sector hours'
#: deviation from their own trend, at the monthly slope (2012-2026, 2020-21 out)
SVC_HOURS = _os.environ.get("GDP_NOWCAST_SVC_HOURS", "1") == "1"
SVC_HOURS_SLOPE = 0.18
#: regressors a bridge may do without when their history is too short (bridge.fit_one)
OPTIONAL_X = {"equipment": ("imports",)}
SA_YEARS = 5


# ── what a date could see ──────────────────────────────────────────────────────────────────────
class View:
    """Every source as it stood on `asof` (availability only; values are today's vintage)."""

    def __init__(self, asof=None, vintage: bool = False):
        self.asof = None if asof is None else str(asof)[:10]
        self.vintage = bool(vintage and self.asof)
        self._m: dict = {}
        self._v: dict = {}
        self._known_q = None

    def twin(self, name: str):
        """The vintage of `name` on `asof` (real-time view only), or None."""
        if not self.vintage:
            return None
        if name not in self._v:
            self._v[name] = V.as_of(name, self.asof)
        return self._v[name]

    def through(self, name: str):
        """The last month of a monthly source this view can see (None = nothing)."""
        tw = self.twin(name)
        if tw is not None:
            return tw.index[-1] if len(tw) else None
        s = S.monthly(name)
        if self.asof is None or not len(s):
            return s.index[-1] if len(s) else None
        rep = cal.report_of(name)
        if rep is None:
            return s.index[-1]
        cap = cal.available_through(rep, self.asof)
        if cap is None:
            return None
        return min(cap, s.index[-1])

    def monthly(self, name: str) -> pd.Series:
        tw = self.twin(name)
        if tw is not None:
            return tw
        if name not in self._m:
            s = S.monthly(name)
            t = self.through(name)
            self._m[name] = s.loc[:t] if t is not None else s.iloc[:0]
        return self._m[name]

    def known_quarter(self) -> pd.Period:
        """The latest quarter whose advance estimate is out by `asof` (live: the last BEA has)."""
        if self._known_q is None:
            last = S.quarterly("gdp_growth").index[-1]
            tw = self.twin("gdp_growth")
            if tw is not None and len(tw):
                self._known_q = tw.index[-1]
            elif self.asof is None:
                self._known_q = last
            else:
                q = pd.Period(self.asof[:7], freq="M").asfreq("Q")
                while q > last or (cal.advance_gdp_date(q) or "9999") > self.asof:
                    q -= 1
                self._known_q = q
        return self._known_q

    def quarterly(self, name: str) -> pd.Series:
        tw = self.twin(name)
        if tw is not None:
            return tw.loc[:self.known_quarter()]
        return S.quarterly(name).loc[:self.known_quarter()]

    def current_quarterly(self, name: str) -> pd.Series:
        """Today's figures, cut at the quarter the view knows (shares, the residential deflator)."""
        return S.quarterly(name).loc[:self.known_quarter()]


# ── monthly arithmetic ─────────────────────────────────────────────────────────────────────────
def months_of(q: pd.Period) -> pd.PeriodIndex:
    return pd.period_range(q.asfreq("M", "start"), q.asfreq("M", "end"), freq="M")


def splice(base: pd.Series, ext: pd.Series, how: str = "ratio") -> pd.Series:
    """`base` carried past its last month by the movement of `ext` (ratio: growth; diff: level
    change). Months `ext` cannot bridge are left off."""
    base = base.dropna()
    ext = ext.dropna()
    if not len(base) or not len(ext):
        return base
    last = base.index[-1]
    if last not in ext.index:
        return base
    more = ext.loc[ext.index > last]
    if not len(more):
        return base
    if how == "ratio":
        add = base.iloc[-1] * more / ext.loc[last]
    else:
        add = base.iloc[-1] + (more - ext.loc[last])
    return pd.concat([base, add])


def fill(s: pd.Series, through: pd.Period, rule: str) -> tuple[pd.Series, list]:
    """Extend a monthly level series to `through` by the rule; returns (series, filled months)."""
    s = s.dropna()
    if not len(s):
        return s, []
    last = s.index[-1]
    if last >= through:
        return s, []
    need = pd.period_range(last + 1, through, freq="M")
    if rule == "trend12" and len(s) >= 13:
        g = (s.iloc[-1] / s.iloc[-13]) ** (1 / 12)
    else:
        g = 1.0
    add = pd.Series([s.iloc[-1] * g ** (i + 1) for i in range(len(need))], index=need)
    return pd.concat([s, add]), [str(m) for m in need]


def qgrowth(s: pd.Series, q: pd.Period) -> float | None:
    """Annualized percent growth of the quarter's mean level over the prior quarter's."""
    cur, prev = months_of(q), months_of(q - 1)
    if not set(cur).issubset(s.index) or not set(prev).issubset(s.index):
        return None
    r = s.loc[cur].mean() / s.loc[prev].mean()
    return (r ** 4 - 1) * 100 if r > 0 else None


def qgrowth_all(s: pd.Series) -> pd.Series:
    """qgrowth for every complete quarter of a monthly series, vectorized."""
    s = s.dropna()
    if not len(s):
        return pd.Series(dtype=float)
    qm = s.groupby(s.index.asfreq("Q")).agg(["mean", "count"])
    qm = qm.loc[qm["count"] == 3, "mean"]
    if not len(qm):
        return pd.Series(dtype=float)
    qm = qm.reindex(pd.period_range(qm.index[0], qm.index[-1], freq="Q"))
    return ((qm / qm.shift(1)) ** 4 - 1) * 100


def held_price(p: pd.Series, through: pd.Period) -> pd.Series:
    return fill(p, through, "hold")[0]


def goods_cpi(v: View) -> pd.Series:
    """Chained CPI goods composite (index, monthly), from GOODS_CPI_WEIGHTS."""
    parts = {n: v.monthly(n) for n in GOODS_CPI_WEIGHTS}
    idx = None
    for n, s in parts.items():
        idx = s.index if idx is None else idx.intersection(s.index)
    lg = sum(w * np.log(parts[n].loc[idx]).diff() for n, w in GOODS_CPI_WEIGHTS.items())
    return np.exp(lg.fillna(0).cumsum()) * 100


def seasonal_adjust(s: pd.Series, years: int = SA_YEARS) -> pd.Series:
    """Ratio-to-moving-average seasonal adjustment of an NSA monthly series: each month's factor
    is the mean of its same-calendar-month ratios to a centered 2x12 moving average over the
    last `years` years whose ratio was settled at least a year before (so a month is never
    adjusted with its own data), normalized to average one within each year."""
    s = s.dropna()
    if len(s) < 25:
        return s * np.nan
    ma = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)
    ratio = (s / ma).dropna()
    fac = {}
    for p in s.index:
        same = ratio[(ratio.index.month == p.month)]
        prior = same[same.index <= p - 12]
        use = prior if len(prior) else same[same.index > p].iloc[:1]   # the first year: the next one known
        fac[p] = float(use.iloc[-years:].mean()) if len(use) else 1.0
    f = pd.Series(fac)
    f = f / f.groupby(f.index.year).transform("mean")
    return s / f


def capgoods_imports_real(v: View) -> pd.Series:
    """Real imports of capital goods except autos, SA, $mn at the latest price level: Census end
    use seasonally adjusted, carried a month past the full report by the advance goods report."""
    key = "_capm"
    if key not in v._m:
        nom = splice(seasonal_adjust(v.monthly("capgoods_imports")), v.monthly("adv_imports_goods"))
        p = v.monthly("import_prices_capital")
        v._m[key] = (nom / held_price(p, nom.index[-1] if len(nom) else p.index[-1])).dropna() if len(nom) else nom
    return v._m[key]


def _summed(names, v: View) -> pd.Series:
    """The month-by-month sum of several monthly sources (months all of them carry)."""
    out = None
    for n in names:
        s = v.monthly(n)
        out = s if out is None else out.add(s, fill_value=np.nan)
    return out.dropna() if out is not None else pd.Series(dtype=float)


def _months_in(base_through, q: pd.Period) -> int:
    if base_through is None:
        return 0
    return int(sum(1 for m in months_of(q) if m <= base_through))


# ── the monthly real indicators, one per component ─────────────────────────────────────────────
def real_level(comp: str, v: View, through: pd.Period) -> tuple[pd.Series, dict]:
    """(monthly real level filled to `through`, info) for a growth component."""
    info: dict = {"sources": [], "filled": []}
    if comp == "pce_goods":
        base = v.monthly("real_pce_goods")
        nominal = v.monthly("retail_total") - v.monthly("retail_food_services")
        proxy = (nominal.dropna() / held_price(goods_cpi(v), nominal.index[-1] if len(nominal) else through)).dropna()
        lvl = splice(base, proxy)
        info["sources"] = ["real_pce_goods", "retail_total less food services / CPI goods"]
        info["data_through"] = str(lvl.index[-1]) if len(lvl) else None
        info["bea_through"] = str(base.index[-1]) if len(base) else None
    elif comp == "pce_services":
        lvl = v.monthly("real_pce_services")
        if SVC_HOURS and len(lvl) >= 13 and lvl.index[-1] < through:
            hrs = v.monthly("hours_services")
            hg = np.log(hrs).diff()
            g12 = (lvl.iloc[-1] / lvl.iloc[-13]) ** (1 / 12)
            add = {}
            for m in pd.period_range(lvl.index[-1] + 1, through, freq="M"):
                if m not in hg.index or m - 1 not in hg.index:
                    break
                dev = hg.loc[m] - hg.loc[m - 12:m - 1].mean()
                prev = add.get(m - 1, lvl.iloc[-1])
                add[m] = prev * g12 * float(np.exp(SVC_HOURS_SLOPE * dev))
            if add:
                lvl = pd.concat([lvl, pd.Series(add)])
        info["sources"] = ["real_pce_services"]
        info["data_through"] = str(lvl.index[-1]) if len(lvl) else None
    elif comp == "equipment":
        nom = splice(v.monthly("core_capgoods_shipments"), v.monthly("adv_core_capgoods_shipments"))
        lvl = nom / held_price(v.monthly("ppi_capital_equipment"), nom.index[-1] if len(nom) else through)
        lvl = lvl.dropna()
        info["sources"] = ["core_capgoods_shipments (+ advance)", "ppi_capital_equipment"]
        info["data_through"] = str(nom.index[-1]) if len(nom) else None
    elif comp in ("structures", "residential"):
        name = "construction_private_nonres" if comp == "structures" else "construction_private_res"
        lvl = v.monthly(name)
        info["sources"] = [name] + (["BEA residential deflator, 4-quarter trend"] if comp == "residential" else [])
        info["data_through"] = str(lvl.index[-1]) if len(lvl) else None
    else:
        raise KeyError(comp)
    lvl, filled = fill(lvl, through, FILL[comp])
    info["filled"] = filled
    return lvl, info


def _gold(flow: str, v: View) -> pd.Series:
    """Nonmonetary gold, trailing three-month mean of the NSA monthly values, $mn."""
    g = v.monthly(f"gold_{flow}").rolling(3).mean().dropna()
    return g


def _deflate_at(nom: pd.Series, price: pd.Series, ref: pd.Period) -> pd.Series:
    p = held_price(price, nom.index[-1]) if len(price) else price
    p = p.reindex(nom.index).ffill()
    return nom * p.loc[ref] / p if ref in p.index else nom * np.nan


def inventory_books(v: View) -> tuple[dict, dict]:
    """({book: end-of-month book values, $mn}, info): manufacturing, wholesale and retail (or retail
    autos and retail ex autos, with INV_SPLIT), each carried to month 3 by its advance report
    where the full report lacks it."""
    mfg = v.monthly("inv_manufacturing")
    mfg = splice(mfg, v.monthly("adv_inv_manufacturing"), how="diff")    # durables move, nondurables held
    whl = splice(v.monthly("inv_wholesale"), v.monthly("adv_inv_wholesale"), how="diff")
    books = {"manufacturing": mfg, "wholesale": whl}
    if INV_SPLIT:
        books["retail_autos"] = splice(v.monthly("inv_retail_autos"), v.monthly("adv_inv_retail_autos"), how="diff")
        books["retail_xauto"] = splice(v.monthly("inv_retail_xauto"), v.monthly("adv_inv_retail_xauto"), how="diff")
    else:
        books["retail"] = splice(v.monthly("inv_retail"), v.monthly("adv_inv_retail"), how="diff")
    info = {"through": {k: str(s.index[-1]) if len(s) else None for k, s in books.items()}}
    return books, info


def trade_flows(v: View) -> tuple[pd.Series, pd.Series, dict]:
    """(exports, imports) of goods and services less nonmonetary gold, $mn, month 3 goods moved
    by the advance report."""
    exp = splice(v.monthly("exports_goods_services"), v.monthly("adv_exports_goods"), how="diff")
    imp = splice(v.monthly("imports_goods_services"), v.monthly("adv_imports_goods"), how="diff")
    out = []
    for flow, s in (("exports", exp), ("imports", imp)):
        g = _gold(flow, v)
        if len(g):
            g = g.reindex(s.index)
            first = g.first_valid_index()
            if first is not None:
                g.loc[:first] = g.loc[first]            # before the HS data: flat, so no change
            g = g.ffill()                               # months the HS data lacks: held
            s = s - g.fillna(0)
        out.append(s)
    info = {"through": {"exports": str(exp.index[-1]) if len(exp) else None,
                        "imports": str(imp.index[-1]) if len(imp) else None}}
    return out[0], out[1], info


def _contribution(kind: str, q: pd.Period, v: View, ngdp_prev: float, pieces=None) -> tuple[float | None, dict]:
    """Inventories or net exports: the contribution indicator for quarter q, percentage points."""
    m3, m0 = q.asfreq("M", "end"), (q - 1).asfreq("M", "end")
    if kind == "inventories":
        books, info = pieces or inventory_books(v)
        info = dict(info)
        filled, by_book = [], {}
        for name, s in books.items():
            s2, f = fill(s, m3, "hold")
            filled += [f"{name} {m}" for m in f]
            r = _deflate_at(s2, v.monthly("ppi_finished_core"), m0)
            if any(m not in r.index or pd.isna(r.loc[m]) for m in (m3, m0)):
                return None, info
            by_book[name] = 400 * 4 * float(r.loc[m3] - r.loc[m0]) / ngdp_prev
        val = sum(by_book.values())
        info.update({"filled": filled, "by_book": by_book})
        return val, info
    exp, imp, info = pieces or trade_flows(v)
    filled = []
    exp2, f1 = fill(exp, m3, "hold")
    imp2, f2 = fill(imp, m3, "hold")
    filled = [f"exports {m}" for m in f1] + [f"imports {m}" for m in f2]
    rx = _deflate_at(exp2, v.monthly("export_prices"), m0)
    rm = _deflate_at(imp2, v.monthly("import_prices"), m0)
    nx = (rx - rm).dropna()
    cur, prev = months_of(q), months_of(q - 1)
    if not set(cur).issubset(nx.index) or not set(prev).issubset(nx.index):
        return None, info
    val = 400 * 12 * (nx.loc[cur].mean() - nx.loc[prev].mean()) / ngdp_prev
    info.update({"filled": filled})
    return val, info


def trend(comp: str, q: pd.Period, v: View) -> tuple[float | None, dict]:
    """Mean of the last TREND_QUARTERS published growth rates known to the view, before q."""
    s = v.quarterly(TARGET[comp]).loc[:q - 1].dropna()
    s = s.drop([p for p in s.index if p in (pd.Period("2020Q2"), pd.Period("2020Q3"))], errors="ignore")
    if len(s) < TREND_QUARTERS:
        return None, {}
    tail = s.iloc[-TREND_QUARTERS:]
    return float(tail.mean()), {"quarters": [str(p) for p in tail.index], "sources": [TARGET[comp]]}


def deflator_trend(comp: str, q: pd.Period, v: View) -> float | None:
    """Mean of BEA's implied deflator inflation for a component over the last TREND_QUARTERS
    quarters the view knows, before q (percent, annual rate)."""
    nom = v.current_quarterly(NOMINAL[comp])
    d = (((nom / nom.shift(1)) ** 4 - 1) * 100 - v.current_quarterly(TARGET[comp])).loc[:q - 1].dropna()
    return float(d.iloc[-TREND_QUARTERS:].mean()) if len(d) >= TREND_QUARTERS else None


def inventory_anchor(q: pd.Period, v: View) -> float | None:
    """BEA's real change in private inventories as a share of real GDP (x400) in the latest
    quarter before q the view knows."""
    ri, rg = v.quarterly("real_inventories").loc[:q - 1], v.quarterly("real_gdp").loc[:q - 1]
    if not len(ri) or not len(rg):
        return None
    return float(400 * ri.iloc[-1] / rg.iloc[-1])


def indicator(comp: str, q: pd.Period, v: View, cache: dict | None = None) -> dict:
    """{'value', 'months' (of q with real data), 'filled', ...} for one component and quarter."""
    q = pd.Period(q, freq="Q")
    cache = {} if cache is None else cache
    m3 = q.asfreq("M", "end")
    if FILL[comp] == "trend":
        val, info = trend(comp, q, v)
        x, filled, months = {"indicator": val}, ["whole quarter (trend)"], 0
        for reg, names in EXTRA_X.get(comp, {}).items():
            lvl = _summed(names, v)
            months = max(months, _months_in(lvl.index[-1] if len(lvl) else None, q))
            lvl, f = fill(lvl, m3, "hold")
            x[reg] = qgrowth(lvl, q) if len(lvl) else None
            filled = [m for m in filled if "trend" not in m] + [f"{reg} {m}" for m in f]
        return {"value": val, "x": x, "months": months, "filled": filled, **info}
    if comp in CONTRIBUTIONS:
        ngdp = v.quarterly("nominal_gdp")
        prev = ngdp.loc[:q - 1]
        if not len(prev):
            return {"value": None, "months": 0, "filled": []}
        key = ("pieces", comp)
        if key not in cache:
            cache[key] = inventory_books(v) if comp == "inventories" else trade_flows(v)
        val, info = _contribution(comp, q, v, float(prev.iloc[-1]), cache[key])
        info = dict(info)
        thr = [pd.Period(t, freq="M") for t in info.get("through", {}).values() if t]
        months = min(_months_in(t, q) for t in thr) if thr else 0
        x = {"indicator": val}
        if comp == "inventories":
            if INV_SPLIT and val is not None:
                x = dict(info.get("by_book") or {})
            x["anchor"] = inventory_anchor(q, v)
        return {"value": val, "x": x, "months": months, **info}
    lvl, info = real_level(comp, v, m3)
    val = qgrowth(lvl, q)
    if comp == "residential" and val is not None:
        dtr = deflator_trend(comp, q, v)
        val = None if dtr is None else val - dtr
    t = info.get("data_through")
    months = _months_in(pd.Period(t, freq="M") if t else None, q)
    x = {"indicator": val}
    for reg, names in EXTRA_X.get(comp, {}).items():
        lvl2, f = fill(_summed(names, v), m3, "hold")
        x[reg] = qgrowth(lvl2, q) if len(lvl2) else None
        info["filled"] = info.get("filled", []) + [f"{reg} {m}" for m in f]
    if comp == "equipment":
        cm = capgoods_imports_real(v)
        cm2, f = fill(cm, m3, "hold")
        x["imports"] = qgrowth(cm2, q) if len(cm2) else None
        info["filled"] = info.get("filled", []) + [f"capital goods imports {m}" for m in f]
        info["imports_through"] = str(cm.index[-1]) if len(cm) else None
    return {"value": val, "x": x, "months": months, **info}


# ── complete-data history, for the bridges ─────────────────────────────────────────────────────
def history(comp: str, v: View | None = None) -> pd.DataFrame:
    """The component's regressors for every quarter the data cover in full (no fills inside a
    quarter; the trend pieces are trends by construction), one column per regressor."""
    v = v or View(None)
    if FILL[comp] == "trend":
        s = v.quarterly(TARGET[comp]).copy()
        s.loc[[p for p in s.index if p in (pd.Period("2020Q2"), pd.Period("2020Q3"))]] = np.nan
        out = s.dropna().rolling(TREND_QUARTERS).mean().shift(1)
        df = pd.DataFrame({"indicator": out.reindex(s.index)})
        for reg, names in EXTRA_X.get(comp, {}).items():
            df[reg] = qgrowth_all(_summed(names, v)).reindex(df.index)
        return df.dropna()
    if comp in CONTRIBUTIONS:
        ngdp = v.quarterly("nominal_gdp")
        pieces = inventory_books(v) if comp == "inventories" else trade_flows(v)
        last_m = min(pd.Period(t, freq="M") for t in pieces[-1]["through"].values() if t)
        last = last_m.asfreq("Q")
        if last.asfreq("M", "end") > last_m:
            last -= 1
        rows = {}
        for q in pd.period_range("1993Q1", last, freq="Q"):
            if q - 1 not in ngdp.index:
                continue
            val, inf = _contribution(comp, q, v, float(ngdp.loc[q - 1]), pieces)
            if val is None or not math.isfinite(val):
                continue
            rows[q] = dict(inf["by_book"]) if (comp == "inventories" and INV_SPLIT) else {"indicator": val}
            if comp == "inventories":
                rows[q]["anchor"] = inventory_anchor(q, v)
        return pd.DataFrame.from_dict(rows, orient="index").dropna()
    lvl, _ = real_level(comp, v, pd.Period("1990-01", freq="M"))   # through < data: no fill
    g = qgrowth_all(lvl)
    if comp == "residential":
        nom = v.current_quarterly(NOMINAL[comp])
        defl = ((nom / nom.shift(1)) ** 4 - 1) * 100 - v.current_quarterly(TARGET[comp])
        g = g - defl.rolling(TREND_QUARTERS).mean().shift(1).reindex(g.index)
    out = pd.DataFrame({"indicator": g}).dropna()
    for reg, names in EXTRA_X.get(comp, {}).items():
        out[reg] = qgrowth_all(_summed(names, v)).reindex(out.index)
    out = out.dropna()
    if comp == "equipment":                      # optional: NaN before the end-use data begin
        out["imports"] = qgrowth_all(capgoods_imports_real(v)).reindex(out.index)
    return out
