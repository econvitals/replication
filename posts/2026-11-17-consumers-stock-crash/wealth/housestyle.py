"""A plain stand-in for the post's chart helper (blogwright's blogcharts.py), so the figures draw with matplotlib
alone. Same layout calls (new_fig, furnish, save) and colors; not the exact house look."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

C = dict(primary="#4472C4", secondary="#ED7D31", highlight="#C00000", gray="#8C8C8C", gold="#C99700",
         teal="#2C8C99", burgundy="#8E3B5E", ink="#262626", muted="#808080", gridline="#D9D9D9")
BRAND = "econvitals.org"


def check_stamp(mark=None):
    return mark or BRAND


def new_fig():
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    fig.subplots_adjust(left=0.085, right=0.965, top=0.78, bottom=0.155)
    ax.grid(axis="y", color=C["gridline"], linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    return fig, ax


def furnish(fig, ax, title, units, source, datestamp=None, brand=True):
    import textwrap
    t = "\n".join(textwrap.wrap(title, 52))
    two = "\n" in t
    fig.subplots_adjust(top=0.74 if two else 0.78)
    band = 0.785 if two else 0.83
    fig.text(0.5, 0.975, t, ha="center", va="top", fontsize=13.5 if two else 15, fontweight="bold", color=C["ink"])
    if units:
        fig.text(0.085, band, units, ha="left", va="bottom", fontsize=10.5, color=C["ink"])
    src = "\n".join(textwrap.wrap(source, 105))
    fig.text(0.085, 0.018, src, ha="left", va="bottom", fontsize=7.5, style="italic", color=C["muted"])
    fig.subplots_adjust(bottom=max(fig.subplotpars.bottom, 0.12 + 0.03 * src.count("\n")))
    if brand:
        fig.text(0.965, 0.97, BRAND, ha="right", va="top", fontsize=7.5, color=C["muted"])


def save(fig, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    return path
