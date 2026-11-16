"""The bridges: fitted linear maps from each component's regressors to what BEA prints.

    python -m engine.bridge --fit     # refit on 2012Q1 onward, write data/ref/bridge_coefficients.json
    python -m engine.bridge           # print the saved table

Ordinary least squares of each `components.TARGET` (BEA's real growth rate, or the inventories /
net exports contribution) on the component's regressors (`components.history`), FIT_START onward,
2020Q2-Q3 left out (two quarters whose swings would set every slope). Refit after each annual
update — `current()` does that by itself: it refits whenever the targets BEA prints (2012Q1 on)
differ from the ones the saved fit used, which catches the annual update, every second and third
estimate, and a new quarter, so the coefficients never sit on a history BEA has replaced.

The back-test refits as it goes (`fit(through=...)`): only quarters before the one being nowcast,
and when FIT_START leaves fewer than MIN_QUARTERS behind, the MIN_QUARTERS before — so no quarter
is ever scored with a bridge that saw it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json

import numpy as np
import pandas as pd

from . import components as C
from . import sources as S

#: components whose bridge is fit on BEA's FIRST PRINTS (the target) rather than the history as
#: revised: each quarter's value as of its own advance estimate (`vintages.first_prints`), today's
#: value where ALFRED does not reach. Real-time back-test 2026-10-19: inventories only helps
#: (1.01 -> 1.00 last day); all ten does worse (1.05), because BEA's later revisions to the other
#: pieces are information about the source data, not noise. GDP_NOWCAST_FIRST_PRINT=none|all for tests.
import os as _os
_FP_MODE = _os.environ.get("GDP_NOWCAST_FIRST_PRINT", "inventories")
FIRST_PRINT_TARGETS = (() if _FP_MODE == "none" else tuple(C.COMPONENTS) if _FP_MODE == "all" else ("inventories",))
FIT_START = pd.Period("2012Q1", freq="Q")
EXCLUDE = (pd.Period("2020Q2", freq="Q"), pd.Period("2020Q3", freq="Q"))
MIN_QUARTERS = 32
MIN_OBS = 16      # an optional regressor (components.OPTIONAL_X) joins only with this many quarters
COEF_FILE = S.REF / "bridge_coefficients.json"

_HIST: dict = {}


def histories(view: C.View | None = None) -> dict[str, pd.DataFrame]:
    """Every component's complete-data regressors joined to its target — today's data, or as seen
    by `view` (the real-time back-test fits each quarter's bridges on what that morning knew)."""
    if view is None:
        if not _HIST:
            _HIST.update(_build(C.View(None), S.quarterly))
        return _HIST
    return _build(view, view.quarterly)


def _target(comp: str, view: C.View, target) -> pd.Series:
    s = target(C.TARGET[comp])
    if comp in FIRST_PRINT_TARGETS:
        from . import vintages as V
        fp = V.first_prints(C.TARGET[comp]).loc[:view.known_quarter()]
        s = fp.combine_first(s)
    return s


def _build(view: C.View, target) -> dict[str, pd.DataFrame]:
    out = {}
    for comp in C.COMPONENTS:
        h = C.history(comp, view)
        h["target"] = _target(comp, view, target).reindex(h.index)
        need = [c for c in h.columns if c not in C.OPTIONAL_X.get(comp, ())]
        out[comp] = h.dropna(subset=need)
    return out


def fit_one(comp: str, through=None, start=FIT_START, min_quarters: int = MIN_QUARTERS, hist: dict | None = None) -> dict:
    h = (hist or histories())[comp]
    if through is not None:
        h = h.loc[:pd.Period(through, freq="Q")]
    h = h.drop([q for q in EXCLUDE if q in h.index])
    s = pd.Period(start, freq="Q")
    if through is not None and len(h.loc[s:]) < min_quarters:
        h = h.iloc[-min_quarters:]
    else:
        h = h.loc[s:]
    opt = [c for c in C.OPTIONAL_X.get(comp, ()) if c in h.columns]
    xs = [c for c in h.columns if c != "target" and c not in opt]
    if opt and h[opt].notna().all(axis=1).sum() >= MIN_OBS:
        h = h.dropna(subset=opt)
        xs += opt
    h = h[xs + ["target"]]
    A = np.column_stack([np.ones(len(h))] + [h[c].to_numpy() for c in xs])
    y = h["target"].to_numpy()
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ b
    dof = max(len(y) - len(b), 1)
    return {"const": round(float(b[0]), 4), "coef": {c: round(float(v), 4) for c, v in zip(xs, b[1:])},
            "n": int(len(y)), "r2": round(float(1 - resid.var() / y.var()), 3) if y.var() > 0 else None,
            "resid_sd": round(float(np.sqrt((resid ** 2).sum() / dof)), 3),
            "sample": [str(h.index[0]), str(h.index[-1])], "target": C.TARGET[comp]}


def signature(view: C.View) -> tuple:
    """What a fit depends on that can change inside a quarter: the quarter BEA has reached and its
    printed history as the view sees it (an annual update or a second estimate changes it)."""
    return (str(view.known_quarter()),) + tuple(
        round(float(view.quarterly(C.TARGET[c]).loc[FIT_START:].sum()), 3) for c in C.COMPONENTS)


def fit(through=None, start=FIT_START, view: C.View | None = None) -> dict:
    hist = histories(view)
    return {comp: fit_one(comp, through, start, hist=hist) for comp in C.COMPONENTS}


def apply(coefs: dict, comp: str, x: dict) -> float | None:
    """The bridged value for one component from its regressors (None if any is missing)."""
    c = coefs[comp]
    out = c["const"]
    for k, b in c["coef"].items():
        v = x.get(k)
        if v is None or not np.isfinite(v):
            return None
        out += b * v
    return float(out)


def data_hash() -> str:
    """A fingerprint of every target series from FIT_START and of the regressors the bridges take:
    changes when BEA revises or adds a quarter, or when an input joins or leaves a bridge."""
    h = hashlib.sha256(json.dumps(C.EXTRA_X, sort_keys=True).encode())
    for comp in C.COMPONENTS:
        s = S.quarterly(C.TARGET[comp]).loc[FIT_START:]
        h.update(f"{comp}:{','.join(f'{q}={v:.4f}' for q, v in s.items())};".encode())
    return h.hexdigest()[:16]


def save(coefs: dict) -> None:
    S.REF.mkdir(parents=True, exist_ok=True)
    COEF_FILE.write_text(json.dumps({"fitted": dt.date.today().isoformat(), "fit_start": str(FIT_START),
                                     "excluded": [str(q) for q in EXCLUDE], "data_hash": data_hash(),
                                     "components": coefs}, indent=1))


def fresh_first_prints() -> None:
    """Before a refit: the archive copies behind the first-print targets must hold BEA's latest advance
    estimate (`vintages.refresh_stale`). A failed download is printed, never raised; the fit then uses
    the copy on disk, as it always did."""
    import sys
    from . import calendar as cal
    from . import vintages as V
    try:
        since = cal.advance_gdp_date(S.quarterly("gdp_growth").index[-1])
        if not since or since > dt.date.today().isoformat():
            return
        got = V.refresh_stale([C.TARGET[c] for c in FIRST_PRINT_TARGETS], since)
        bad = [f"{k}: {v}" for k, v in got.items() if str(v).startswith("ERR")]
        if bad:
            print(f"first-print archive not refreshed ({bad[0]}); the fit uses the copy on disk", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — never stops a refit
        print(f"first-print archive not checked ({e!r}); the fit uses the copy on disk", file=sys.stderr)


def current() -> tuple[dict, bool]:
    """(coefficients, refit?) — the saved fit, refit first if BEA's history has moved under it."""
    try:
        saved = json.loads(COEF_FILE.read_text())
    except Exception:  # noqa: BLE001
        saved = {}
    if saved.get("data_hash") == data_hash() and saved.get("components"):
        return saved["components"], False
    _HIST.clear()
    fresh_first_prints()
    coefs = fit()
    save(coefs)
    return coefs, True


def load() -> dict:
    """The saved coefficients; fits and saves them if the file is missing (a fresh checkout)."""
    if not COEF_FILE.exists():
        save(fit())
    return json.loads(COEF_FILE.read_text())["components"]


def table(coefs: dict) -> str:
    lines = [f"{'component':14s} {'target':22s} {'const':>7s} {'slopes':28s} {'R2':>5s} {'resid sd':>8s} {'n':>3s}  sample"]
    for comp, c in coefs.items():
        sl = ", ".join(f"{k} {v:+.3f}" for k, v in c["coef"].items())
        lines.append(f"{comp:14s} {c['target']:22s} {c['const']:+7.3f} {sl:28s} {c['r2'] if c['r2'] is not None else float('nan'):5.2f} "
                     f"{c['resid_sd']:8.2f} {c['n']:3d}  {c['sample'][0]}-{c['sample'][1]}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true", help="refit on FIT_START onward and save")
    a = ap.parse_args()
    if a.fit:
        coefs = fit()
        save(coefs)
        print(f"wrote {COEF_FILE}")
    else:
        coefs = load()
    print(table(coefs))
