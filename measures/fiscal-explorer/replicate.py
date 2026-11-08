"""Fiscal Explorer — rebuilds the baseline budget the Explorer starts from
(econvitals.org/tools/fiscal-explorer/), plus two worked examples of the arithmetic on top.

    python replicate.py      # needs FRED_API_KEY; writes output/baseline.csv,
                             # output/rate_scenario.csv and output/fiscal_gap.csv

The baseline is federal revenues, outlays, net interest, the deficit and debt held by the public,
fiscal years 1901-2056, in billions of dollars and as a percent of GDP:

    1901-1961   OMB Historical Tables
    1962-2024   CBO's historical budget data
    2025-2036   CBO's February 2026 ten-year baseline, with fiscal 2026 (a year Treasury has
                now closed) replaced by Treasury's final Monthly Treasury Statement
    2037-2056   CBO's February 2026 extended baseline (the Long-Term Budget Outlook)

    GDP         BEA for completed fiscal years from 1991, OMB for 1930-1990, CBO for projected
                years, and before 1930 a reconstruction from Census's historical GNP series.

The CBO, OMB and Census numbers are in inputs/ (CBO's website refuses scripted downloads);
GDP comes from FRED and the 2026 actuals from Treasury's Fiscal Data API, which needs no key.
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.cbo import fiscal_year_gdp, fred_as_of, read_input, treasury_year_end  # noqa: E402
from common.econdata import get, save  # noqa: E402

# The day the Explorer's data were built. BEA revises GDP, so the GDP denominators are taken as
# FRED published them that day; move this date when the Explorer is rebuilt.
VINTAGE = "2026-11-01"
YEARS = range(1901, 2057)

omb = read_input(HERE, "omb_historical_tables_fy2027.csv")          # $ millions; GDP $ billions
hist = read_input(HERE, "cbo_historical_budget_data_2026-02.csv")   # $ billions, 1962-2024
cbo10 = read_input(HERE, "cbo_budget_projections_2026-02.csv")      # $ billions, 2025-2036
ltbo = read_input(HERE, "cbo_ltbo_extended_baseline_2026-02.csv")   # percent of GDP, 2026-2056
rates = read_input(HERE, "cbo_ltbo_interest_and_growth_2026-02.csv") / 100
f1 = read_input(HERE, "census_hsus_series_f1_gnp.csv")["gnp_billions"]

# ---------------------------------------------------------------- 1. fiscal-year GDP, $ billions
gdp = pd.Series(index=pd.Index(YEARS), dtype=float)
# Before 1930 nobody published a fiscal-year GDP. Census's GNP (Historical Statistics, Series F 1)
# is scaled to BEA's GDP at 1929 and put on the July-June fiscal year then in force.
bea_1929 = fred_as_of("GDPA", VINTAGE)[pd.Timestamp("1929-01-01")]
for y in range(1901, 1930):
    gdp.loc[y] = 0.5 * (f1.loc[y - 1] + f1.loc[y]) * bea_1929 / f1.loc[1929]
gdp.loc[1930:1990] = omb.loc[1930:1990, "gdp"]                          # OMB Table 1.2
bea = fiscal_year_gdp(VINTAGE)                                        # Oct-Sep, FY1991 on
gdp.loc[bea.index] = bea
for y in range(2025, 2037):                                           # CBO where BEA has no year yet
    if y not in bea.index:
        gdp.loc[y] = cbo10.loc[y, "gdp"]
gdp.loc[2037:2056] = ltbo.loc[2037:2056, "gdp_trillions"] * 1000

# ---------------------------------------------------------------- 2. the budget, $ billions
b = pd.DataFrame(index=pd.Index(YEARS, name="fiscal_year"),
                 columns=["revenues", "outlays", "net_interest", "deficit", "debt"], dtype=float)
b["source"] = ""
# OMB, 1901-1961 (millions -> billions). OMB prints FY1913 and FY1914 balances as "less than
# half a million dollars"; for those two the deficit is outlays minus receipts.
early = omb.loc[1901:1961]
b.loc[1901:1961, "revenues"] = early["receipts"] / 1000
b.loc[1901:1961, "outlays"] = early["outlays"] / 1000
b.loc[1901:1961, "net_interest"] = early["net_interest"] / 1000      # OMB starts it in 1940
b.loc[1901:1961, "deficit"] = (-early["surplus"]).fillna(early["outlays"] - early["receipts"]) / 1000
# Debt held by the public: OMB publishes it as a percent of GDP (Table 7.1, from 1940).
b.loc[1940:1961, "debt"] = early.loc[1940:1961, "debt_pct_gdp"] / 100 * gdp.loc[1940:1961]
b.loc[1901:1961, "source"] = "OMB"
# CBO's historical budget data, 1962-2024.
b.loc[1962:2024, ["revenues", "outlays", "net_interest", "debt"]] = \
    hist.loc[1962:2024, ["revenues", "outlays", "net_interest", "debt_held_public"]].values
b.loc[1962:2024, "deficit"] = -hist.loc[1962:2024, "surplus"]
b.loc[1962:2024, "source"] = "CBO history"
# CBO's ten-year baseline, 2025-2036 (CBO prints deficits as negatives).
b.loc[2025:2036, ["revenues", "outlays", "net_interest", "debt"]] = \
    cbo10.loc[2025:2036, ["revenues", "outlays", "net_interest", "debt_held_public"]].values
b.loc[2025:2036, "deficit"] = -cbo10.loc[2025:2036, "deficit_neg"]
b.loc[2025:2036, "source"] = "CBO baseline"
# Fiscal years Treasury has closed that CBO still projects: Treasury's final figures.
for y in range(2026, 2037):
    actual = treasury_year_end(y, as_of=VINTAGE)
    if actual is None:
        break
    b.loc[y, ["revenues", "outlays", "deficit", "net_interest", "debt"]] = [
        actual["revenues"], actual["outlays"], actual["deficit"], actual["net_interest"],
        actual["debt_held_public"]]
    b.loc[y, "source"] = "Treasury"
# CBO's extended baseline, 2037-2056: its percent-of-GDP figures times its GDP.
lt = ltbo.loc[2037:2056]
for col, pct in [("revenues", lt["revenues_pct"]), ("outlays", lt["outlays_pct"]),
                 ("net_interest", lt["net_interest_pct"]), ("deficit", -lt["deficit_neg_pct"]),
                 ("debt", lt["debt_pct"])]:
    b.loc[2037:2056, col] = pct / 100 * gdp.loc[2037:2056]
b.loc[2037:2056, "source"] = "CBO long term"

b["primary_deficit"] = b["deficit"] - b["net_interest"]
b["gdp"] = gdp
for col in ["revenues", "outlays", "net_interest", "primary_deficit", "deficit", "debt"]:
    b[col + "_pct"] = 100 * b[col] / b["gdp"]

out = b.copy()
out.index = pd.to_datetime([f"{y}-01-01" for y in out.index])
out.index.name = "date"
out.insert(0, "date_dec31", [f"{y}-12-31" for y in b.index])   # the debt chart's dating convention
save(out, HERE, "baseline")

# ---------------------------------------------------------------- 3. worked example: the fiscal gap
# The permanent cut in the primary deficit, starting in 2027, that leaves debt in 2056 at its
# 2025 share of GDP. With d the debt ratio, r CBO's average interest rate on the debt and g
# nominal GDP growth, debt dynamics give
#     gap = (d[2056] - d[2025]) / sum over t=2027..2056 of prod over s=t+1..2056 of (1+r_s)/(1+g_s)
d = b["debt_pct"]
annuity = sum(
    pd.Series([(1 + rates.loc[s, "interest_rate_pct"]) / (1 + rates.loc[s, "nominal_gdp_growth_pct"])
               for s in range(t + 1, 2057)], dtype=float).prod()
    for t in range(2027, 2057))
gap = (d.loc[2056] - d.loc[2025]) / annuity
save(pd.DataFrame({"value": [gap, d.loc[2025], d.loc[2056], annuity]},
                  index=pd.Index(["fiscal_gap_pct_gdp", "debt_2025_pct", "debt_2056_pct",
                                  "annuity_factor"], name="item")), HERE, "fiscal_gap")

# ---------------------------------------------------------------- 4. worked example: rates +1 point
# The Explorer's interest-rate dial: Treasury rates 100 basis points higher from 2027, the economy
# unchanged. Two stocks pay it differently. CBO's existing debt is termed out, so the average rate
# on it reprices as it rolls over: 1/6 of the gap closes each year (an average maturity of about
# six years). The extra debt the shock itself creates is new borrowing and pays the full higher
# rate at once, r + 1 point, where r is CBO's average rate on the debt.
SHOCK, FROM, MATURITY = 0.01, 2027, 6.0
extra_debt, repriced, rows = 0.0, 0.0, []
for y in range(2026, 2057):
    dr = SHOCK if y >= FROM else 0.0
    repriced = dr / MATURITY + (1 - 1 / MATURITY) * repriced
    extra_interest = repriced * b.loc[y - 1, "debt"] + (rates.loc[y, "interest_rate_pct"] + dr) * extra_debt
    extra_debt += extra_interest                  # no policy change, so the deficit rises by the interest
    rows.append({"date": pd.Timestamp(f"{y}-01-01"),
                 "debt_pct": d.loc[y],
                 "debt_pct_rates_plus_1pt": 100 * (b.loc[y, "debt"] + extra_debt) / gdp.loc[y],
                 "net_interest_pct": b.loc[y, "net_interest_pct"],
                 "net_interest_pct_rates_plus_1pt": 100 * (b.loc[y, "net_interest"] + extra_interest) / gdp.loc[y]})
scen = pd.DataFrame(rows).set_index("date")
save(scen, HERE, "rate_scenario")

show = b.loc[[1946, 2000, 2025, 2026, 2036, 2056],
             ["source", "revenues_pct", "outlays_pct", "deficit_pct", "debt_pct"]]
print(show.round(2).to_string())
print(f"\nFiscal gap, 2027-2056: {gap:.2f}% of GDP a year (debt held at {d.loc[2025]:.1f}% of GDP)")
print("Debt in 2056 with rates 1 point higher from 2027: "
      f"{scen['debt_pct_rates_plus_1pt'].iloc[-1]:.1f}% of GDP, against {d.loc[2056]:.1f}%")


# ---------------------------------------------------------------- 5. self-check against the live page
def check_live_page():
    """Compare every dollar figure with the copy built into the live Explorer page.

    The page carries its whole data set inline (const FISCAL_DATA = {...}). Unreachable, or built
    on a different day from VINTAGE: say so and carry on. Built the same day and different: fail.
    """
    try:
        html = get("https://econvitals.org/tools/fiscal-explorer/", timeout=60)
        at = re.search(r"const FISCAL_DATA\s*=\s*", html).end()
        page, _ = json.JSONDecoder().raw_decode(html[at:])
    except Exception as exc:  # noqa: BLE001 - the check is optional
        print(f"\nLive-page check skipped ({type(exc).__name__}).")
        return 0
    if page["meta"].get("built") != VINTAGE:
        print(f"\nLive-page check skipped: the page was built on {page['meta'].get('built')}, "
              f"this script reproduces the {VINTAGE} build. Update VINTAGE and the inputs.")
        return 0
    keys = {"revenues": "revenues_total", "outlays": "outlays_total", "net_interest": "net_interest",
            "deficit": "deficit", "debt": "debt_held_public", "gdp": None}
    worst, rows = 0.0, []
    for ours, theirs in keys.items():
        pub = page["gdp"] if theirs is None else page["series"][theirs]
        for y in YEARS:
            mine, there = b.loc[y, ours], pub.get(str(y))
            if pd.notna(mine) and there is not None:
                rows.append({"series": ours, "fiscal_year": y, "ours": mine, "page": there,
                             "diff": mine - there})
                worst = max(worst, abs(mine - there))
    cmp = pd.DataFrame(rows).set_index("series")
    save(cmp, HERE, "live_page_check")
    print(f"\nLive page ({len(cmp)} numbers in $ billions): largest difference {worst:.4f}")
    # The page rounds every dollar figure to $1 million; nine OMB-era deficits differ by one
    # rounding step because the page takes them from OMB's printed balance, not CBO's.
    return 1 if worst > 0.002 else 0


sys.exit(check_live_page())
