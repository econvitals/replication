"""Figures A1-A5 for the online appendix to Part 3 of the AI-bubble series, drawn with a
plain stand-in for the house style (housestyle.py). Run from the package folder after cf_calc.py, cf_extras.py,
expanding_rolling.py and appendix_numbers.py. Writes output/figures/figure-a1.png ... figure-a5.png."""
import sys, json, textwrap
from pathlib import Path
sys.path.insert(0, "wealth")
import housestyle as B
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import warnings; warnings.filterwarnings("ignore")

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "output/figures"); OUT.mkdir(parents=True, exist_ok=True)
O = Path("output")
C = B.C; INK, MUTED = C["ink"], C["muted"]; BLUE, ORANGE, RED, GRAY = C["primary"], C["secondary"], C["highlight"], C["gray"]
LIGHT = "#9DB9E8"; TEAL, BURG = C["teal"], C["burgundy"]
R = json.load(open(O / "r9_cf_results.json")); N = json.load(open(O / "a1_numbers.json")); END = R["END"]
ser = pd.read_csv(O / "r9_series.csv", index_col=0)
SRC = "Sources: BEA; Federal Reserve Board, Financial Accounts; author’s calculations"
def q2t(q): q = str(q); return pd.Timestamp(int(q[:4]), (int(q[-1]) - 1) * 3 + 2, 15)
def foot(fig, n=118, size=7.6, bottom=0.17):
    fig.texts[-2].set_text("\n".join(textwrap.wrap(fig.texts[-2].get_text(), n))); fig.texts[-2].set_fontsize(size)
    fig.subplots_adjust(bottom=bottom)

# ---------------------------------------------------------------- A1: fit of the 1955-2019 model
t = [q2t(q) for q in ser.index]
fig, ax = B.new_fig()
ax.axvspan(q2t("2020Q1"), q2t(END) + pd.Timedelta(days=60), color="#EEF2FA", lw=0, zorder=0)
ax.plot(t, ser["fit19"], color=BURG, lw=1.8, zorder=3)
ax.plot(t, ser["cy"], color=BLUE, lw=2.2, zorder=4)
ax.text(q2t("2019Q2"), 96.6, "Shaded: out of sample", fontsize=9, color=MUTED, ha="right", va="top")
ax.legend(handles=[Line2D([0], [0], color=BLUE, lw=2.2, label="Actual"),
                   Line2D([0], [0], color=BURG, lw=1.8, label="Fitted: consumption function estimated on 1955–2019")],
          loc="lower left", bbox_to_anchor=(0.0, 0.0), frameon=False, fontsize=9)
ax.set_ylim(80, 97); ax.set_yticks([80, 85, 90, 95]); ax.set_xlim(q2t("1955Q1") - pd.Timedelta(days=200), q2t(END) + pd.Timedelta(days=200))
B.furnish(fig, ax, "Figure A1. Consumer Spending and the Historical Consumption Function, 1955–2026",
          "Personal consumption expenditures, percent of disposable personal income",
          "Fitted values use the 1955–2019 estimates (Table A3, first column) and actual values of every right-hand-side variable; "
          "after 2019 they are out of sample and are not anchored. The 2020 lockdown quarters fall below the bottom of the scale. " + SRC, datestamp=" ")
foot(fig, bottom=0.2)
B.save(fig, OUT / "figure-a1.png")

# ---------------------------------------------------------------- A2: expanding window
e = pd.read_csv(O / "r9_expanding_path.csv", index_col=0).loc["1990Q1":]
ex = pd.read_csv(Path("output") / "part3_r10_expanding.csv", index_col=0) if (Path("output") / "part3_r10_expanding.csv").exists() else None
t = [q2t(q) for q in e.index]
fig, ax = B.new_fig()
ax.fill_between(t, e["Sy"] - 1.645 * e["Sy_se"], e["Sy"] + 1.645 * e["Sy_se"], color=LIGHT, alpha=0.45, lw=0, zorder=1)
ax.plot(t, e["Sy"], color=BLUE, lw=2.2, zorder=3)
if ex is not None:
    exd = ex.dropna(subset=["Sx"]); ax.plot([q2t(q) for q in exd.index], exd["Sx"], color=ORANGE, lw=1.8, ls="--", zorder=3)
    ax.text(q2t("2023Q2"), 2.75, "Dropping 2020 and 2021", fontsize=8.8, color=ORANGE, ha="center")
ax.axhline(0, color=INK, lw=0.8)
for q, dy in (("1999Q4", 0.55), ("2019Q4", -0.55), (END, -0.7)):
    v = e.loc[q, "Sy"]; ax.plot([q2t(q)], [v], "o", color=BLUE, ms=4.5, zorder=4)
    ax.text(q2t(q) - (pd.Timedelta(days=120) if q == END else pd.Timedelta(0)), v + dy, f"Through {q[:4] if q != END else q[:4] + ' Q' + q[-1]}: {v:.1f}",
            ha="right" if q == END else "center", va="center", fontsize=9.4, color=INK)
ax.text(q2t("1991Q1"), -1.6, "Shaded: 90 percent confidence interval", fontsize=8.6, color=MUTED, ha="left")
ax.set_ylim(-2.5, 5.0); ax.set_xlim(q2t("1990Q1") - pd.Timedelta(days=60), q2t(END) + pd.Timedelta(days=320))
B.furnish(fig, ax, "Figure A5. Spending per Dollar of Stock Wealth, Estimated From 1955 Through Each Quarter",
          "Cents of annual spending per dollar of stock wealth, sample from 1955 to the date shown",
          "The coefficient on stock wealth in the consumption function (Table A3). Samples that reach 2020 include dummies for 2020Q1–2021Q2; "
          "the dashed line drops 2020–2021 instead. " + SRC, datestamp=" ")
foot(fig, bottom=0.2)
B.save(fig, OUT / "figure-a5.png")

# ---------------------------------------------------------------- A3: gains and losses (levels)
a = R["asym"]
groups = [("Estimated 1955–2019", [("Gains", a["1955–2019"]["Gy"], a["1955–2019"]["Gy_se"], BLUE), ("Losses", a["1955–2019"]["Ly"], a["1955–2019"]["Ly_se"], RED)]),
          ("Estimated 1955–2026", [("Gains", a["1955–2026"]["Gy"], a["1955–2026"]["Gy_se"], BLUE), ("Losses", a["1955–2026"]["Ly"], a["1955–2026"]["Ly_se"], RED)]),
          ("1955–2026, recent\ngains separate", [("Gains", a["post"]["Gy"], a["post"]["Gy_se"], BLUE),
                                                             ("Gains since 2019", a["post"]["gp"], a["post"]["gp_se"], "#9DB7E4"),   # gp = Gy + Gpost, the total effect
                                                             ("Losses", a["post"]["Ly"], a["post"]["Ly_se"], RED)])]
fig, ax = B.new_fig()
pos, labs, x0 = [], [], 0.0
for g, bars in groups:
    xs = [x0 + i * 0.85 for i in range(len(bars))]
    for xx, (lab, v, se, col) in zip(xs, bars):
        ax.bar(xx, v, width=0.72, color=col, zorder=3)
        ax.errorbar(xx, v, yerr=1.645 * se, color=INK, capsize=3, lw=1, zorder=4)
        ax.text(xx, max(v + 1.645 * se, 0) + 0.25, f"{v:.1f}", ha="center", va="bottom", fontsize=9.4, color=INK)
    pos.append(np.mean(xs)); labs.append(g); x0 = xs[-1] + 1.6
ax.axhline(0, color=INK, lw=0.8)
ax.set_xticks(pos); ax.set_xticklabels(labs, fontsize=9.6); ax.tick_params(axis="x", length=0)
ax.set_ylim(-2.5, 7.5)
ax.legend(handles=[Patch(color=BLUE, label="Accumulated gains"), Patch(color="#9DB7E4", label="Gains since 2019"), Patch(color=RED, label="Accumulated losses")],
          loc="upper center", ncol=3, frameon=False, fontsize=9)
B.furnish(fig, ax, "Figure A4. Spending per Dollar of Accumulated Stock Gains and Losses",
          "Cents of annual spending per dollar of accumulated real gains or losses since 1952",
          "Whiskers: 90 percent confidence intervals. The consumption function with stock wealth split into accumulated real holding gains, "
          "accumulated real holding losses and the remainder (Table A11). " + SRC, datestamp=" ")
foot(fig, bottom=0.22)
B.save(fig, OUT / "figure-a4.png")

# ---------------------------------------------------------------- A4: the projection since 2019, three anchors
s = ser.loc["2015Q1":]
t = [q2t(q) for q in s.index]
fig, ax = B.new_fig()
cols = {"2019": BURG, "2015–2019": "#B07AA1", "2023": GRAY}
lab = {"2019": "Anchored to 2019", "2015–2019": "Anchored to 2015–2019", "2023": "Anchored to 2023"}
for k in ("2015–2019", "2019", "2023"):
    an = N["anchors"][k]["anchor_pp"]
    st = "2019Q1" if k != "2023" else "2023Q1"
    p = (s["fit19"] + an).loc[st:]
    p = p.copy(); p.loc[[q for q in p.index if q in ("2020Q2", "2020Q3", "2020Q4", "2021Q1", "2021Q2")]] = np.nan
    ax.plot([q2t(q) for q in p.index], p, color=cols[k], lw=1.9 if k == "2019" else 1.6, ls="-" if k == "2019" else "--", zorder=3)
    ax.text(q2t(END) + pd.Timedelta(days=45), p.iloc[-1], f"{p.iloc[-1]:.1f}", fontsize=9, color=cols[k], va="center", ha="left")
ax.plot(t, s["cy"], color=BLUE, lw=2.4, zorder=4)
ax.text(q2t(END) + pd.Timedelta(days=45), s["cy"].iloc[-1] - 0.15, f"{s['cy'].iloc[-1]:.1f}", fontsize=9.5, color=BLUE, va="center", ha="left", fontweight="bold")
ax.legend(handles=[Line2D([0], [0], color=BLUE, lw=2.4, label="Actual")] +
          [Line2D([0], [0], color=cols[k], lw=1.8, ls="-" if k == "2019" else "--", label=lab[k]) for k in ("2015–2019", "2019", "2023")],
          loc="lower left", bbox_to_anchor=(0.0, 0.0), frameon=False, fontsize=9, labelspacing=0.3)
ax.set_ylim(82, 97.5); ax.set_yticks(range(82, 97, 2)); ax.set_xlim(q2t("2015Q1") - pd.Timedelta(days=30), q2t(END) + pd.Timedelta(days=300))
B.furnish(fig, ax, "Figure A2. The Consumption Function’s Projection Since 2019 Depends on Its Starting Point",
          "Personal consumption expenditures, percent of disposable personal income",
          "The 1955–2019 consumption function given the actual values of every variable, shifted so that it matches actual spending on "
          "average in the anchor period. The projections skip 2020Q2–2021Q2, when lockdowns and stimulus payments dominate. "
          "The 2020 lockdown low in actual spending falls below the scale. " + SRC, datestamp=" ")
foot(fig, bottom=0.235)
B.save(fig, OUT / "figure-a2.png")

# ---------------------------------------------------------------- A5: out-of-sample record from every anchor year
o = pd.read_csv(O / "r9_oos_rolling_origin.csv")
o = o[(o["anchor"] <= 2012) | (o["anchor"] == 2019)]
fig, ax = B.new_fig()
xs = o["anchor"].values; xpos = np.where(xs == 2019, 2015.0, xs)
ax.bar(xpos, o["gap_pct"], width=0.75, color=[RED if a_ == 2019 else BLUE for a_ in xs], zorder=3)
ax.plot(xpos, o["stock_part_pct"], "o", color=ORANGE, ms=4.2, zorder=4)
ax.axhline(0, color=INK, lw=0.8)
ax.set_xticks([1970, 1980, 1990, 2000, 2010, 2015]); ax.set_xticklabels(["1970", "1980", "1990", "2000", "2010", "2019"])
ax.axvline(2013.5, color=GRAY, lw=0.8, ls=":")
ax.legend(handles=[Patch(color=BLUE, label="Error after 27 quarters (predicted minus actual spending)"),
                   Patch(color=RED, label="The 2019 run (to the third quarter of 2026)"),
                   Line2D([0], [0], marker="o", color=ORANGE, lw=0, ms=5, label="What the model expected stocks to add")],
          loc="upper left", frameon=False, fontsize=8.6)
ax.set_ylim(-8, 11); ax.set_yticks([-5, 0, 5, 10])
B.furnish(fig, ax, "Figure A3. How Far Off the Same Method Was Six and Three-Quarter Years Later",
          "Percent of actual spending, by the year the projection starts",
          "Each run estimates the consumption function on 1955 to the anchor year, anchors it to that year, feeds in the actual data and is "
          "compared 27 quarters later, the distance from 2019Q4 to 2026Q3. Runs starting 2013–2018 reach the pandemic and are left out. " + SRC, datestamp=" ")
foot(fig, bottom=0.2)
B.save(fig, OUT / "figure-a3.png")
print("wrote", sorted(p.name for p in OUT.glob("figure-a*.png")))
