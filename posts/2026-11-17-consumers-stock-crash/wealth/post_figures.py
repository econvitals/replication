"""The post's Table 1 and Figures 1-7, redrawn from the rebuilt numbers with plain matplotlib (housestyle.py), not
the exact look of the published images. Run from the package folder after every numbers step.
Writes output/figures/table-1.png (+ output/table_1.csv) and output/figures/figure-1.png ... figure-7.png."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "wealth")
import housestyle as B  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

O = Path("output"); FIG = O / "figures"; FIG.mkdir(parents=True, exist_ok=True)
C = B.C; INK, MUTED, BLUE, ORANGE, RED, GRAY, TEAL, BURG = (C[k] for k in ("ink", "muted", "primary", "secondary", "highlight", "gray", "teal", "burgundy"))
N = json.load(open(O / "a1_numbers.json")); P = json.load(open(O / "post_numbers.json")); R = json.load(open(O / "r9_cf_results.json"))
END = R["END"]
MINUS = "−"


def lab(v, d=1):
    s = f"{abs(v):.{d}f}"
    return (MINUS + s) if v < 0 and float(s) != 0 else s


def q2t(q):
    q = str(q)
    return pd.Timestamp(int(q[:4]), (int(q[-1]) - 1) * 3 + 2, 15)


def done(fig, ax, title, units, source, name):
    B.furnish(fig, ax, title, units, source)
    B.save(fig, FIG / name)
    print("wrote", FIG / name)


# ---------------------------------------------------------------- Table 1
t1 = N["table1"]
rows = []
for pct, label in (("25", "Baseline: 25 percent"), ("35", "Bad case: 35 percent"), ("50", "Severe case: 50 percent")):
    r = t1[pct]
    rows.append([label, f"${r['lost_bn'] / 1000:.0f} trillion", f"{r['frbus_earn_4']:.1f}", f"{r['frbus_ret_4']:.1f}",
                 f"{r['r1']:.1f}", f"{r['cf_4']:.1f}", f"{r['r3']:.1f}"])
cols = ["Fall in the stock market", "Stock wealth lost", "FRB/US: lower earnings", "FRB/US: higher return",
        "Spend 1 cent per dollar", "Historical consumption function", "Spend 3 cents per dollar"]
pd.DataFrame(rows, columns=cols).to_csv(O / "table_1.csv", index=False)
fig, ax = plt.subplots(figsize=(10, 2.6)); ax.axis("off")
import textwrap
tb = ax.table(cellText=rows, colLabels=["\n".join(textwrap.wrap(c, 16)) for c in cols], loc="center", cellLoc="center")
tb.auto_set_font_size(False); tb.set_fontsize(8.5); tb.scale(1, 2.2)
for (r_, c_), cell in tb.get_celld().items():
    if r_ == 0: cell.set_height(cell.get_height() * 1.9)
fig.suptitle("Table 1. How Much a Stock Market Fall Would Reduce GDP Growth Over the Next Year (percentage points)", fontsize=11, fontweight="bold")
B.save(fig, FIG / "table-1.png"); print("wrote", FIG / "table-1.png")

# ---------------------------------------------------------------- Figure 1: declines of 20 percent or more since 1946
bm = pd.read_csv(O / "bear_markets.csv")
fig, ax = B.new_fig(); ax.grid(False)
x = np.arange(len(bm))
ax.bar(x, bm["decline"], 0.7, color=[RED if r else GRAY for r in bm["recession"].fillna("")], zorder=3)
for i, v in enumerate(bm["decline"]):
    ax.text(i, v - 1.2, lab(v, 0), ha="center", va="top", fontsize=7.5, color=INK)
ax.set_xticks(x); ax.set_xticklabels([p[:4] for p in bm["peak"]], rotation=90, fontsize=7.5)
ax.axhline(0, color=INK, lw=0.8); ax.set_yticks([]); ax.spines["left"].set_visible(False)
ax.set_ylim(-65, 2)
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=RED), plt.Rectangle((0, 0), 1, 1, color=GRAY)],
          labels=["With a recession", "Without a recession"], loc="lower right", frameon=False, fontsize=8.5)
done(fig, ax, "Figure 1. U.S. Stock Market Declines of 20 Percent or More Since 1946",
     "Peak-to-trough fall in all listed U.S. stocks, excluding estimated dividends, percent",
     "Source: Kenneth R. French data library (CRSP); Shiller; NBER; author’s calculations", "figure-1.png")

# ---------------------------------------------------------------- Figure 2: consumer spending's drag in each recession
rc = pd.read_csv(O / "recession_contributions.csv", index_col=0)
fig, ax = B.new_fig(); ax.grid(False)
x = np.arange(len(rc))
ax.bar(x, rc["C"], 0.66, color=[ORANGE if n == "2001" else BLUE for n in rc.index], zorder=3)
for i, v in enumerate(rc["C"]):
    ax.text(i, v - 0.1, lab(v), ha="center", va="top", fontsize=9, color=INK)
ax.set_xticks(x); ax.set_xticklabels([n + ("*" if n == "1980–82" else "") for n in rc.index], fontsize=8.5)
ax.axhline(0, color=INK, lw=0.8); ax.set_yticks([]); ax.spines["left"].set_visible(False)
done(fig, ax, "Figure 2. The Drag From Consumer Spending in Each Recession",
     "Shortfall in its contribution to real GDP growth, peak to trough, percentage points",
     "Shortfall = growth from peak to trough below the pace of the prior 10 years. *1980 and 1981–82 combined. Sources: BEA; NBER", "figure-2.png")

# ---------------------------------------------------------------- Figure 3: the December 2000 Greenbook and what happened
keys = ["gdp", "pce", "res", "bfi", "gov"]; names = ["GDP", "Consumer\nspending", "Residential\ninvestment", "Business\ninvestment", "Government"]
gb = [P[f"greenbook_2001_{k}"] for k in keys]; act = [P[f"rtdsm_latest_2001_{k}"] for k in keys]
fig, ax = B.new_fig(); ax.grid(False)
x = np.arange(len(keys)); w = 0.34
for off, vals, col, lb in ((-w / 2, gb, GRAY, "Fed staff forecast, December 2000"), (w / 2, act, BLUE, "Actual")):
    ax.bar(x + off, vals, w, color=col, label=lb, zorder=3)
    for xi, v in zip(x + off, vals):
        ax.text(xi, v + (0.3 if v >= 0 else -0.3), lab(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(names, fontsize=8.5); ax.axhline(0, color=INK, lw=0.8)
ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.legend(frameon=False, fontsize=8.5, loc="lower left")
done(fig, ax, "Figure 3. The Fed Staff’s Forecast for 2001 and What Happened",
     "Real growth, fourth quarter of 2000 to fourth quarter of 2001, percent",
     "Sources: Federal Reserve Board staff, Greenbook, December 13, 2000; Federal Reserve Bank of Philadelphia, Real-Time Data Set", "figure-3.png")

# ---------------------------------------------------------------- Figure 4: the value of U.S. stocks relative to GDP
sg = pd.read_csv(O / "stocks_gdp.csv", index_col=0).loc["1952Q1":]
fig, ax = B.new_fig()
t = [q2t(q) for q in sg.index]
ax.plot(t, sg["all_us_stock_pct_gdp"], color=BLUE, lw=2, label="All U.S. corporate stock")
ax.plot(t, sg["household_stock_pct_gdp"], color=ORANGE, lw=2, label="Held by U.S. households")
ax.legend(frameon=False, fontsize=9, loc="upper left")
done(fig, ax, "Figure 4. The Value of U.S. Stocks Relative to GDP", "Market value, percent of GDP",
     "Sources: Federal Reserve Board, Financial Accounts; BEA; author’s calculations", "figure-4.png")

# ---------------------------------------------------------------- Figure 5: spending since 2019 against two models
pth = pd.read_csv(O / "r8_t2_paths_all_2019.csv", index_col=0)
pan = pd.read_csv(O / "panel.csv", index_col=0)
s = pth.loc["2015Q1":END]; y = pan["dpi"].reindex(s.index)
act = 100 * s["actual"] / y; cf = (100 * s["cf"] / y).loc["2019Q1":]; fr = (100 * s["frbus"] / y).loc["2019Q4":].dropna()
fig, ax = B.new_fig()
ax.plot([q2t(q) for q in cf.index], cf, color=BURG, lw=2, label="Historical consumption function")
ax.plot([q2t(q) for q in fr.index], fr, color=TEAL, lw=2, label="Fed’s model (FRB/US)")
ax.plot([q2t(q) for q in act.index], act, color=BLUE, lw=2.6, label="Actual")
ax.axhline(act.loc["2015Q1":"2019Q4"].mean(), color=GRAY, lw=0.8, ls=":")
ax.set_ylim(76, 97); ax.legend(frameon=False, fontsize=9, loc="lower right")
done(fig, ax, "Figure 5. Consumer Spending Since 2019 Compared With Two Models",
     "Personal consumption expenditures, percent of disposable personal income",
     "Sources: BEA; Federal Reserve Board, Financial Accounts and FRB/US; author’s calculations", "figure-5.png")

# ---------------------------------------------------------------- Figure 6: rolling 20-year estimate
rr = pd.read_csv(O / "part3_r11_rolling20.csv", index_col=0).loc["2000Q1":]
fig, ax = B.new_fig(); t = [q2t(q) for q in rr.index]
ax.fill_between(t, rr["S"] - 1.645 * rr["Sse"], rr["S"] + 1.645 * rr["Sse"], color="#9DB9E8", alpha=0.45, lw=0)
ax.plot(t, rr["S"], color=BLUE, lw=2.2)
rx = rr.dropna(subset=["Sx"]); ax.plot([q2t(q) for q in rx.index], rx["Sx"], color=ORANGE, lw=1.8, ls="--", label="Dropping 2020 and 2021")
ax.axhline(0, color=INK, lw=0.8); ax.legend(frameon=False, fontsize=9, loc="upper left")
done(fig, ax, "Figure 6. Spending per Dollar of Stock Wealth, Estimated Over Rolling 20-Year Periods",
     "Cents of annual spending per dollar of stock wealth, 20-year periods ending at the date shown",
     "Shaded: 90 percent confidence interval. Sources: BEA; Federal Reserve Board, Financial Accounts; author’s calculations", "figure-6.png")

# ---------------------------------------------------------------- Figure 7: a 25 percent fall and consumer spending
SIM = Path("data/simulator"); K = json.load(open(SIM / "current.json"))["stock_wealth"]["factor"]
def frbus(shock, var):
    r = json.load(open(SIM / f"{shock}_var_no_fixed.json"))["runs"]["3|balanced|perm"][var]
    return [v * K * 25 / 30 for v in r]
H = 20; lost = N["table1"]["25"]["lost_bn"]; pce_now = float(pan.loc[END, "pce"]) / 1e3
cf19 = R["main"]["1955Q1-2019Q4"]["Sy"] / 100; rho = N["rho19"]
c1 = [0.0] + [-(lost * 0.01 / pce_now * 100)] * H
c3 = [0.0] + [-(lost * 0.03 / pce_now * 100)] * H
ccf = [0.0] + [-(lost * cf19 / pce_now * 100) * (1 - rho ** h) for h in range(1, H + 1)]
fig, ax = B.new_fig()
for yv, lb, col, ls in ((c3, "Spend 3 cents per dollar, right away", ORANGE, "-"), (ccf, "Historical consumption function", BURG, "-"),
                        (frbus("stocks", "ecnia")[:H + 1], "FRB/US, investors demand a higher return", TEAL, "--"),
                        (frbus("stocks_earn", "ecnia")[:H + 1], "FRB/US, investors expect lower earnings", TEAL, "-"),
                        (c1, "Spend 1 cent per dollar, right away", BLUE, "-")):
    ax.plot(range(H + 1), yv, color=col, lw=2, ls=ls, label=lb)
ax.axhline(0, color=INK, lw=0.8); ax.set_xticks([0, 4, 8, 12, 16, 20]); ax.set_xticklabels(["0", "1", "2", "3", "4", "5"])
ax.set_xlabel("Years after the fall"); ax.legend(frameon=False, fontsize=7.8, loc="lower left", ncol=2)
ax.set_ylim(-4.4, 0.2)
done(fig, ax, "Figure 7. What a 25 Percent Stock Market Fall Would Do to Consumer Spending",
     "Real consumer spending, percent difference from a world without the fall",
     "FRB/US as run in the Econvitals Macroeconomic Simulator, with the Fed responding. Source: author’s calculations", "figure-7.png")
json.dump(dict(fig7_cons_4q=dict(r1=c1[4], r3=c3[4], cf=ccf[4], frbus_earn=frbus("stocks_earn", "ecnia")[4], frbus_ret=frbus("stocks", "ecnia")[4])),
          open(O / "figure_numbers.json", "w"), indent=1)
