"""The engine: Engine().nowcast(quarter, asof) -> the estimate, the component table and the stage.

    from engine.model import Engine
    e = Engine()
    e.nowcast("2026Q3")                  # live: everything on hand
    e.nowcast("2026Q2", "2026-07-17")    # what the engine would have said that day

Per component: the indicator as of `asof` (`components.indicator`), bridged to BEA's concept
(`bridge.apply`), weighted by its share of current-dollar GDP in the latest quarter BEA had
published. The sum is done in quarterly terms and annualized at the end — real GDP's quarterly
growth = Σ share × the component's quarterly growth + the two contributions de-annualized — which
reproduces BEA's printed growth from its printed components to 4 bp on average (2012-2026, mean
error +2 bp, against +9 bp for share × annualized growth). Contributions in the table are
re-annualized the same way, so they add up to the headline.

A component whose regressors are missing on the day (a source not yet published at all, say)
falls back to the mean of its last four published growth rates — zero for the contributions — and
says so (`fallback: true`).

`released` = the reports with at least one month of the quarter in; `stage` = the latest of them
to print by `asof`, which is what an estimate is labeled by.

FIRST PRINT: the bridges are fit on today's revised history, so the sum estimates GDP as it will
read after the revisions; BEA's ADVANCE estimate — the target — has come in 0.35 pp below today's
vintage of the same quarter on average (2011Q3-2026Q2; -0.35 in 2011-19, -0.34 in 2021-26). The
headline `value` adds that gap (`first_print_offset`, the mean over every quarter at least
FIRST_PRINT_LAG quarters old, so each has been through an annual update); `value_raw` is the sum
before it. Re-measured on every run from Atlanta's TrackRecord sheet (advance) and BEA's current
table; the last good measurement is kept in data/ref/first_print_gaps.json for a day Atlanta's file
cannot be read.

THE GAP IS INSIDE THE COMPONENTS, not a line of its own (2026-10-27): `offset_allocation` splits it
across the components in proportion to each one's own
average first-print gap over the same quarters (`first_print_component_gaps`: structures,
intellectual property, state and local and consumer services carry most of it; net exports goes
the other way), scaled so the pieces sum exactly to the headline's gap — so `contribution` adds up
to `value`, and `bridged` is the growth rate that contribution implies. Inventories takes none: its
bridge already targets BEA's first prints. `contribution_raw` / `bridged_raw` / `first_print` keep
the pieces before the split.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import json

from . import bridge
from . import calendar as cal
from . import components as C
from . import sources as S

#: Decimals the estimate is STORED at (2026-10-28): only printers round, once, half up.
#: A value cut to 2 dp rounds twice at one decimal (2.649 -> 2.65 -> 2.7).
DP = 4
FIRST_PRINT_FILE = S.REF / "first_print_gaps.json"
FIRST_PRINT_COMPONENT_FILE = S.REF / "first_print_component_gaps.json"
FIRST_PRINT_LAG = 4
FIRST_PRINT_MIN = 4
FIRST_PRINT_SKIP = ("2020Q2", "2020Q3")
_GAPS: dict = {}

#: the reports that feed the engine, with the source that says how far each has got
INPUT_REPORTS = {
    "retail": "retail_total", "m3_adv": "adv_core_capgoods_shipments",
    "m3_full": "core_capgoods_shipments", "inventories": "inv_total_business",
    "retail_trade": "inv_retail", "wholesale": "inv_wholesale",
    "construction": "construction_private_nonres", "trade": "exports_goods_services",
    "advance_indicators": "adv_exports_goods", "pce": "real_pce", "cpi": "cpi_all",
    "ppi": "ppi_finished_goods", "trade_prices": "import_prices",
    "employment": "emp_state",
}
#: how a stage reads in a sentence: "after <this>", {m} = the report's latest month
REPORT_LABEL = {
    "retail": "{m} retail sales", "m3_adv": "{m} advance durable goods",
    "m3_full": "{m} factory orders", "inventories": "{m} business inventories",
    "retail_trade": "{m} retail inventories", "wholesale": "{m} wholesale inventories",
    "construction": "{m} construction spending", "trade": "{m} trade",
    "advance_indicators": "{m} advance goods trade and inventories",
    "pce": "{m} consumer spending", "cpi": "the {m} CPI", "ppi": "the {m} PPI",
    "trade_prices": "{m} import and export prices",
    "employment": "the {m} jobs report",
}


def annualize(gq: float) -> float:
    return ((1 + gq) ** 4 - 1) * 100


def deannualize(g: float) -> float:
    return (1 + g / 100) ** 0.25 - 1


def aggregate(shares: dict, growth: dict, contribs: dict) -> tuple[float, dict]:
    """(real GDP growth, annualized; {component: contribution in pp}) from shares, component
    growth rates (percent, annual rate) and contributions (pp, annual rate)."""
    base = sum(shares[k] * deannualize(growth[k]) for k in growth)
    c_total = sum(contribs.values())
    gq = base + c_total / 400
    for _ in range(8):                     # contributions are scaled by BEA's annualizing factor
        a = ((1 + gq) ** 4 - 1) / gq if abs(gq) > 1e-9 else 4.0
        gq = base + c_total / 100 / a
    a = ((1 + gq) ** 4 - 1) / gq if abs(gq) > 1e-9 else 4.0
    contrib = {k: shares[k] * deannualize(growth[k]) * a * 100 for k in growth}
    contrib.update(contribs)
    return annualize(gq), contrib


def first_print_gaps() -> pd.Series:
    """BEA's advance estimate minus today's vintage, by quarter (pp), 2020Q2-Q3 left out."""
    if "s" in _GAPS:
        return _GAPS["s"]
    s = None
    try:
        from .public_doors import atlfed
        rec = atlfed.gdpnow_track_record()
        g = S.quarterly("gdp_growth")
        d = {k: round(v["advance"] - float(g.loc[pd.Period(k, freq="Q")]), 4)
             for k, v in rec.items() if pd.Period(k, freq="Q") in g.index and k not in ("2020Q2", "2020Q3")}
        if d:
            S.REF.mkdir(parents=True, exist_ok=True)
            FIRST_PRINT_FILE.write_text(json.dumps(dict(sorted(d.items())), indent=0))
            s = pd.Series({pd.Period(k, freq="Q"): v for k, v in d.items()}).sort_index()
    except Exception:  # noqa: BLE001 — Atlanta unreachable: the last good measurement
        s = None
    if s is None:
        try:
            d = json.loads(FIRST_PRINT_FILE.read_text())
            s = pd.Series({pd.Period(k, freq="Q"): v for k, v in d.items()}).sort_index()
        except Exception:  # noqa: BLE001
            s = pd.Series(dtype=float)
    _GAPS["s"] = s
    return s


def first_print_offset(q: pd.Period, view: C.View | None = None) -> float:
    """Mean advance-minus-revised gap over the quarters at least FIRST_PRINT_LAG before q. A
    real-time view measures "revised" as that morning knew it, not as today does."""
    s = first_print_gaps().loc[:q - 1 - FIRST_PRINT_LAG]
    if view is not None and view.vintage:
        g_then = view.twin("gdp_growth")
        if g_then is not None:
            g_now = S.quarterly("gdp_growth")
            adv = s + g_now.reindex(s.index)             # gap = advance - today, so advance = gap + today
            s = (adv - g_then.reindex(s.index)).dropna()
    return float(s.mean()) if len(s) >= FIRST_PRINT_MIN else 0.0


def first_print_component_gaps() -> pd.DataFrame:
    """Each component's first print minus today's vintage, as a contribution (pp at an annual rate),
    by quarter: a growth component's gap times its share of current-dollar GDP the quarter before,
    a contribution component's gap as is. Rows = the quarters every component has (2020Q2-Q3 out).
    Measured from the ALFRED vintages when all ten are on disk (replicate.py downloads them), else
    the last measurement in data/ref/first_print_component_gaps.json."""
    if "c" in _GAPS:
        return _GAPS["c"]
    from . import vintages as V
    df = None
    if all((V.VINT / f"{V.TWINS[C.TARGET[c]]}.json").exists() for c in C.COMPONENTS):
        try:
            ngdp = S.quarterly("nominal_gdp")
            cols = {}
            for comp in C.COMPONENTS:
                fp = V.first_prints(C.TARGET[comp])
                g = (fp - S.quarterly(C.TARGET[comp]).reindex(fp.index)).dropna()
                if comp not in C.CONTRIBUTIONS:
                    g = (g * (S.quarterly(C.NOMINAL[comp]) / ngdp).shift(1).reindex(g.index)).dropna()
                cols[comp] = g
            df = pd.DataFrame(cols).dropna()
            df = df[[str(q) not in FIRST_PRINT_SKIP for q in df.index]]
            if len(df):
                S.REF.mkdir(parents=True, exist_ok=True)
                FIRST_PRINT_COMPONENT_FILE.write_text(json.dumps(
                    {str(q): {c: round(float(v), 4) for c, v in r.items()} for q, r in df.iterrows()}, indent=0))
        except Exception:  # noqa: BLE001 — a vintage file unreadable: the last good measurement
            df = None
    if df is None or not len(df):
        try:
            d = json.loads(FIRST_PRINT_COMPONENT_FILE.read_text())
            df = pd.DataFrame.from_dict(d, orient="index")
            df.index = pd.PeriodIndex(df.index, freq="Q")
            df = df.sort_index()
        except Exception:  # noqa: BLE001
            df = pd.DataFrame(columns=list(C.COMPONENTS))
    _GAPS["c"] = df
    return df


def offset_allocation(q: pd.Period, offset: float, shares: dict) -> dict:
    """{component: pp} summing exactly to `offset`. The components BEA revises (every one but those
    bridged to first prints) share it in proportion to their own mean first-print gap over the
    quarters the headline's offset averages (at least FIRST_PRINT_LAG before q). If those gaps are
    missing, or their sum is not the offset's sign and at least a fifth of its size (so the scaling
    cannot blow up), it falls back to shares of current-dollar GDP among the growth components."""
    if not offset:
        return {}
    take = [c for c in C.COMPONENTS if c not in bridge.FIRST_PRINT_TARGETS]
    gaps = first_print_component_gaps()
    gaps = gaps.loc[gaps.index <= q - 1 - FIRST_PRINT_LAG] if len(gaps) else gaps
    w = {}
    if len(gaps) >= FIRST_PRINT_MIN and all(c in gaps.columns for c in take):
        w = {c: float(gaps[c].mean()) for c in take}
        tot = sum(w.values())
        if not (tot * offset > 0 and abs(tot) >= 0.2 * abs(offset)):
            w = {}
    if not w:
        w = {c: shares[c] for c in take if c in shares}
    tot = sum(w.values())
    return {c: offset * v / tot for c, v in w.items()} if tot else {}


class Engine:
    def __init__(self, coefs: dict | None = None):
        self.coefs = coefs or bridge.load()

    def nowcast(self, quarter, asof=None, coefs: dict | None = None, first_print: bool = True,
                vintage: bool = False) -> dict:
        q = pd.Period(quarter, freq="Q")
        v = C.View(asof, vintage=vintage)
        coefs = coefs or self.coefs
        kq = v.known_quarter()
        share_q = min(kq, q - 1)
        ngdp = v.current_quarterly("nominal_gdp")
        shares = {comp: float(v.current_quarterly(n).loc[share_q] / ngdp.loc[share_q]) for comp, n in C.NOMINAL.items()}
        cache: dict = {}
        rows, growth, contribs = {}, {}, {}
        for comp in C.COMPONENTS:
            ind = C.indicator(comp, q, v, cache)
            bridged = bridge.apply(coefs, comp, ind.get("x") or {})
            fallback = bridged is None
            if fallback:
                if comp in C.CONTRIBUTIONS:
                    bridged = 0.0
                else:
                    hist = v.quarterly(C.TARGET[comp]).loc[:q - 1].dropna()
                    bridged = float(hist.iloc[-C.TREND_QUARTERS:].mean())
            rows[comp] = {"label": C.LABEL[comp], "indicator": _r(ind.get("value")),
                          "x": {k: _r(x) for k, x in (ind.get("x") or {}).items()},
                          "bridged": _r(bridged), "months": ind.get("months", 0),
                          "filled": ind.get("filled", []), "fallback": fallback}
            if comp in C.CONTRIBUTIONS:
                contribs[comp] = bridged
            else:
                growth[comp] = bridged
                rows[comp]["share"] = round(shares[comp], 4)
        raw, contrib = aggregate(shares, growth, contribs)
        all_fp = set(bridge.FIRST_PRINT_TARGETS) >= set(C.COMPONENTS)   # the sum IS a first print then
        offset = first_print_offset(q, v) if first_print and not all_fp else 0.0
        # the gap goes into the components (offset_allocation), so they add up to the headline; a
        # growth component's rate is then the one its new contribution implies at the headline's
        # annualizing factor — model.aggregate's arithmetic run backwards, so it reproduces `value`
        alloc = offset_allocation(q, offset, shares)
        gq = deannualize(raw + offset)
        a = ((1 + gq) ** 4 - 1) / gq if abs(gq) > 1e-9 else 4.0
        for comp in rows:
            c1 = contrib[comp] + alloc.get(comp, 0.0)
            rows[comp]["contribution_raw"] = _r(contrib[comp])
            rows[comp]["first_print"] = _r(alloc.get(comp, 0.0))
            rows[comp]["contribution"] = _r(c1)
            if comp in growth:
                rows[comp]["bridged_raw"] = rows[comp]["bridged"]
                rows[comp]["bridged"] = _r(annualize(c1 / (shares[comp] * a * 100)))
        released, stage, stage_date = self._released(q, v, asof)
        return {"quarter": str(q), "value": round(raw + offset, DP), "value_raw": round(raw, DP),
                "first_print_offset": round(offset, DP), "asof": v.asof or dt.date.today().isoformat(),
                "components": rows, "released": released, "stage": stage,
                "stage_date": stage_date, "stage_label": _stage_label(stage, q, v),
                "shares_from": str(share_q), "known_quarter": str(kq)}

    @staticmethod
    def _released(q: pd.Period, v: C.View, asof) -> tuple[list, str | None, str | None]:
        first = q.asfreq("M", "start")
        day = v.asof or dt.date.today().isoformat()
        released, latest = [], (None, "")
        for rep, src in INPUT_REPORTS.items():
            t = v.through(src)
            if t is None or t < first:
                continue
            released.append(rep)
            d = cal.month_map(rep).get(t) or ""
            if d <= day and d > latest[1]:
                latest = (rep, d)
        prior = cal.advance_gdp_date(q - 1)
        if prior and prior <= day and prior > latest[1]:
            latest = ("gdp", prior)
        return released, latest[0], latest[1] or None


def _stage_label(stage: str | None, q: pd.Period, v: C.View) -> str | None:
    if not stage:
        return None
    if stage == "gdp":
        return f"after BEA's advance estimate for {q - 1}"
    t = v.through(INPUT_REPORTS[stage])
    month = t.to_timestamp().strftime("%B") if t is not None else ""
    return "after " + REPORT_LABEL[stage].format(m=month).strip()


def _r(x, nd: int = 4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if np.isfinite(x) else None


if __name__ == "__main__":  # pragma: no cover
    import sys
    args = sys.argv[1:]
    q = args[0] if args else None
    asof = args[1] if len(args) > 1 else None
    if q is None:
        from .public_doors import current_quarter
        q = current_quarter()
    out = Engine().nowcast(q, asof)
    print(f"{out['quarter']} as of {out['asof']}: {out['value']:.2f}%  ({out['stage_label']}; "
          f"{out['value_raw']:.2f} before the first-print gap {out['first_print_offset']:+.2f})")
    print(f"{'component':34s} {'months':>6s} {'indicator':>9s} {'bridged':>8s} {'share':>6s} {'contrib':>8s}")
    for k, r in out["components"].items():
        print(f"{r['label']:34s} {r['months']:6d} {r['indicator'] if r['indicator'] is not None else float('nan'):9.2f} "
              f"{r['bridged']:8.2f} {r.get('share', float('nan')):6.3f} {r['contribution']:8.2f}"
              + ("  (fallback)" if r["fallback"] else ""))
    if "--json" in args:
        print(json.dumps(out, indent=1))
