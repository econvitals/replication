"""Trade Balance Excluding Data-Center Goods — rebuilds the charts on
econvitals.org/other/tradedetail/ (both views of its Percent of GDP | Dollars switch).

    python replicate.py     # needs FRED_API_KEY and BEA_API_KEY; CENSUS_API_KEY for the gold bar
                            # writes output/ytd.csv, output/imports_index.csv, output/change_since_2024.csv

Data-center goods are four Census end-use categories: computers, computer accessories and parts,
semiconductors, and telecommunications equipment. Their exports and imports come from BEA's
quarterly international transactions (table 2.1, seasonally adjusted), each quarter split evenly
across its three months; months after BEA's latest quarter come from the current FT-900 release
(exhibits 7 and 8). "Everything else" is the total goods-and-services balance less their net
exports. Each year's bar sums the same months, January through the latest month published.
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from common.econdata import fred, get, key, save  # noqa: E402

# Chart label, BEA ITA indicator (after "ExpGds"/"ImpGds"), FT-900 exhibit 7/8 row label.
CATS = [("Computers", "Comp", "Computers"),
        ("Computer parts and accessories", "CompAccPeriAndParts", "Computer accessories"),
        ("Semiconductors", "Semiconductors", "Semiconductors"),
        ("Telecommunications equipment", "TelecomEquip", "Telecommunications equipment")]
FT900 = "https://www.census.gov/foreign-trade/Press-Release/current_press_release/{}.xlsx"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
BASE_YEAR, BASE_QUARTER = 2024, pd.Period("2024Q4")     # the year and quarter before the tariffs


def bea_ita(indicator: str) -> pd.Series:
    """One BEA international-transactions line, quarterly, seasonally adjusted, $ millions."""
    params = {"UserID": key("BEA_API_KEY"), "method": "GetData", "datasetname": "ITA",
              "Indicator": indicator, "AreaOrCountry": "AllCountries", "Frequency": "QSA",
              "Year": "ALL", "ResultFormat": "JSON"}
    res = json.loads(get("https://apps.bea.gov/api/data", params))["BEAAPI"].get("Results", {})
    if not res.get("Data"):
        raise RuntimeError(f"BEA ITA {indicator}: {res.get('Error', 'no data')}")
    s = {pd.Period(r["TimePeriod"], "Q"): float(r["DataValue"].replace(",", ""))
         for r in res["Data"] if r.get("DataValue") not in (None, "", "(D)")}
    return pd.Series(s).sort_index()


def ft900_exhibit(name: str) -> dict:
    """The current FT-900's exhibit 7 (exports) or 8 (imports), seasonally adjusted part:
    {'month': Period, 'rows': {label: (this month, last month, year to date)}}, $ millions."""
    ws = openpyxl.load_workbook(io.BytesIO(get(FT900.format(name), binary=True)),
                                read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    head = next(i for i, r in enumerate(rows) if r and str(r[0] or "").startswith("Item"))
    month = MONTHS.index(str(rows[head][1]).strip()) + 1
    year = int(str(rows[head + 1][1]).split()[0])
    out = {}
    for r in rows[head + 2:]:
        if r and isinstance(r[0], str) and isinstance(r[1], (int, float)):
            out.setdefault(r[0].strip(), (float(r[1]), float(r[2]), float(r[4])))  # Part A first
    return {"month": pd.Period(year=year, month=month, freq="M"), "rows": out}


def ft900_history() -> pd.DataFrame:
    """Census's FT-900 exhibit 1 history, monthly from 1992: balance, exports and imports, each
    total / goods / services, by position (checked against the header row)."""
    url = "https://www.census.gov/foreign-trade/statistics/historical/exhibit_history.xlsx"
    wb = openpyxl.load_workbook(io.BytesIO(get(url, binary=True)), read_only=True, data_only=True)
    rows = list(wb["exhibit_history"].iter_rows(values_only=True))
    head = next(i for i, r in enumerate(rows) if str(r[0] or "").strip() == "Period")
    cols = [f"{band}_{str(c).replace('(1)', '').strip().lower()}"
            for band in ("bal", "exp", "imp") for c in rows[head][1:4]]
    assert cols[:3] == ["bal_total", "bal_goods", "bal_services"], rows[head]
    data, year = {}, None
    for r in rows[head + 1:]:
        label = str(r[0] or "").strip()
        if label.isdigit() and len(label) == 4:          # a year heading; its months follow
            year = int(label)
        elif label in MONTHS and year and isinstance(r[1], (int, float)):
            data[pd.Period(year=year, month=MONTHS.index(label) + 1, freq="M")] = r[1:10]
    return pd.DataFrame.from_dict(data, orient="index", columns=cols).astype(float)


def monthly(quarterly: pd.Series, exhibit_row: tuple, latest: pd.Period) -> pd.Series:
    """BEA's quarters spread evenly over their months, then the FT-900's months after them: the
    latest month and the one before as printed, any month in between as an equal share of
    what the year-to-date total leaves."""
    out = {m: v / 3 for q, v in quarterly.items() for m in pd.period_range(q.asfreq("M", "s"),
                                                                           q.asfreq("M", "e"))}
    cur, prev, ytd = exhibit_row
    covered = [q for q in quarterly.index if q.year == latest.year]
    last_bea_month = max((q.asfreq("M", "e") for q in covered),
                         default=pd.Period(year=latest.year - 1, month=12, freq="M"))
    if last_bea_month >= latest:
        return pd.Series(out).sort_index()
    out[latest] = cur
    filled = cur
    if latest - 1 > last_bea_month:
        out[latest - 1] = prev
        filled += prev
    elif latest.month == 1 and latest - 1 not in out:      # January: last month is December
        out[latest - 1] = prev
    between = pd.period_range(last_bea_month + 1, latest - 2) if latest - 2 > last_bea_month else []
    leftover = ytd - quarterly[covered].sum() - filled
    for m in between:
        out[m] = leftover / len(between)
    return pd.Series(out).sort_index()


def monthly_gdp(q: pd.Series) -> pd.Series:
    """Quarterly GDP (SAAR) to months: each quarter sits on its middle month, months between are
    interpolated log-linearly, and the year after the last quarter extends its latest growth."""
    t = np.array([p.year * 12 + p.quarter * 3 - 2 for p in q.index])  # middle month, counted
    lv = np.log(q.values)
    months = np.arange(t[0], t[-1] + 13)
    val = np.interp(months, t, lv)
    after = months > t[-1]
    val[after] = lv[-1] + (months[after] - t[-1]) * (lv[-1] - lv[-2]) / 3
    idx = [pd.Period(year=m // 12, month=m % 12 + 1, freq="M") for m in months]
    return pd.Series(np.exp(val), index=idx)


def year_to_date(s: pd.Series, through: int) -> pd.Series:
    """Sum of January..`through` for every year with all those months present."""
    s = s[[p.month <= through for p in s.index]]
    by_year = s.groupby([p.year for p in s.index])
    return by_year.sum()[by_year.count() == through]


# ---------------------------------------------------------------- the data-center lines
exports, imports = ft900_exhibit("exh7"), ft900_exhibit("exh8")
latest = exports["month"]
assert imports["month"] == latest, "the FT-900 exhibits disagree on the month"
net, dc_imports = {}, 0
for label, ita, row in CATS:
    x = monthly(bea_ita("ExpGds" + ita), exports["rows"][row], latest)
    m = monthly(bea_ita("ImpGds" + ita), imports["rows"][row], latest)
    net[label] = (x - m).dropna()
    dc_imports = dc_imports + m
dc_net = sum(net.values()).dropna()                               # $ millions, monthly

# The published balances: the FT-900's exhibit 1 history (balance-of-payments basis, seasonally
# adjusted, $ millions). FRED carries the same series (BOPGSTB, BOPGTB, BOPSTB, BOPGIMP), but its
# copies of 1999-2011 and 2016 have not taken some of Census's revisions (up to $1.2 billion a
# month in 1999-2000), so the history comes from Census's own workbook.
history = ft900_history()
total, goods, services = history["bal_total"], history["bal_goods"], history["bal_services"]
goods_imports = history["imp_goods"]
gdp_q = fred("GDP", "1990-01-01")                                 # nominal GDP, $ billions, SAAR
gdp_q.index = gdp_q.index.to_period("Q")
gdp = monthly_gdp(gdp_q)

# ---------------------------------------------------------------- 1. the year-to-date bars
through = latest.month
gdp_ytd = year_to_date(gdp / 12, through)                         # $ billions
panels = {"total": total, "dc": dc_net, "ex_dc": (total - dc_net).dropna(),
          "goods_ex_dc": (goods - dc_net).dropna()}
ytd = pd.DataFrame({k: year_to_date(v[v.index >= pd.Period("1999-01")], through) / 1000
                    for k, v in panels.items()}).dropna()
for k in panels:
    ytd[k + "_pct_gdp"] = 100 * ytd[k] / gdp_ytd.reindex(ytd.index)
ytd.index = pd.to_datetime([f"{y}-01-01" for y in ytd.index])
ytd.index.name = "date"
save(ytd, HERE, "ytd")

# ---------------------------------------------------------------- 2. imports, indexed to 2024 Q4
def quarterly_sum(s: pd.Series) -> pd.Series:
    q = s.groupby(s.index.asfreq("Q"))
    return q.sum()[q.count() == 3]


dcq, gq = quarterly_sum(dc_imports.dropna()), quarterly_sum(goods_imports)
both = dcq.index.intersection(gq.index)
both = both[both.year >= 2019]
index = pd.DataFrame({"dc": 100 * dcq[both] / dcq[BASE_QUARTER],
                      "other": 100 * (gq - dcq)[both] / (gq - dcq)[BASE_QUARTER]})
index.index = both.to_timestamp()
index.index.name = "date"
save(index, HERE, "imports_index")

# ---------------------------------------------------------------- 3. the change since 2024
def census_gold(flow: str) -> pd.Series:
    """Nonmonetary gold, HS 7108 + 7115, Census basis (not seasonally adjusted), $ millions."""
    prefix, value = ("E", "ALL_VAL_MO") if flow == "exports" else ("I", "GEN_VAL_MO")
    out = pd.Series(dtype=float)
    for hs in ("7108", "7115"):
        rows = json.loads(get(f"https://api.census.gov/data/timeseries/intltrade/{flow}/hs",
                              {"get": value, "COMM_LVL": "HS4", f"{prefix}_COMMODITY": hs,
                               "time": "from 2013-01", "key": key("CENSUS_API_KEY")}, timeout=120))
        out = out.add(pd.Series({pd.Period(r[-1], "M"): float(r[0]) / 1e6 for r in rows[1:]}),
                      fill_value=0)
    return out


try:
    gold = (census_gold("exports") - census_gold("imports")).dropna()
    for m, i in ((latest, 0), (latest - 1, 1)):     # a month the product data has not reached
        if m not in gold.index:
            gold[m] = exports["rows"]["Nonmonetary gold"][i] - imports["rows"]["Nonmonetary gold"][i]
    gold = gold.sort_index()
except SystemExit as e:                              # no CENSUS_API_KEY: skip the change chart
    gold = None
    print(f"(change chart skipped: {e})")

if gold is not None:
    parts = [("Total trade balance", "Total", total), ("Services", "Everything else", services),
             ("Gold", "Everything else", gold)]
    parts += [(label, "Data-center goods", net[label]) for label, _, _ in CATS]
    parts += [("All other goods", "Everything else", (goods - gold - dc_net).dropna())]
    gdp_mn = year_to_date(gdp * 1000 / 12, through)               # $ millions, same months
    rows = []
    for label, group, s in parts:
        sums = year_to_date(s, through)
        rows.append({"label": label, "group": group,
                     "value": (sums[latest.year] - sums[BASE_YEAR]) / 1000,
                     "value_pct_gdp": 100 * (sums[latest.year] / gdp_mn[latest.year]
                                             - sums[BASE_YEAR] / gdp_mn[BASE_YEAR])})
    change = pd.DataFrame(rows).set_index("label")
    save(change, HERE, "change_since_2024")
    print(f"Change, January–{MONTHS[through - 1]} {latest.year} vs. {BASE_YEAR}:")
    print(change.round(2).to_string(), "\n")

print(f"FT-900 through {MONTHS[through - 1]} {latest.year}. Year to date ($ billions, % of GDP):")
print(ytd.tail(3).round(2).to_string())
print("\nGoods imports, 2024 Q4 = 100:")
print(index.tail(3).round(2).to_string())
