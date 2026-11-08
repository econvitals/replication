"""Inequality Explorer — rebuilds the numbers behind econvitals.org/tools/inequality-explorer/
from the Congressional Budget Office’s own files.

    python replicate.py        # no keys; reads the two CBO files in inputs/, writes output/*.csv

Every number on the page starts from CBO’s The Distribution of Household Income, 2023 (September
2026). Most are CBO’s, shown as printed, and this script simply reads them. A few are Econvitals’
arithmetic on CBO’s figures, and each is computed here in the open:

  1. growth in average income by group (an index, and the percent change between two years);
  2. income shares and the Gini under a definition CBO does not publish: Medicare and Medicaid
     and CHIP counted at 40 cents per dollar of government spending, or left out;
  3. the “all nonelderly” household type, which combines two of CBO’s types.

At the end it compares what it read and built with the page’s own data files, when econvitals.org
can be reached.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import get, save  # noqa: E402

ZIP = HERE / "inputs" / "62761-additional-data-for-researchers.zip"   # CBO, unchanged
GINI_CSV = HERE / "inputs" / "62761-figure-18-gini.csv"               # CBO Figure 18, as printed
PUB, YEAR = 62761, 2023
LIVE = "https://econvitals.org/tools/inequality-explorer/"

# CBO’s spellings, and the short names used below.
GROUPS = {"all_quintiles": "all", "lowest_quintile": "q1", "second_quintile": "q2",
          "middle_quintile": "q3", "fourth_quintile": "q4", "highest_quintile": "q5",
          "percentiles_81_90": "p81_90", "percentiles_91_95": "p91_95",
          "percentiles_96_99": "p96_99", "top_1_percent": "top1"}
TYPES = {"all_households": "all", "hh_with_children": "children",
         "elderly_headed_hh": "elderly", "nonelderly_childless_hh": "nonelderly"}
RANKINGS = {"before": "inc_before_trans_tax",     # CBO’s headline: ranked by income before
            "market": "market_inc",               # transfers and taxes
            "after": "inc_after_trans_tax"}
# The eight groups that do not overlap (the four upper groups split the highest fifth).
DISJOINT = ["q1", "q2", "q3", "q4", "p81_90", "p91_95", "p96_99", "top1"]
SPLIT = DISJOINT + ["q5"]

# The tables used, and what their numbers are. THE SAME COLUMN NAME is dollars in one table, a
# rate in another and a share in a third (federal_taxes is $30,000, 20.4 and 100 for all
# households in 2023), so a rate or a share gets a suffix. Rates are percent of income BEFORE
# transfers and taxes, CBO’s base under every ranking. Counts are millions.
TABLES = {"01": "count", "03": "dollars", "05": "dollars", "06": "dollars", "07": "dollars",
          "08": "rate", "09": "rate", "10": "share", "11": "share", "12": "share"}
SUFFIX = {"count": "", "dollars": "", "rate": "_rate", "share": "_share"}


# ------------------------------------------------------------------------------ CBO’s tables
def member(z, ranking, number):
    want = f"households_ranked_by_{RANKINGS[ranking]}_table_{number}_"
    (name,) = [n for n in z.namelist() if want in n and n.endswith(f"_1979_{YEAR}.csv")]
    return pd.read_csv(io.BytesIO(z.read(name)), encoding="utf-8-sig")


def read_tables():
    """Tables 1 and 3–12 for all three rankings, long: ranking, type, group, year, variable, value."""
    parts = []
    with zipfile.ZipFile(ZIP) as z:
        for ranking in RANKINGS:
            for number, kind in TABLES.items():
                t = member(z, ranking, number).melt(["household_type", "income_group", "year"],
                                                    var_name="variable")
                t["variable"] += SUFFIX[kind]
                t["ranking"] = ranking
                parts.append(t)
    long = pd.concat(parts).dropna(subset=["value"])
    long["type"] = long.pop("household_type").map(TYPES)
    long["group"] = long.pop("income_group").map(GROUPS)
    key = ["ranking", "type", "group", "year", "variable"]
    # Tables 5–7 repeat totals first printed in Table 3; they must agree.
    assert long.groupby(key)["value"].nunique().max() == 1, "two CBO tables disagree"
    return long.drop_duplicates(key)


def panel(long, ranking="before", htype="all"):
    """{variable: DataFrame of years × groups} for one ranking and household type."""
    sub = long[(long.ranking == ranking) & (long.type == htype)]
    return {v: g.pivot(index="year", columns="group", values="value")
            for v, g in sub.groupby("variable")}


def read_extras():
    """Medians (Table 4, all households, the same in every ranking file) and the income needed
    to enter each group (Table 2, by household size, one per ranking)."""
    with zipfile.ZipFile(ZIP) as z:
        med = member(z, "before", "04").set_index("year")
        mins = {r: member(z, r, "02").rename(columns=GROUPS) for r in RANKINGS}
    return med, mins


# ------------------------------------------------------------------------------ Econvitals’ arithmetic
def implied_households(P):
    """Households in each group as CBO’s own printed shares imply them. A share is the group’s
    average income × its households ÷ the aggregate, so households = share × aggregate ÷ (100 ×
    average). CBO prints the counts themselves only to 0.1 million (±4 percent for the top 1
    percent), so this is the better weight. The middle of the three estimates (market income,
    income before and after transfers and taxes); with two, the larger; with none, CBO’s count."""
    n_all = P["num_households"]["all"]
    est = []
    for inc in ("market_inc", "inc_before_transfers_taxes", "inc_after_transfers_taxes"):
        avg, share, tot = P[inc], P[inc + "_share"], P[inc]["all"]
        e = share.mul(tot * n_all, axis=0) / (100 * avg)
        est.append(e.where((avg > 0) & (share > 0) & (tot > 0).to_numpy()[:, None]))
    stack = np.sort(np.stack([e.to_numpy() for e in est]), axis=0)        # NaNs sort last
    count = (~np.isnan(stack)).sum(axis=0)
    pick = np.take_along_axis(stack, (count // 2)[None], axis=0)[0]
    W = pd.DataFrame(pick, index=est[0].index, columns=est[0].columns)
    W = W.where(count > 0, P["num_households"])
    W["all"] = n_all
    return W


def share_from(inc, W):
    """Each group’s share of the total under an income definition, groups weighted by W."""
    return 100 * inc * W / (inc["all"] * W["all"]).to_numpy()[:, None]


def grouped_gini(inc, W):
    """The Gini the eight non-overlapping groups show: a Lorenz curve drawn straight between the
    groups, households weighted by W. It cannot see inequality inside a group, so it is lower
    than CBO’s own Gini; it is used only for the DIFFERENCE between two definitions."""
    out = {}
    for year in inc.index:
        p, y = W.loc[year, DISJOINT], inc.loc[year, DISJOINT] * W.loc[year, DISJOINT]
        order = np.argsort((y / p).to_numpy(), kind="stable")
        p, y = p.to_numpy()[order] / p.sum(), y.to_numpy()[order] / y.sum()
        cum = np.concatenate([[0], np.cumsum(y)[:-1]])
        out[year] = 1 - float((p * (2 * cum + y)).sum())
    return pd.Series(out)


def combine(A, B, kinds):
    """CBO’s households with children + its nonelderly childless households = “all nonelderly”.
    Counts are added; dollar averages are weighted by the households each type’s printed shares
    imply and rounded to $100 as CBO prints them; a rate is the two printed rates weighted by
    each part’s income before transfers and taxes (the rate’s base); a share is the two printed
    shares weighted by each type’s total of that income."""
    nA, nB = implied_households(A), implied_households(B)
    out = {}
    for var, kind in kinds.items():
        a, b = A[var], B[var]
        if kind == "count":
            out[var] = (a + b).apply(lambda col: col.map(lambda v: round(v, 1)))
        elif kind == "dollars":
            v = (a * nA + b * nB) / (nA + nB)
            out[var] = v.apply(lambda col: col.map(lambda x: x if np.isnan(x) else int(round(x, -2))))
        elif kind == "rate":
            wa = A["inc_before_transfers_taxes"] * nA
            wb = B["inc_before_transfers_taxes"] * nB
            out[var] = ((a * wa + b * wb) / (wa + wb)).apply(lambda col: col.map(lambda x: round(x, 1)))
        else:                                                              # a share
            base = var[: -len("_share")]
            ta = (A[base]["all"] * nA["all"]).to_numpy()[:, None]
            tb = (B[base]["all"] * nB["all"]).to_numpy()[:, None]
            out[var] = ((a * ta + b * tb) / (ta + tb)).apply(lambda col: col.map(lambda x: round(x, 1)))
    return out


# ------------------------------------------------------------------------------ build
long = read_tables()
P = panel(long)                       # CBO’s headline panel: ranked by income before transfers
W = implied_households(P)             # and taxes, all households
gini = pd.read_csv(GINI_CSV, index_col="year")
gini.columns = ["market", "before", "after_transfers", "after"]
med, mins = read_extras()
AFTER, BEFORE, MARKET = "inc_after_transfers_taxes", "inc_before_transfers_taxes", "market_inc"

# 1. Headline inequality measures, CBO’s as printed (plus two sums and a ratio of CBO’s figures).
headline = pd.DataFrame({
    "top1_share_market": P["market_inc_share"]["top1"],
    "top1_share_before": P["inc_before_transfers_taxes_share"]["top1"],
    "top1_share_after": P["inc_after_transfers_taxes_share"]["top1"],
    "top10_share_after": P["inc_after_transfers_taxes_share"][["p91_95", "p96_99", "top1"]].sum(axis=1),
    "top20_share_after": P["inc_after_transfers_taxes_share"]["q5"],
    "bottom20_share_after": P["inc_after_transfers_taxes_share"]["q1"],
    "gini_market": gini["market"], "gini_before": gini["before"],
    "gini_after_transfers": gini["after_transfers"], "gini_after": gini["after"],
    "mean_over_median_after": P[AFTER]["all"] / med["inc_after_transfers_taxes"],
})
save(headline.round(4), HERE, "headline")

# 2. Growth: average income after transfers and taxes (CBO’s, 2023 dollars) indexed to 1979 = 100,
#    and the percent change 1979–2023 under each of CBO’s three income measures.
groups = ["q1", "q2", "q3", "q4", "q5", "top1", "all"]
save((100 * P[AFTER][groups] / P[AFTER][groups].loc[1979]).round(2), HERE, "growth_index_after")
change = pd.DataFrame({name: 100 * (P[col].loc[YEAR] / P[col].loc[1979] - 1)
                       for name, col in (("market", MARKET), ("before", BEFORE), ("after", AFTER))})
change.index.name = "group"
save(change.loc[SPLIT + ["all"]].round(2), HERE, f"growth_1979_{YEAR}")

# 3. Who pays and who receives, latest year: CBO’s rates and shares, plus social insurance as a
#    percent of income before transfers and taxes (CBO prints no rate for it).
i = YEAR
rates = pd.DataFrame({
    "federal_tax_rate": P["federal_taxes_rate"].loc[i],
    "means_tested_transfer_rate": P["means_tested_transfers_rate"].loc[i],
    "social_insurance_rate": 100 * P["social_insurance_benefits"].loc[i] / P[BEFORE].loc[i],
    "share_of_income_before": P["inc_before_transfers_taxes_share"].loc[i],
    "share_of_federal_taxes": P["federal_taxes_share"].loc[i],
    "share_of_means_tested_transfers": P["means_tested_transfers_share"].loc[i],
})
rates["benefits_minus_taxes"] = (rates.social_insurance_rate + rates.means_tested_transfer_rate
                                 - rates.federal_tax_rate)
rates.index.name = "group"
save(rates.loc[SPLIT + ["all"]].round(2), HERE, f"rates_{YEAR}")

# 4. Two definitions CBO does not publish, each built from CBO’s nearest published total (income
#    after transfers and taxes) adjusted only by the pieces that differ. CBO counts Medicare and
#    Medicaid and CHIP at what the government spends; at 40 cents each dollar counts 0.4.
health = P["medicare"] + P["medicaid_and_chip"]
defs = {"after": P[AFTER], "health40": P[AFTER] - 0.6 * health, "exhealth": P[AFTER] - health}
alt = pd.DataFrame({"top1_share_after_printed": P["inc_after_transfers_taxes_share"]["top1"]})
for name, inc in defs.items():
    alt[f"top1_share_{name}"] = share_from(inc, W)["top1"]       # rebuilt with implied households
# A Gini for an unpublished definition: CBO’s Gini for income after transfers and taxes, moved
# by the difference the eight groups show between the two definitions.
g_after = grouped_gini(defs["after"], W)
alt["gini_after"] = gini["after"]
for name in ("health40", "exhealth"):
    alt[f"gini_{name}"] = gini["after"] + grouped_gini(defs[name], W) - g_after
save(alt.round(4), HERE, "health_alternatives")
avg = pd.DataFrame({name: inc.loc[YEAR] for name, inc in defs.items()})
avg.index.name = "group"
save(avg.loc[SPLIT + ["all"]].round(0), HERE, f"average_income_{YEAR}_health_alternatives")

# How close the household-count weighting comes: CBO’s printed shares rebuilt from its averages
# for every group, year, ranking and household type.
gaps = []
for ranking in RANKINGS:
    for htype in TYPES.values():
        Q = panel(long, ranking, htype)
        WQ = implied_households(Q)
        for col in (MARKET, BEFORE, AFTER):
            d = (share_from(Q[col], WQ) - Q[col + "_share"]).abs()[DISJOINT + ["q5"]]
            gaps.append({"ranking": ranking, "household_type": htype, "income": col,
                         "worst_gap": d.max().max(), "worst_gap_top1": d["top1"].max()})
gaps = pd.DataFrame(gaps)
save(gaps.set_index("ranking").round(3), HERE, "rebuilt_share_gaps")

# 5. “All nonelderly” households (an Econvitals combination), headline ranking, latest year.
kind_of = {v: ("count" if v.startswith("num_") else "rate" if v.endswith("_rate")
               else "share" if v.endswith("_share") else "dollars") for v in P}
blends = {r: combine(panel(long, r, "children"), panel(long, r, "nonelderly"), kind_of)
          for r in RANKINGS}
B = blends["before"]
nonelderly = pd.DataFrame({"households_millions": B["num_households"].loc[YEAR],
                           "average_income_after": B[AFTER].loc[YEAR],
                           "share_of_income_after": B["inc_after_transfers_taxes_share"].loc[YEAR],
                           "federal_tax_rate": B["federal_taxes_rate"].loc[YEAR]})
nonelderly.index.name = "group"
save(nonelderly.loc[SPLIT + ["all"]], HERE, f"nonelderly_{YEAR}")


# ------------------------------------------------------------------------------ self-check
def compare_with_live():
    """Compare with the page’s own data files. Never fails the run if the site is unreachable."""
    try:
        live = json.loads(get(LIVE + "data.json"))
        full = json.loads(get(LIVE + "data-full.json", timeout=120))
    except Exception as exc:                                # noqa: BLE001
        print(f"\nSelf-check skipped: could not read {LIVE}data.json ({exc}).")
        return True
    if live["meta"].get("pub") != PUB:
        print(f"\nSelf-check skipped: the page now shows CBO publication {live['meta'].get('pub')}, "
              f"these inputs are {PUB}.")
        return True
    years = live["years"]
    worst, n = 0.0, 0

    def against(arrays, frames):
        nonlocal worst, n
        for var, by_group in arrays.items():
            for g, vals in by_group.items():
                mine = frames[var][g].reindex(years).to_numpy(dtype=float)
                theirs = np.array([np.nan if v is None else v for v in vals], dtype=float)
                both = ~np.isnan(mine) & ~np.isnan(theirs)
                if (np.isnan(mine) != np.isnan(theirs)).any():     # a number one side lacks
                    print(f"  {var}/{g}: blank on one side only")
                    worst = float("inf")
                if both.any():
                    worst = max(worst, float(np.abs(mine[both] - theirs[both]).max()))
                    n += int(both.sum())
    against(live["core"], P)
    for key, arrays in full["panels"].items():
        ranking, htype = key.split("|")
        against(arrays, blends[ranking] if htype == "nonelderly_all" else panel(long, ranking, htype))
    against({"gini": {c: live["gini"][c] for c in gini.columns}}, {"gini": gini})
    m = {c: med[col] for c, col in (("market", "market_inc"), ("before", "inc_before_transfers_taxes"),
                                    ("after", "inc_after_transfers_taxes"))}
    m.update({c + "_adj": med["adj_" + m[c].name] for c in ("market", "before", "after")})
    against({"medians": live["medians"]}, {"medians": pd.DataFrame(m)})
    for ranking, sizes in live["minimums"].items():
        t = mins[ranking]
        for size, by_group in sizes.items():
            frame = t[t.household_size == int(size[4:])].set_index("year")
            against({"min": by_group}, {"min": frame})
    ok = worst < 1e-6
    print(f"\nSelf-check against {LIVE}data.json and data-full.json: {n:,} numbers compared, "
          f"largest difference {worst:.2g} — {'MATCHES' if ok else 'DOES NOT MATCH'}.")
    return ok


print(f"CBO, The Distribution of Household Income, {YEAR}: top 1 percent’s share and the Gini")
print(headline[["top1_share_market", "top1_share_after", "gini_market", "gini_after"]].tail(3).to_string())
print(f"\nPercent change in average income, 1979–{YEAR}:")
print(change.loc[["q1", "q3", "q5", "top1"]].round(1).to_string())
print(f"\nMedicare and Medicaid and CHIP at 40 cents, or left out ({YEAR}):")
print(alt.loc[[YEAR]].T.round(3).to_string(header=False))
headline_top1 = gaps[(gaps.ranking == "before") & (gaps.household_type == "all")].worst_gap_top1.max()
print(f"\nRebuilt shares vs CBO’s printed shares, worst gap: {gaps.worst_gap.max():.3f} point; "
      f"top 1 percent, headline ranking, all households: {headline_top1:.3f}")
if not compare_with_live():
    sys.exit(1)
