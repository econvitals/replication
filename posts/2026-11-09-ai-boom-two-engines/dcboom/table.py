"""table.py: the post's summary table, "The Economy With and Without the AI Boom".

Growth rows: annualized growth over the eight quarters 2024Q3-2026Q3. Core PCE inflation: the actual
eight-quarter annualized rate from BEA's index; the model's effect is the average effect on quarterly
annualized core inflation (picxfe) over 2024Q4-2026Q3. Other rows: 2026Q3 values. The data-center row is
by construction (actual = the measured excess, without = 0).
Writes output/results/table_1_summary.csv and output/figures/table 1 summary.png.
"""
import pandas as pd

from . import common as C
from . import paths


def g8(x1, x0):
    return 100 * ((x1 / x0) ** 0.5 - 1)


def build():
    runs, a = C.post_runs(), C.actual()
    A, B = runs["A_s75"], runs["B_s75"]
    Q, Q0 = C.Q, C.Q0_8
    wv = lambda eff, col, v, q: C.without_level(a, eff, col, v, q)
    rows = []
    for lab, col, v in [("Real GDP", "rgdp", "xgdp"), ("Consumer spending", "rpce", "ecnia"), ("Business investment", "rbfi", "ebfi"),
                        ("excluding data centers", "rbfi_x", "ebfio"), ("Residential investment", "rres", "eh"),
                        ("Exports", "rex", "ex"), ("Imports", "rim", "em")]:
        act = g8(a.loc[Q, col], a.loc[Q0, col])
        rows.append(("growth", lab, act, g8(wv(A, col, v, Q), wv(A, col, v, Q0)), g8(wv(B, col, v, Q), wv(B, col, v, Q0))))
    core = a["core_pce_index"]
    act = g8(core.loc[Q], core.loc[Q0])
    qq = pd.period_range(Q0 + 1, Q, freq="Q")
    rows.append(("growth", "Core PCE inflation", act, act - float(A.loc[qq, "picxfe"].mean()), act - float(B.loc[qq, "picxfe"].mean())))
    for lab, col, v in [("Unemployment rate", "unemp", "lur"), ("Federal funds rate", "ffr", "rff"), ("10-year Treasury yield", "t10", "rg10"),
                        ("30-year mortgage rate", "mort", "rme"), ("Net exports (percent of GDP)", "nx_share", "nx")]:
        act = a.loc[Q, col]
        rows.append(("2026Q3", lab, act, act - float(A.loc[Q, v]), act - float(B.loc[Q, v])))
    for lab, col, v in [("Real dollar (index)", "dollar", "fpxr"), ("Stock market value (trillions of dollars)", "mktval", "wpsn")]:
        act = a.loc[Q, col]
        rows.append(("2026Q3", lab, act, wv(A, col, v, Q), wv(B, col, v, Q)))
    dc = float(a.loc[Q, "dc_share"])
    rows.append(("2026Q3", "Data center investment above trend (percent of GDP)", dc, 0.0, 0.0))
    T = pd.DataFrame([(k, l, x, y, z, x - y, x - z) for k, l, x, y, z in rows],
                     columns=["block", "row", "actual", "without_buildout", "without_buildout_or_stock_gain",
                              "effect_buildout", "effect_buildout_and_stock_gain"])
    return T


def fmt(v, d):
    if abs(v) < 0.5 * 10 ** (-d):
        v = 0.0
    return f"{v:.{d}f}".replace("-", "−")


def draw(T, out):
    plt = C.plt_setup()
    K = C.COLORS
    fig = plt.figure(figsize=(7.6, 7.2), dpi=200)
    fig.patch.set_facecolor(K["background"])
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    X = [0.2, 0.425, 0.55, 0.672, 0.792, 0.912]
    HDR = ["", "Actual", "Without the\nbuildout", "Without the\nbuildout or the\nstock gain", "Effect of the\nbuildout",
           "Effect of the\nbuildout and the\nstock gain"]
    y = 0.94
    ax.text(0.5, y, "The Economy With and Without the AI Boom", ha="center", va="top", fontsize=13, fontweight="bold")
    y -= 0.06
    ax.plot([0.03, 0.97], [y, y], color=K["ink"], lw=1.2)
    for x, h in zip(X, HDR):
        ax.text(x, y - 0.012, h, ha="center", va="top", fontsize=7.4, fontweight="bold", linespacing=1.15)
    y -= 0.085
    ax.plot([0.03, 0.97], [y, y], color=K["ink"], lw=0.6)
    step = 0.034

    def section(title, y):
        ax.add_patch(plt.Rectangle((0.03, y - step + 0.004), 0.94, step - 0.004, color=K["panel"], lw=0, zorder=0))
        ax.text(0.5, y - step / 2 + 0.002, title, ha="center", va="center", fontsize=8.3, fontweight="bold", style="italic")
        return y - step
    y = section("Growth, annualized, 2024Q3 to 2026Q3 (percent)", y)
    for r in T.itertuples(index=False):
        if r.row == "Unemployment rate":
            y = section("Third quarter of 2026", y)
        lab = {"excluding data centers": "   excluding data centers",
               "Data center investment above trend (percent of GDP)": "Data center investment above\ntrend (percent of GDP)"}.get(r.row, r.row)
        vals = [fmt(r.actual, 1), fmt(r.without_buildout, 1), fmt(r.without_buildout_or_stock_gain, 1),
                fmt(r.effect_buildout, 2), fmt(r.effect_buildout_and_stock_gain, 2)]
        h = step * (1.7 if "\n" in lab else 1.0)
        ax.text(X[0], y - h / 2, lab, ha="center", va="center", fontsize=8.3, linespacing=1.1)
        for x, v in zip(X[1:], vals):
            ax.text(x, y - h / 2, v, ha="center", va="center", fontsize=8.3)
        y -= h
    ax.plot([0.03, 0.97], [y, y], color=K["ink"], lw=1.2)
    note = ("Note: Growth rates and core PCE inflation are annualized over the eight quarters from 2024Q3 to 2026Q3, roughly the period\n"
            "of the boom; other rows are 2026Q3 values, in percent unless noted. The “without” columns take out the data center buildout\n"
            "and then also the AI stock gain; effects are actual minus each. Backward-looking expectations; the Fed follows its inertial\n"
            "policy rule. Source: FRB/US simulations; BEA; BLS; Census; Federal Reserve; author’s calculations.")
    ax.text(0.03, y - 0.015, note, ha="left", va="top", fontsize=6.3, style="italic", color=K["muted"], linespacing=1.3)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.savefig(out, dpi=200, facecolor=K["background"])
    plt.close(fig)


def main():
    paths.ensure()
    T = build()
    T.to_csv(paths.OUT_RESULTS / "table_1_summary.csv", index=False)
    draw(T, paths.OUT_FIGS / "table 1 summary.png")
    print("table: wrote output/results/table_1_summary.csv and output/figures/table 1 summary.png")


if __name__ == "__main__":
    main()
