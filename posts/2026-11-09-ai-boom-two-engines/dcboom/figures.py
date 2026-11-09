"""figures.py: every figure in the post, in plain matplotlib (same series, titles, units and periods as the
post's figures; the post's typeface and layout are not reproduced pixel for pixel).

  figure 1   Selected U.S. capital-expenditure booms (Van Nieuwerburgh 2026, Table 1)
  figure 2   Investment in computers, communications and data centers, percent of GDP, 1990-2026Q3
  figure 3   Seven AI companies and the rest of the U.S. stock market, index Nov. 30, 2022 = 100
  figure 4   Business investment, percent of GDP; real construction spending growth by type
  figure 5   Trade balance: data-center goods vs everything else, January-September of each year
  figure 6   Real GDP and unemployment, the buildout alone (dotted: the buildout held at its 2026Q4 share)
  figure 7   Where the buildout's spending went, 2026Q3
  figure 8   Real GDP and unemployment, the buildout alone and with the stock gain
  figure 9   Where the spending went with the stock gain, 2026Q3
  figure 10  Net exports with and without the boom
  appendix figures 1-4: every table variable, both scenarios, through 2028
Writes output/figures/*.png and output/results/figure_data.json (the plotted values, for verify.py).
"""
import json

import numpy as np
import pandas as pd

from . import common as C
from . import descriptive as D
from . import engine as E
from . import paths

K = C.COLORS
FIGDATA = {}


WRAP = {"Business Investment Excluding Data Centers": "Business Investment\nExcluding Data Centers"}   # too wide for a half-width panel


def _style(ax, ttl, unit, zero=True):
    ax.set_title(WRAP.get(ttl, ttl), fontsize=11, fontweight="bold", pad=14)
    ax.text(0.0, 1.015, unit, transform=ax.transAxes, fontsize=7.5, color=K["muted"])
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color=K["gridline"], lw=0.7); ax.set_axisbelow(True)
    ax.tick_params(labelsize=8)
    if zero:
        ax.axhline(0, color=K["ink"], lw=0.8)


def _save(plt, fig, name, note=C.SRC_MODEL):
    fig.text(0.02, 0.01, note, fontsize=6.8, color=K["muted"], style="italic", va="bottom")
    fig.savefig(paths.OUT_FIGS / name, dpi=200, facecolor=K["background"])
    plt.close(fig)


# ------------------------------------------------------------------ model figures
def panels(plt, ext, spec, scen, name, dotted):
    cols = {"A": K["primary"], "B": K["secondary"]}
    n = len(spec); ncol = 2; nr = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nr, ncol, figsize=(7.6, 3.1 * nr + 1.1), dpi=200, squeeze=False)
    fig.patch.set_facecolor(K["background"])
    i1 = pd.period_range("2023Q1", C.LAST, freq="Q"); i2 = pd.period_range(C.LAST, C.END, freq="Q")
    FIGDATA[name] = {}
    for ax, (ttl, unit, fn) in zip(axes.flat, spec):
        FIGDATA[name][ttl] = {}
        for s in scen:
            y = fn(ext[f"{s}_s75"])
            ax.plot(C.xs(i1), y.reindex(i1).values, color=cols[s], lw=2.0, label=C.LAB[s])
            ax.plot(C.xs(i2), y.reindex(i2).values, color=cols[s], lw=2.0, ls=(0, (2, 2)))
            FIGDATA[name][ttl][s] = {str(q): round(float(y.loc[q]), 5) for q in y.index}
        ax.axvline(C.xs([C.LAST])[0], color=K["gridline"], lw=0.8)
        _style(ax, ttl, unit)
        ax.set_xlim(2023, 2029.0); ax.set_xticks([2023, 2024, 2025, 2026, 2027, 2028])
    for ax in list(axes.flat)[n:]:
        ax.axis("off")
    h, l = axes.flat[0].get_legend_handles_labels()
    from matplotlib.lines import Line2D
    h.append(Line2D([0], [0], color=K["muted"], lw=2.0, ls=(0, (2, 2)))); l.append("Projection if the boom continues")
    fig.legend(h, l, loc="lower center", ncol=len(h), frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.075 if nr == 1 else 0.05))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.9, bottom=0.24 if nr == 1 else 0.15, hspace=0.6, wspace=0.28)
    _save(plt, fig, name, note=C.SRC_MODEL + "\n" + dotted)


def waterfall(plt, a, e, imported, name, title, unit):
    st = C.waterfall_steps(a, e, imported)
    FIGDATA[name] = {k: round(v, 5) for k, v in st.items()}
    steps = [(k, v) for k, v in st.items() if k != "Real GDP"]
    gdp = st["Real GDP"]
    fig, ax = plt.subplots(figsize=(7.6, 4.4), dpi=200); fig.patch.set_facecolor(K["background"])
    run_ = 0.0
    for i, (lab, v) in enumerate(steps):
        bottom = run_ if v >= 0 else run_ + v
        ax.bar(i, abs(v), 0.6, bottom=bottom, color=K["primary"] if v >= 0 else K["secondary"])
        ax.text(i, run_ + v + (0.03 if v >= 0 else -0.03), ("0.00" if abs(v) < 0.005 else f"{v:+.2f}".replace("-", "−")),
                ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5)
        run_ += v
    ax.bar(len(steps), gdp, 0.6, color=K["ink"])
    ax.text(len(steps), gdp + 0.03, f"{gdp:+.2f}".replace("-", "−"), ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    labels = ["Data-center\nspending", "Imported\nequipment", "Consumer\nspending", "Other business\ninvestment", "Housing",
              "Everything\nelse", "Real GDP"]
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=8)
    _style(ax, title, unit)
    ax.set_ylim(min(0, run_) - 0.1, st["Data-center spending"] + 0.25)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.85, bottom=0.19)
    _save(plt, fig, name)


def model_figures():
    plt = C.plt_setup()
    runs, ext, a = C.post_runs(), C.extend_runs(), C.actual()
    D1 = "Dotted: the boom held at its 2026Q4 share of GDP."
    D2 = "Dotted: the buildout held at its 2026Q4 share of GDP, and the stock gain held at its early-November level."
    gdp = ("Real GDP", "Percent difference from the economy without the boom", lambda e: e["xgdp"])
    une = ("Unemployment Rate", "Percentage points", lambda e: e["lur"])
    panels(plt, ext, [gdp, une], ["A"], "figure 6 gdp and unemployment.png", D1)
    imported = E.import_share_series(0.75)[0]
    waterfall(plt, a, runs["A_s75"], imported, "figure 7 where the spending went.png",
              "Where the Buildout’s Spending Went, 2026Q3", "Percent of GDP; the buildout alone, without the stock gain")
    panels(plt, ext, [gdp, une], ["A", "B"], "figure 8 gdp and unemployment with stock gain.png", D2)
    waterfall(plt, a, runs["B_s75"], imported, "figure 9 where the spending went with stock gain.png",
              "Where the Spending Went With the Stock Gain, 2026Q3", "Percent of GDP; the buildout plus the AI stock-market gain")
    # figure 10: net exports, actual and without
    fig, ax = plt.subplots(figsize=(7.6, 4.2), dpi=200); fig.patch.set_facecolor(K["background"])
    i2 = pd.period_range("2022Q1", C.LAST, freq="Q")
    ax.plot(C.xs(i2), a.loc[i2, "nx_share"].values, color=K["ink"], lw=2.2, label="Actual")
    FIGDATA["figure 10 net exports.png"] = {"Actual": {str(q): round(float(a.loc[q, "nx_share"]), 5) for q in i2}}
    for s, lab, col in (("A", "Without the buildout", K["primary"]), ("B", "Also without the stock gain", K["secondary"])):
        w = a.loc[i2, "nx_share"] - runs[f"{s}_s75"]["nx"].reindex(i2).fillna(0.0)
        ax.plot(C.xs(i2), w.values, color=col, lw=2.0, label=lab)
        FIGDATA["figure 10 net exports.png"][lab] = {str(q): round(float(w.loc[q]), 5) for q in i2}
    _style(ax, "Net Exports With and Without the Boom", "Percent of GDP")
    ax.set_xticks([2022, 2023, 2024, 2025, 2026])
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.85, bottom=0.25)
    _save(plt, fig, "figure 10 net exports.png")
    # the appendix: every table variable, both scenarios, dotted through 2028
    PCT, PP = "Percent difference in level", "Percentage points"
    A1 = [("Real GDP", PCT, lambda e: e["xgdp"]), ("Consumer Spending", PCT, lambda e: e["ecnia"]),
          ("Business Investment", PCT, lambda e: e["ebfi"]),
          ("Business Investment Excluding Data Centers", PCT, lambda e: e["ebfio"]),
          ("Residential Investment", PCT, lambda e: e["eh"]), ("Exports", PCT, lambda e: e["ex"]),
          ("Imports", PCT, lambda e: e["em"]),
          ("Data-Center Investment Above Trend", "Percent of GDP", lambda e: e["dcinv"])]
    A2 = [("Unemployment Rate", PP, lambda e: e["lur"]), ("Core PCE Inflation (Four Quarters)", PP, lambda e: e["picx4"]),
          ("Federal Funds Rate", PP, lambda e: e["rff"]), ("10-Year Treasury Yield", PP, lambda e: e["rg10"]),
          ("30-Year Mortgage Rate", PP, lambda e: e["rme"]), ("Net Exports", "Percentage points of GDP", lambda e: e["nx"]),
          ("Real Dollar", "Percent difference (higher = stronger)", lambda e: e["fpxr"]),
          ("Household Stock-Market Wealth", PCT, lambda e: e["wpsn"])]
    panels(plt, ext, A1[:4], ["A", "B"], "appendix figure 1 gdp and spending.png", D2)
    panels(plt, ext, A1[4:], ["A", "B"], "appendix figure 2 housing and trade.png", D2)
    panels(plt, ext, A2[:4], ["A", "B"], "appendix figure 3 rates and inflation.png", D2)
    panels(plt, ext, A2[4:], ["A", "B"], "appendix figure 4 mortgage, net exports, dollar, stocks.png", D2)


# ------------------------------------------------------------------ descriptive figures
RECESSIONS = [(1990.5, 1991.0), (2001.0, 2001.75), (2007.75, 2009.25), (2020.0, 2020.25)]   # NBER peaks to troughs, quarterly


def descriptive_figures():
    plt = C.plt_setup()
    # figure 1
    b = D.capex_booms().sort_values("avg_capex_pct_gdp")
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200); fig.patch.set_facecolor(K["background"])
    labs = [f"{r.episode}, {r.period}" + (" (projected)" if r.projected else "") for r in b.itertuples()]
    ax.barh(range(len(b)), b.avg_capex_pct_gdp, 0.62, color=[K["highlight"] if p else K["primary"] for p in b.projected])
    for i, v in enumerate(b.avg_capex_pct_gdp):
        ax.text(v + 0.04, i, f"{v:.2f}", va="center", fontsize=11)
    ax.set_yticks(range(len(b))); ax.set_yticklabels(labs, fontsize=11); ax.set_xlim(0, 4.2); ax.set_xticks([0])
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.suptitle("Selected U.S. Capital-Expenditure Booms", fontsize=15, fontweight="bold", y=0.97)
    fig.text(0.5, 0.885, "Average annual capital expenditure, percent of GDP", ha="center", fontsize=11)
    fig.subplots_adjust(left=0.42, right=0.97, top=0.84, bottom=0.12)
    _save(plt, fig, "figure 1 capex booms.png", note="Stijn Van Nieuwerburgh, ‘Financing the AI Buildout,’ Brookings Papers on Economic Activity, 2026.")
    FIGDATA["figure 1 capex booms.png"] = dict(zip(b.episode, b.avg_capex_pct_gdp))
    # figure 2
    sh = D.buildout_shares()
    x = C.xs(sh.index)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200); fig.patch.set_facecolor(K["background"])
    for a0, a1 in RECESSIONS:
        ax.axvspan(a0, a1, color="#EBEBEB", lw=0, zorder=0)
    ax.stackplot(x, sh.comp, sh.commeq, sh.commst, sh.dc, colors=[K["primary"], K["secondary"], K["gray"], K["highlight"]],
                 labels=["Computers", "Telecom equipment", "Telecom structures", "Data centers"], alpha=0.85)
    ax.plot(x, sh.total, color=K["ink"], lw=2.5, label="Total")
    _style(ax, "Investment in Computers, Communications and Data Centers", "Percent of GDP", zero=False)
    ax.text(1.0, 1.015, "Through Q3 2026", transform=ax.transAxes, ha="right", fontsize=7.5, color=K["muted"])
    ax.set_ylim(0, 3); ax.set_xlim(1990, 2026.75); ax.set_xticks(range(1990, 2026, 5))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=5, frameon=False, fontsize=8)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.25)
    _save(plt, fig, "figure 2 buildout share of gdp.png",
          note="Note: Private fixed investment in computers and peripherals, communication equipment and structures, and data centers. Data centers\n"
               "are identified from 2014 (Census; BEA from 2020); before that they are in office buildings. Source: BEA; Census; author’s calculations.")
    FIGDATA["figure 2 buildout share of gdp.png"] = {"total_2026Q3": round(float(sh.total.iloc[-1]), 4)}
    # figure 3
    st = D.stock_index()
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200); fig.patch.set_facecolor(K["background"])
    ax.plot(st.x, st.seven, color=K["primary"], lw=3); ax.plot(st.x, st.rest, color=K["secondary"], lw=3)
    ax.axhline(100, color=K["ink"], lw=1.5, ls=":")
    for col, c in (("seven", K["primary"]), ("rest", K["secondary"])):
        ax.plot(st.x.iloc[-1], st[col].iloc[-1], "o", color=c)
        ax.text(st.x.iloc[-1] + 0.05, st[col].iloc[-1], f"{st[col].iloc[-1]:.0f}", color=c, va="center", fontsize=11)
    ax.text(2023.15, 255, "Seven AI companies", color=K["primary"], fontsize=13, fontweight="bold")
    ax.text(2024.75, 70, "Rest of the market", color=K["secondary"], fontsize=13, fontweight="bold")
    _style(ax, "Seven AI Companies and the Rest of the U.S. Stock Market", "Index, November 30, 2022 = 100", zero=False)
    ax.set_ylim(0, 400); ax.set_xlim(2022.85, 2026.95); ax.set_xticks([2023, 2024, 2025, 2026])
    fig.subplots_adjust(left=0.08, right=0.95, top=0.88, bottom=0.2)
    _save(plt, fig, "figure 3 ai stocks vs rest.png",
          note="Note: The seven are Nvidia, Microsoft, Alphabet, Amazon, Meta, Broadcom and Oracle; the rest of the market is all other U.S. public\n"
               "companies. Quarter-end values; the last is Nov. 5, 2026. Source: SEC; Nasdaq; Federal Reserve Board; author’s calculations.")
    FIGDATA["figure 3 ai stocks vs rest.png"] = {"seven_latest": round(float(st.seven.iloc[-1]), 2), "rest_latest": round(float(st.rest.iloc[-1]), 2)}
    # figure 4
    inv = D.investment_shares()
    con = D.construction_bars().sort_values("real")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 6.4), dpi=200, gridspec_kw={"width_ratios": [1, 1.25]})
    fig.patch.set_facecolor(K["background"])
    xi = C.xs(inv.index)
    a1.plot(xi, inv.nonres, color=K["primary"], lw=2.5); a1.plot(xi, inv.nonres_ex, color=K["secondary"], lw=2.5)
    a1.text(xi[-1] + 0.15, inv.nonres.iloc[-1], f"Total {inv.nonres.iloc[-1]:.1f}", color=K["primary"], va="center", fontsize=10)
    a1.text(xi[-1] + 0.15, inv.nonres_ex.iloc[-1], f"Excluding\nbuildout\n{inv.nonres_ex.iloc[-1]:.1f}", color=K["secondary"], va="center", fontsize=10)
    _style(a1, "Business Investment", "Percent of GDP", zero=False)
    a1.set_ylim(11, 16); a1.set_xlim(2015, 2026.75); a1.set_xticks([2015, 2019, 2023])
    cols = [K["highlight"] if g == "Data centers" else (K["secondary"] if g == "Residential" else K["primary"]) for g in con.group]
    a2.barh(range(len(con)), con.real, 0.62, color=cols)
    for i, v in enumerate(con.real):
        a2.text(v + (1 if v >= 0 else -1), i, (f"+{v:.1f}" if v > 0 else f"{v:.1f}".replace("-", "−")), va="center",
                ha="left" if v >= 0 else "right", fontsize=8)
    a2.set_yticks(range(len(con))); a2.set_yticklabels(con.label, fontsize=8); a2.axvline(0, color=K["ink"], lw=0.8)
    for sp in ("top", "right"):
        a2.spines[sp].set_visible(False)
    a2.set_title("Real Construction Spending Growth", fontsize=11, fontweight="bold", pad=14)
    a2.text(0.0, 1.015, "Percent change, real, September 2025 to September 2026", transform=a2.transAxes, fontsize=7.5, color=K["muted"])
    a2.set_xlim(-45, 100)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.9, bottom=0.17, wspace=0.62)
    _save(plt, fig, "figure 4 investment and construction.png",
          note="Note: Left: Business investment is private nonresidential fixed investment. ‘Excluding buildout’ leaves out computers and peripheral equipment,\n"
               "communication equipment and data centers. Right: Nominal Census spending deflated by the PPI for Final Demand Construction. Office ex-data-center\n"
               "is total office construction less the Census data-center line. Source: BEA; Census; BLS; author’s calculations.")
    FIGDATA["figure 4 investment and construction.png"] = {"nonres_2026Q3": round(float(inv.nonres.iloc[-1]), 4),
                                                           "nonres_ex_2026Q3": round(float(inv.nonres_ex.iloc[-1]), 4),
                                                           **{f"real_{r.label}": round(float(r.real), 4) for r in con.itertuples()}}
    # figure 5
    tr = D.trade_ytd()
    fig, ax = plt.subplots(figsize=(8, 5), dpi=200); fig.patch.set_facecolor(K["background"])
    ax.bar(tr.index, tr.other, 0.72, color=K["primary"], label="Everything else")
    ax.bar(tr.index, tr.dc, 0.72, bottom=tr.other, color=K["secondary"], label="Data-center goods")
    _style(ax, "Trade Balance: Data-Center Goods vs. Everything Else", "Percent of GDP, year to date through September")
    ax.set_ylim(-4, 0); ax.set_xticks(range(2015, 2027, 2))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False, fontsize=9)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.22)
    _save(plt, fig, "figure 5 trade balance.png",
          note="Note: Each bar covers the same months of the year. Data-center goods are computers, computer parts and accessories, semiconductors,\n"
               "and telecommunications equipment. Source: Census Bureau and Bureau of Economic Analysis; author’s calculations.")
    FIGDATA["figure 5 trade balance.png"] = {str(y): {c: round(float(tr.loc[y, c]), 4) for c in ("other", "dc", "total")} for y in tr.index}


def check_chart_data():
    """Compare the descriptive figures' data with the chart data used for the post (data/as_used/)."""
    A = paths.AS_USED
    a = pd.read_csv(A / "fig2_buildout_share.csv"); s = D.buildout_shares().reset_index(drop=True)
    d2 = max(np.abs(a[c].values - s[c].round(4).values).max() for c in ["comp", "commeq", "commst", "dc", "total"])
    a = pd.read_csv(A / "fig3_stocks.csv"); s = D.stock_index()
    d3 = max(np.abs(a.seven.values - s.seven.round(1).values).max(), np.abs(a.rest.values - s.rest.round(1).values).max())
    a = pd.read_csv(A / "fig4_left_business_investment.csv"); s = D.investment_shares().reset_index(drop=True)
    d4 = max(np.abs(a[c].values - s[c].round(3).values).max() for c in ["nonres", "nonres_ex"])
    a = pd.read_csv(A / "fig4_right_construction.csv").set_index("label"); s = D.construction_bars().set_index("label")
    d4r = float(np.abs(a["value"] - s.loc[a.index, "real"].round(1)).max())
    a = pd.read_csv(A / "fig5_trade_balance.csv"); s = D.trade_ytd()
    d5 = max(np.abs(a[c].values - s[c].values).max() for c in ["other", "dc", "total"])
    print(f"figures: largest difference from the post's chart data: figure 2 {d2:.4f}, figure 3 {d3:.1f}, figure 4 {d4:.3f} "
          f"and {d4r:.1f}, figure 5 {d5:.4f} (the post's figure 5 divided by a monthly interpolation of GDP)")


def main():
    paths.ensure()
    descriptive_figures()
    if paths.using_frozen_data():
        check_chart_data()
    model_figures()
    (paths.OUT_RESULTS / "figure_data.json").write_text(json.dumps(FIGDATA, indent=1))
    print(f"figures: wrote {len(list(paths.OUT_FIGS.glob('*.png')))} PNG files to output/figures/")


if __name__ == "__main__":
    main()
