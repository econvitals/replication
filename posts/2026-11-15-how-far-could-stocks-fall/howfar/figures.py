"""Draw the post's four figures from the same data (plain matplotlib, not the post's house style).

Figures 2, 3 and 4 use public data. Figure 1 needs licensed/forward_pe_monthly.csv and is skipped without it;
the dotted "how often it happened" line in Figure 4 needs licensed/sp500_daily.csv and is left off without it.
Writes output/figures/figure_<n>.png.

    python -m howfar.figures
"""
import datetime as dt
import json
import statistics as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .common import CAPE_NOW, LICENSED, NOW, OUT, fred, have, month_key, rows  # noqa: E402
from .numbers import mpd, shiller  # noqa: E402

FIG = OUT / "figures"
BLUE, GREY, ORANGE = "#3b6fc4", "#777777", "#ee7d2b"


def mid(y, m):
    return dt.date(y, m, 15)


def finish(fig, ax, title, units, source, path):
    ax.set_title(title, fontsize=13, fontweight="bold", loc="center", pad=26)
    ax.text(0, 1.02, units, transform=ax.transAxes, fontsize=9.5)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd", lw=0.6)
    fig.text(0.01, 0.01, source, fontsize=8, style="italic", color=GREY)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("wrote", path.relative_to(OUT.parent))


def figure1():
    if not have("forward_pe_monthly.csv"):
        print("figure 1 skipped: needs licensed/forward_pe_monthly.csv")
        return
    f = sorted((month_key(r["month"]), float(r["fpe"])) for r in rows(LICENSED / "forward_pe_monthly.csv"))
    x = [mid(*k) for k, _ in f]
    x[-1] = NOW
    y = [v for _, v in f]
    avg = st.mean(v for k, v in f if (1979, 1) <= k <= (2026, 10))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, y, color=BLUE, lw=1.6)
    ax.axhline(avg, color=GREY, ls="--", lw=1)
    ax.text(x[0], avg + 0.5, f"Average since 1979: {avg:.1f}", color=GREY, fontsize=9)
    pk = max((v, d) for d, v in zip(x, y) if d.year <= 2000)
    ax.annotate(f"1999: {pk[0]:.1f}", (pk[1], pk[0]), xytext=(8, 4), textcoords="offset points", fontsize=9)
    ax.annotate(f"Now: {y[-1]:.1f}", (x[-1], y[-1]), xytext=(-60, -16), textcoords="offset points", fontsize=9)
    ax.set_ylim(0, 28)
    finish(fig, ax, "Figure 1. Stock Prices Relative to Expected Earnings",
           "S&P 500 price over expected earnings for the next 12 months, monthly",
           "Federal Reserve Board (I/B/E/S) from 1988; Yardeni Research, 1979–87; FactSet since May 2026",
           FIG / "figure_1.png")


def figure2():
    c = sorted((k, v["cape"]) for k, v in shiller().items() if v["cape"] is not None)
    x = [mid(*k) for k, _ in c] + [NOW]
    y = [v for _, v in c] + [CAPE_NOW]
    avg = st.mean(v for k, v in c if (1979, 1) <= k <= (2026, 10))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, y, color=BLUE, lw=1.1)
    ax.plot([dt.date(1979, 1, 1), NOW], [avg, avg], color=GREY, ls="--", lw=1)
    ax.text(0.99, 0.03, f"Dashed line: average since 1979, {avg:.1f}", transform=ax.transAxes, ha="right", color=GREY, fontsize=9)
    for lab, a, b in (("1929", 1929, 1929), ("1999", 1999, 2000)):
        v, d = max((v, d) for d, v in zip(x, y) if a <= d.year <= b)
        ax.annotate(f"{lab}: {v:.1f}", (d, v), xytext=(-70, 6), textcoords="offset points", fontsize=9)
    ax.annotate(f"Now: {CAPE_NOW:.1f}", (NOW, CAPE_NOW), xytext=(-70, 10), textcoords="offset points", fontsize=9)
    ax.set_ylim(0, 50)
    finish(fig, ax, "Figure 2. Stock Prices Relative to Ten Years of Earnings",
           "S&P 500 price over the average of ten years of real earnings, monthly",
           "Robert Shiller; multpl.com (the November 13, 2026 reading)", FIG / "figure_2.png")


def figure3():
    p, g = fred("CPATAX"), fred("GDP")
    s = sorted((d, p[d] / g[d] * 100) for d in p if d in g)
    x = [d + dt.timedelta(days=45) for d, _ in s]
    y = [v for _, v in s]
    avg = st.mean(v for d, v in s if d.year <= 2019)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, y, color=BLUE, lw=1.5)
    ax.plot([x[0], dt.date(2019, 12, 31)], [avg, avg], color=GREY, ls="--", lw=1)
    ax.text(0.99, 0.03, f"Dashed line: average, 1947–2019, {avg:.1f}", transform=ax.transAxes, ha="right", color=GREY, fontsize=9)
    v97, d97 = max((v, d) for d, v in zip(x, y) if d.year == 1997)
    ax.annotate(f"1997: {v97:.1f}", (d97, v97), xytext=(-60, 6), textcoords="offset points", fontsize=9)
    d19 = max(d for d in x if d <= dt.date(2019, 12, 31))
    ax.annotate(f"2019: {y[x.index(d19)]:.1f}", (d19, y[x.index(d19)]), xytext=(4, -22), textcoords="offset points", fontsize=9)
    ax.annotate(f"Now: {y[-1]:.1f}", (x[-1], y[-1]), xytext=(-60, 8), textcoords="offset points", fontsize=9)
    ax.set_ylim(0, 14)
    finish(fig, ax, "Figure 3. Corporate Profits as a Share of GDP", "After-tax corporate profits, percent of GDP, quarterly",
           "Bureau of Economic Analysis (profits with inventory valuation and capital consumption adjustments)",
           FIG / "figure_3.png")


def figure4():
    v = mpd()
    x, y = [d for d, _ in v], [p for _, p in v]
    avg = st.mean(y)
    fig, ax = plt.subplots(figsize=(8, 5))
    for a, b in (("2007-10-09", "2009-03-09"), ("2011-04-29", "2011-10-03"), ("2018-09-20", "2018-12-24"),
                 ("2020-02-19", "2020-03-23"), ("2022-01-03", "2022-10-12"), ("2025-02-19", "2025-04-08")):
        ax.axvspan(dt.date.fromisoformat(a), dt.date.fromisoformat(b), color="#9aa0a6", alpha=0.18, lw=0)
    ax.plot(x, y, color=BLUE, lw=1.1)
    ax.axhline(avg, color=GREY, ls="--", lw=1)
    lines = [f"Dashed line: average since 2007, {avg:.0f} percent"]
    nums = json.loads((OUT / "numbers.json").read_text()) if (OUT / "numbers.json").exists() else {}
    if "mpd_realized" in nums:
        ax.axhline(nums["mpd_realized"], color=ORANGE, ls=":", lw=1.2)
        lines.append(f"Dotted line: how often it happened, {nums['mpd_realized']:.0f} percent")
    lines.append("Shaded: declines of about 20 percent or more")
    ax.text(0.99, 0.97, "\n".join(lines), transform=ax.transAxes, ha="right", va="top", color=GREY, fontsize=9)
    ax.annotate(f"Latest: {y[-1]:.1f}", (x[-1], y[-1]), xytext=(-40, -24), textcoords="offset points", fontsize=9)
    ax.set_ylim(0, 40)
    finish(fig, ax, "Figure 4. The Price of Insurance Against a Stock Market Fall",
           "Implied chance the S&P 500 is 20 percent lower a year later, percent",
           "Federal Reserve Bank of Minneapolis; S&P Dow Jones Indices; author’s calculations", FIG / "figure_4.png")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (figure1, figure2, figure3, figure4):
        f()


if __name__ == "__main__":
    main()
