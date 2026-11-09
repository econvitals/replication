"""common.py: loading the model results and the actual series, and the arithmetic that maps model effects onto
the data. 'Without' levels = actual / (1 + effect/100); 'without' rates and shares = actual - effect."""
import json

import numpy as np
import pandas as pd

from . import paths

Q = pd.Period("2026Q3", "Q")                 # the last quarter of data
Q0_8 = pd.Period("2024Q3", "Q")              # eight quarters earlier: the table's growth window
LAST = Q
END = pd.Period("2028Q4", "Q")

LAB = {"A": "Data centers only", "B": "Data centers plus stock gain"}
COLORS = {"primary": "#4472C4", "secondary": "#ED7D31", "highlight": "#C00000", "gray": "#8C8C8C",
          "ink": "#262626", "muted": "#808080", "gridline": "#D9D9D9", "background": "#FFFFFF", "panel": "#F2F2F2"}
SRC_MODEL = "Source: FRB/US simulations (Federal Reserve Board model and data); BEA; Census; author’s calculations."


def _frames(J):
    idx = pd.PeriodIndex(J["index"], freq="Q")
    return {k: pd.DataFrame(r["eff"], index=idx) for k, r in J["runs"].items() if r.get("ok")}


def post_runs():
    return _frames(json.loads((paths.OUT_RESULTS / "post_runs.json").read_text()))


def post_runs_raw():
    return json.loads((paths.OUT_RESULTS / "post_runs.json").read_text())


def extend_runs():
    return _frames(json.loads((paths.OUT_RESULTS / "post_extend.json").read_text()))


def news_runs():
    J = json.loads((paths.OUT_RESULTS / "news2026.json").read_text())
    out = {}
    for k, v in J.items():
        if k.startswith("news_"):
            out[k] = pd.DataFrame(v["eff"], index=pd.PeriodIndex(v["index"], freq="Q"))
    return out, J


def reversal_runs():
    """The boom ending in 2027 (reversal.py): (holds, worlds, raw), with holds = the world in which the boom holds
    (the baseline) and worlds = {scenario: levels} for the scenarios that solved, quarterly 2022Q1-2030Q4."""
    J = json.loads((paths.OUT_RESULTS / "reversal_runs.json").read_text())
    idx = pd.PeriodIndex(J["index"], freq="Q")
    return (pd.DataFrame(J.get("holds", {}), index=idx),
            {k: pd.DataFrame(r["cf"], index=idx) for k, r in J["runs"].items() if r.get("ok")}, J)


def actual():
    """Actual series 2019Q1-2026Q3 plus the buildout pieces the table and waterfalls need."""
    a = pd.read_csv(paths.OUT_INPUTS / "actual.csv", index_col=0)
    a.index = pd.PeriodIndex(a.index, freq="Q")
    inv = pd.read_csv(paths.OUT_INPUTS / "inv_excess.csv", index_col=0)
    inv.index = pd.PeriodIndex(inv.index, freq="Q")
    a["dc_real"] = (inv["inv_excess"] / 1e6).reindex(a.index).fillna(0.0) / a["pbfi"]
    a["rbfi_x"] = a["rbfi"] - a["dc_real"]                     # business investment excluding the buildout, real
    a["dc_share"] = (100 * inv["inv_excess"] / inv["ngdp"]).reindex(a.index).fillna(0.0)
    return a


def without_level(a, eff, col, v, q):
    return a.loc[q, col] / (1 + float(eff.loc[q, v]) / 100)


def contrib(a, eff, col, v):
    """A component's contribution to the GDP effect, percent of actual real GDP: (actual - without) / GDP."""
    e = eff[v].reindex(a.index).fillna(0.0)
    w = a[col] / (1 + e / 100)
    return 100 * (a[col] - w) / a["rgdp"]


def waterfall_steps(a, e, imported_share_pp):
    """Where the spending went in 2026Q3, percent of GDP: the measured excess spending, less its imported part,
    plus the model's consumer spending, other business investment and housing; everything else is the rest of
    the model's GDP effect (other imports pulled in, inventories, government, exports)."""
    direct = float(a.loc[Q, "dc_share"])
    imp = float(imported_share_pp.loc[Q])
    cons = float(contrib(a, e, "rpce", "ecnia").loc[Q])
    obf = float(contrib(a, e, "rbfi_x", "ebfio").loc[Q])
    resi = float(contrib(a, e, "rres", "eh").loc[Q])
    gdp = float(e.loc[Q, "xgdp"])
    other = gdp - (direct - imp + cons + obf + resi)
    return {"Data-center spending": direct, "Imported equipment": -imp, "Consumer spending": cons,
            "Other business investment": obf, "Housing": resi, "Everything else": other, "Real GDP": gdp}


def xs(idx):
    return np.array([q.year + (q.quarter - 1) / 4 for q in idx])


def plt_setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Serif", "axes.edgecolor": COLORS["ink"], "text.color": COLORS["ink"],
                         "axes.labelcolor": COLORS["ink"], "xtick.color": COLORS["ink"], "ytick.color": COLORS["ink"],
                         "svg.fonttype": "none"})
    return plt
