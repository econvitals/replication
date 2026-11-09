"""descriptive.py: the descriptive series behind figures 1-5 and the post's descriptive facts, from data/."""
import numpy as np
import pandas as pd

from . import inputs as I
from . import paths


def capex_booms():
    return pd.read_csv(paths.DATA / "capex_booms_van_nieuwerburgh.csv")


def buildout_shares():
    """Figure 2: percent of GDP, 1990Q1-2026Q3. Data centers: Census C30 (quarterly average of monthly annual
    rates) for 2014Q1-2019Q4, BEA data-center structures (NIPA 5.4.5U, LA001282) from 2020Q1, zero before 2014
    (they sat inside office buildings)."""
    B = I.bea()
    vip = I.c30()["Data center"]
    dcq = vip.groupby(vip.index.to_period("Q")).mean()
    dc = B["LA001282"].copy()
    splice = dcq.loc["2014Q1":"2019Q4"]
    dc.loc[splice.index] = splice.values
    dc = dc.fillna(0.0)
    g = B["A191RC"]
    sh = pd.DataFrame({"comp": 100 * B["B935RC"] / g, "commeq": 100 * B["C275RC"] / g,
                       "commst": 100 * B["C314RC"] / g, "dc": 100 * dc / g})
    sh["total"] = sh[["comp", "commeq", "commst", "dc"]].sum(axis=1)
    sh["telecom_vn"] = sh["commeq"] + sh["commst"]                  # Van Nieuwerburgh's telecom-and-fiber measure
    sh["dollars_bn"] = (B["B935RC"] + B["C275RC"] + B["C314RC"] + dc) / 1e3
    return sh.loc["1990Q1":].dropna(subset=["comp"])


def investment_shares():
    """Figure 4, left, and the investment facts: percent of nominal GDP. 'Excluding buildout' leaves out
    computers and peripheral equipment, communication equipment and data-center structures."""
    B = I.bea()
    ai = B["B935RC"] + B["C275RC"] + B["LA001282"].fillna(0)
    g = B["A191RC"]
    out = pd.DataFrame({"nonres": 100 * B["A008RC"] / g, "nonres_ex": 100 * (B["A008RC"] - ai) / g,
                        "fixed": 100 * B["A007RC"] / g, "fixed_ex": 100 * (B["A007RC"] - ai) / g})
    return out.loc["2015Q1":].dropna(subset=["nonres"])


def nonres_share_history():
    B = I.bea()
    return (100 * B["A008RC"] / B["A191RC"]).dropna()


BARS = [("Data center", "Data center", "Data centers"), ("Manufacturing", "Manufacturing", "Other nonresidential"),
        ("Power", "Power (inc. Gas and Oil)", "Other nonresidential"), ("Health care", "Health care", "Other nonresidential"),
        ("Educational", "Educational", "Other nonresidential"), ("Lodging", "Lodging", "Other nonresidential"),
        ("Commercial (incl. warehouses)", "Commercial (inc. Farm)", "Other nonresidential"),
        ("Office ex-data-center", "office_ex_dc", "Other nonresidential"),
        ("Nonresidential total", "Nonresidential", "Other nonresidential"),
        ("Single family", "New single family", "Residential"), ("Multi-family", "New multifamily", "Residential"),
        ("Residential total", "Residential (inc. Improvements)", "Residential")]
EXTRA = [("Warehouse", "Warehouse"), ("Nonresidential excluding data centers", "nonres_ex_dc"),
         ("Nonresidential excluding data centers and power", "nonres_ex_dc_power"), ("Electric", "Electric")]


def construction_levels():
    c = I.c30()
    c["office_ex_dc"] = c["Office"] - c["Data center"]
    c["nonres_ex_dc"] = c["Nonresidential"] - c["Data center"]
    c["nonres_ex_dc_power"] = c["Nonresidential"] - c["Data center"] - c["Power (inc. Gas and Oil)"]
    ppi = I.fred("WPSFD43")
    c = c.join(ppi.rename("ppi"), how="inner")
    return c


def construction_growth(month="2026-09-01"):
    """Figure 4, right: percent change from twelve months earlier, nominal and deflated by the BLS PPI for
    final demand construction (WPSFD43)."""
    c = construction_levels()
    L = pd.Timestamp(month); P = L - pd.DateOffset(years=1)
    rows = []
    for lab, col, grp in BARS + [(a, b, "extra") for a, b in EXTRA]:
        nom = 100 * (c.loc[L, col] / c.loc[P, col] - 1)
        real = 100 * ((c.loc[L, col] / c.loc[L, "ppi"]) / (c.loc[P, col] / c.loc[P, "ppi"]) - 1)
        rows.append({"label": lab, "group": grp, "nominal": nom, "real": real})
    df = pd.DataFrame(rows)
    df.attrs["ppi_change"] = 100 * (c.loc[L, "ppi"] / c.loc[P, "ppi"] - 1)
    return df


def construction_bars():
    d = construction_growth()
    return d[d.group != "extra"].reset_index(drop=True)


def stock_index():
    """Figure 3: the seven companies' market value and the rest of the U.S. public-company market, indexed to
    Nov. 30, 2022 = 100, at quarter ends (the 2022-12-30 point is left out) and the latest close."""
    sg = pd.read_csv(paths.DATA / "stock_gain.csv")
    sg["d"] = pd.to_datetime(sg["date"])
    sg = sg[sg["date"] != "2022-12-30"].reset_index(drop=True)
    yr = sg.d.dt.year + (sg.d.dt.dayofyear - 1) / np.where(sg.d.dt.is_leap_year, 366, 365)
    base = sg.iloc[0]
    return pd.DataFrame({"x": yr.round(4), "date": sg["date"], "seven": 100 * sg.sum7 / base.sum7,
                         "rest": 100 * sg.R_alt / base.R_alt})


def stocks():
    return pd.read_csv(paths.DATA / "stock_gain.csv")


def trade_ytd(months=9):
    """Figure 5: the balance on goods and services and its data-center-goods part, January-September of each
    year, percent of GDP (the same months' nominal GDP: the first three quarters' annual rates / 4)."""
    t = pd.read_csv(paths.DATA / "trade_dc_goods_m.csv", index_col=0)
    tot = I.fred("BOPGSTB")
    tot.index = tot.index.strftime("%Y-%m")
    g = I.bea()["A191RC"]
    rows = {}
    for y in range(2015, 2027):
        m = [f"{y}-{i:02d}" for i in range(1, months + 1)]
        gdp = sum(g[pd.Period(f"{y}Q{q}", "Q")] for q in range(1, months // 3 + 1)) / 4
        dc = (t.loc[m, "dc_x"] - t.loc[m, "dc_m"]).sum()
        total = tot.loc[m].sum()
        rows[y] = {"dc": 100 * dc / gdp, "total": 100 * total / gdp, "other": 100 * (total - dc) / gdp,
                   "dc_imports": 100 * t.loc[m, "dc_m"].sum() / gdp}
    return pd.DataFrame(rows).T


def dc_goods_imports_full_year():
    """Gross imports of data-center goods, percent of GDP, by calendar year (2015-2025)."""
    t = pd.read_csv(paths.DATA / "trade_dc_goods_m.csv", index_col=0)
    g = I.bea()["A191RC"]
    out = {}
    for y in range(2015, 2026):
        m = [f"{y}-{i:02d}" for i in range(1, 13)]
        out[y] = 100 * t.loc[m, "dc_m"].sum() / (sum(g[pd.Period(f"{y}Q{q}", "Q")] for q in range(1, 5)) / 4)
    return pd.Series(out)


def nx_share_annual():
    B = I.bea()
    a = B[["A019RC", "A191RC"]].dropna()
    a = a.groupby(a.index.year).sum()
    return 100 * a["A019RC"] / a["A191RC"]
