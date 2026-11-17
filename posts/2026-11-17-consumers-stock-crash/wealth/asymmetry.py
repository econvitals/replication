"""Question 3: are increases and decreases in wealth symmetric?

    python 04_asymmetry.py <out dir>

  A. Distributed lag with real holding gains on stocks and housing entered separately for gains and losses.
     Variants: split at zero real gain (main), at zero nominal gain, large versus small moves.
  B. State dependence: gains while wealth is below its previous peak versus gains at new highs.
  C. Levels: wealth/income split into its previous peak and the shortfall from that peak.
Writes q3_asymmetry.csv, q3_levels.csv, q3_counts.csv and fig08-fig09.
"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import *

OUT = Path(sys.argv[1])
d = load(OUT)
x = add_basics(d)
END = str(x["cy"].last_valid_index())
periods = [("1955Q1", "2019Q4"), ("1955Q1", END), ("1955Q1", "1989Q4"), ("1990Q1", "2019Q4"), ("1990Q1", END)]
yl = d["r_dpi"].shift(1)

# nominal gains over income, to split by the sign of the nominal change
x["gS_nom"] = (d["g_S"] * 1e6 / (d["p_pce"] / 100) / (d["pop"] * 1000)) / yl
x["gH_nom"] = (d["g_H"] * 1e6 / (d["p_pce"] / 100) / (d["pop"] * 1000)) / yl

def fit_split(a, b, pos_mask, J=8, drop=()):
    """pos_mask[k] is a boolean series: True where the quarter counts as a 'gain' for type k."""
    X = pd.DataFrame(index=x.index)
    for k in ["gS", "gH"]:
        gp = x[k].where(pos_mask[k], 0.0)
        gn = x[k].where(~pos_mask[k], 0.0)
        for j in range(J + 1):
            X[f"{k}p_{j}"] = gp.shift(j)
            X[f"{k}n_{j}"] = gn.shift(j)
    for j in range(J + 1):
        X[f"gO_{j}"] = x["gO"].shift(j)
    for j in range(5):
        X[f"dy_{j}"] = x["dy"].shift(j)
    for j in range(3):
        X[f"du_{j}"] = x["du"].shift(j); X[f"drr_{j}"] = x["drr"].shift(j)
    if b >= "2020Q1":
        X[DUMS] = x[DUMS]
    for q in drop:
        X[f"X{q}"] = (x.index == q).astype(float)
    return ols(x["dc"].loc[a:b], X.loc[a:b], lags=4)

variants = {
    "real gain above or below zero": {k: x[k] > 0 for k in ["gS", "gH"]},
    "nominal gain above or below zero": {"gS": x["gS_nom"] > 0, "gH": x["gH_nom"] > 0},
}
# state: real wealth per person below its previous peak at the start of the quarter
for k, col in [("gS", "r_S"), ("gH", "r_H")]:
    lvl = d[col].shift(1)
    x[f"{k}_under"] = lvl < lvl.cummax().shift(1)
variants["wealth at a new high versus below its previous peak"] = {k: ~x[f"{k}_under"] for k in ["gS", "gH"]}

rows, counts = [], []
for name, mask in variants.items():
    for a, b in periods:
        m = fit_split(a, b, mask)
        for k in ["gS", "gH"]:
            sel = x.loc[a:b]
            counts.append(dict(variant=name, start=a, end=b, asset=k, n=int(m.nobs),
                               n_down=int((~mask[k].loc[a:b] & sel[k].notna()).sum())))
            for h in [0, 1, 2, 4, 8]:
                p = lincom(m, [f"{k}p_{j}" for j in range(h + 1)])
                n = lincom(m, [f"{k}n_{j}" for j in range(h + 1)])
                names = [f"{k}p_{j}" for j in range(h + 1)] + [f"{k}n_{j}" for j in range(h + 1)]
                diff, dse = lincom(m, names, [1] * (h + 1) + [-1] * (h + 1))
                rows.append(dict(variant=name, start=a, end=b, asset=k, h=h, up=100 * p[0], up_se=100 * p[1],
                                 down=100 * n[0], down_se=100 * n[1], diff=100 * diff, diff_se=100 * dse, t=diff / dse))
# is the housing-loss result one episode? Leave out the quarters of the housing bust.
bust = pd.period_range("2007Q1", "2012Q4", freq="Q")
m = fit_split("1955Q1", "2019Q4", variants["real gain above or below zero"], drop=bust)
for k in ["gS", "gH"]:
    for h in [4, 8]:
        p_ = lincom(m, [f"{k}p_{j}" for j in range(h + 1)]); n_ = lincom(m, [f"{k}n_{j}" for j in range(h + 1)])
        names = [f"{k}p_{j}" for j in range(h + 1)] + [f"{k}n_{j}" for j in range(h + 1)]
        diff, dse = lincom(m, names, [1] * (h + 1) + [-1] * (h + 1))
        rows.append(dict(variant="housing bust 2007–2012 left out", start="1955Q1", end="2019Q4", asset=k, h=h, up=100 * p_[0], up_se=100 * p_[1],
                         down=100 * n_[0], down_se=100 * n_[1], diff=100 * diff, diff_se=100 * dse, t=diff / dse))
res = pd.DataFrame(rows)
res.to_csv(OUT / "q3_asymmetry.csv", index=False)
pd.DataFrame(counts).to_csv(OUT / "q3_counts.csv", index=False)
pd.set_option("display.width", 250)
print(res[res.h.isin([2, 4, 8])].round(2).to_string())
print(pd.DataFrame(counts).to_string())

# ---- C. levels: previous peak and shortfall ------------------------------------------------------
rows = []
for k, col in [("S", "r_S"), ("H", "r_H")]:
    lvl = d[col].shift(1)
    peak = lvl.cummax()
    x[f"{k}peak_y"] = peak / d["r_dpi"]
    x[f"{k}short_y"] = (lvl - peak) / d["r_dpi"]
for a, b in periods:
    X = x[["Speak_y", "Sshort_y", "Hpeak_y", "Hshort_y", "Oy"] + CTL].copy()
    if b >= "2020Q1":
        X[DUMS] = x[DUMS]
    m = ols(x["cy"].loc[a:b], X.loc[a:b], lags=8)
    for k in ["S", "H"]:
        diff, dse = lincom(m, [f"{k}short_y", f"{k}peak_y"], [1, -1])
        rows.append(dict(start=a, end=b, asset=k, peak=100 * m.params[f"{k}peak_y"], peak_se=100 * m.bse[f"{k}peak_y"],
                         shortfall=100 * m.params[f"{k}short_y"], shortfall_se=100 * m.bse[f"{k}short_y"],
                         diff=100 * diff, t=diff / dse))
lv = pd.DataFrame(rows)
lv.to_csv(OUT / "q3_levels.csv", index=False)
print(lv.round(2).to_string())

# ---- charts ------------------------------------------------------------------------------------
main = res[res.variant == "real gain above or below zero"]

def bars(asset, title, path):
    fig, ax = plt.subplots(figsize=(8, 5))
    sets = [(("1955Q1", "2019Q4"), "1955–2019"), (("1990Q1", END), f"1990–{END[:4]}")]
    hs = [1, 4, 8]
    pos, labels = [], []
    xx = 0
    for (a, b), lab in sets:
        for h in hs:
            q = main[(main.start == a) & (main.end == b) & (main.asset == asset) & (main.h == h)].iloc[0]
            ax.bar(xx - 0.2, q.up, width=0.4, color=C["primary"], label="Gains" if xx == 0 else None)
            ax.bar(xx + 0.2, q.down, width=0.4, color=C["highlight"], label="Losses" if xx == 0 else None)
            ax.errorbar([xx - 0.2, xx + 0.2], [q.up, q.down], yerr=[1.645 * q.up_se, 1.645 * q.down_se], fmt="none", ecolor=C["ink"], lw=1, capsize=3)
            pos.append(xx); labels.append(f"{h} qtr{'s' if h > 1 else ''}\n{lab}")
            xx += 1
        xx += 0.5
    ax.axhline(0, color=C["ink"], lw=0.8)
    ax.set_xticks(pos); ax.set_xticklabels(labels, fontsize=8.5)
    ax.legend(loc="upper left", fontsize=9)
    finish(fig, ax, title, "Cumulative cents of annual spending per dollar of real gain or loss, by quarters elapsed", path,
           note="Note: A positive bar for losses means spending falls when wealth falls. Whiskers are 90 percent confidence intervals.")

bars("gS", "Spending Response to Stock Gains and Stock Losses", OUT / "fig08_asymmetry_stocks.png")
bars("gH", "Spending Response to Housing Gains and Housing Losses", OUT / "fig09_asymmetry_housing.png")
print("done")
