"""Cut the CSVs in this folder out of the original CBO, OMB and Census files.

You do not need to run this: the CSVs it writes are already here. It is kept so anyone can see
exactly which cells each number came from, and redo the cut if CBO publishes a new vintage.

    python cut_inputs.py <folder holding the original files>

The folder must hold, under these names (download them by hand; CBO refuses scripted downloads):
    51118-2026-02-Budget-Projections.xlsx      CBO, cbo.gov/publication/61882 (February 2026)
    51134-2026-02-Historical-Budget-Data.xlsx  CBO, cbo.gov/publication/61882 (February 2026)
    51119-2026-02-25-LTBO-Budget.xlsx          CBO, cbo.gov/publication/62044 (February 2026)
    57054-2026-02-LTBO-econ.xlsx               CBO, cbo.gov/publication/62044 (February 2026)
    hist01z1.xlsx, hist01z2.xlsx, hist03z1.xlsx, hist07z1.xlsx
                                               OMB Historical Tables, FY2027 Budget
The Census figures (Series F 1) are typed from the printed table; see the README.
"""
import sys
from pathlib import Path

import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent


def rows(path, sheet=None):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=sheet is not None)
    ws = wb[sheet] if sheet else wb.active
    return [list(r) for r in ws.iter_rows(values_only=True)]


def num(v):
    return float(v) if isinstance(v, (int, float)) else None


def main(src: Path):
    # 1. CBO's ten-year baseline, Table 1-1 (billions of dollars). Column B is 2025 (actual),
    #    C..M are 2026-2036. CBO prints deficits as negative numbers; they are kept as printed.
    t11 = rows(src / "51118-2026-02-Budget-Projections.xlsx", "Table 1-1")
    years = list(range(2025, 2037))
    want = {"revenues": (17, "Total"), "outlays": (24, "Total"), "net_interest": (23, "Net interest"),
            "deficit_neg": (27, "Total deficit"), "primary_deficit_neg": (30, "Primary deficit"),
            "debt_held_public": (31, "Debt held by the public"), "gdp": (33, "GDP")}
    out = {}
    for name, (r, label) in want.items():
        row = t11[r - 1]
        assert str(row[0]).strip().startswith(label), (name, row[0])
        out[name] = [num(row[1 + i]) for i in range(len(years))]
    pd.DataFrame(out, index=pd.Index(years, name="fiscal_year")).to_csv(
        HERE / "cbo_budget_projections_2026-02.csv")

    # 2. CBO's historical budget data since 1962 (billions of dollars): sheet 1 for revenues,
    #    outlays, the total deficit and debt held by the public; sheet 3 for net interest.
    s1 = {int(r[0]): r for r in rows(src / "51134-2026-02-Historical-Budget-Data.xlsx",
                                     "1. Rev, Outlays, Surplus, Debt") if isinstance(r[0], (int, float))}
    s3 = {int(r[0]): r for r in rows(src / "51134-2026-02-Historical-Budget-Data.xlsx",
                                     "3. Outlays") if isinstance(r[0], (int, float))}
    hist = pd.DataFrame({"revenues": {y: num(r[1]) for y, r in s1.items()},
                         "outlays": {y: num(r[2]) for y, r in s1.items()},
                         "surplus": {y: num(r[6]) for y, r in s1.items()},
                         "debt_held_public": {y: num(r[7]) for y, r in s1.items()},
                         "net_interest": {y: num(r[4]) for y, r in s3.items()}})
    hist.index.name = "fiscal_year"
    hist.loc[1962:2024].to_csv(HERE / "cbo_historical_budget_data_2026-02.csv")

    # 3. CBO's extended baseline to 2056 (percent of GDP, and GDP in trillions of dollars),
    #    Long-Term Budget Outlook, sheet "1. Summary Ext Baseline".
    cols = {6: "revenues_pct", 13: "noninterest_outlays_pct", 14: "net_interest_pct",
            15: "outlays_pct", 16: "primary_deficit_neg_pct", 17: "deficit_neg_pct",
            18: "debt_pct", 21: "gdp_trillions"}
    lt = [r for r in rows(src / "51119-2026-02-25-LTBO-Budget.xlsx", "1. Summary Ext Baseline")
          if isinstance(r[0], int) and 2026 <= r[0] <= 2056]
    pd.DataFrame({name: {r[0]: num(r[j]) for r in lt} for j, name in cols.items()}).rename_axis(
        "fiscal_year").to_csv(HERE / "cbo_ltbo_extended_baseline_2026-02.csv")

    # 4. The two rates the long-run debt arithmetic needs, from the LTBO economic data:
    #    the average interest rate on debt held by the public (net interest in a fiscal year
    #    divided by debt at the end of the previous one) and nominal GDP growth, in percent.
    ec = rows(src / "57054-2026-02-LTBO-econ.xlsx", "1. Econ Vars_Annual Rates")
    hdr = next(r for r in ec if sum(isinstance(c, int) and 1990 < c < 2100 for c in r) > 20)
    g_row = next(r for r in ec if isinstance(r[0], str) and r[0].strip().lower().startswith("nominal gdp"))
    r_row = next(r for r in ec if isinstance(r[0], str)
                 and "all federal debt held by the public" in r[0].lower())
    rates = {y: (num(r_row[j]), num(g_row[j])) for j, y in enumerate(hdr)
             if isinstance(y, int) and 2025 <= y <= 2056}
    pd.DataFrame(rates, index=["interest_rate_pct", "nominal_gdp_growth_pct"]).T.rename_axis(
        "year").to_csv(HERE / "cbo_ltbo_interest_and_growth_2026-02.csv")

    # 5. OMB Historical Tables, 1901-1990: receipts, outlays and the surplus (Table 1.1,
    #    millions), fiscal-year GDP (Table 1.2, billions, from 1930), net interest (Table 3.1,
    #    millions, from 1940) and debt held by the public as a percent of GDP (Table 7.1, from
    #    1940). A balance OMB prints as "-*" (less than half a million dollars) is left blank.
    def by_year(tbl):
        out = {}
        for r in tbl:
            s = str(r[0]).strip()
            if s.isdigit() and 1901 <= int(s) <= 1990:
                out[int(s)] = r
        return out
    t1 = by_year(rows(src / "hist01z1.xlsx"))
    t2 = by_year(rows(src / "hist01z2.xlsx"))
    t7 = by_year(rows(src / "hist07z1.xlsx"))
    t3 = rows(src / "hist03z1.xlsx")
    head = t3[1]
    ni_row = next(r for r in t3 if r[0] and str(r[0]).strip().lower() == "net interest")
    ni = {int(str(h)[:4]): num(v) for h, v in zip(head[1:], ni_row[1:])
          if h is not None and str(h)[:4].isdigit() and int(str(h)[:4]) <= 1990}
    omb = pd.DataFrame({"receipts": {y: num(r[1]) for y, r in t1.items()},
                        "outlays": {y: num(r[2]) for y, r in t1.items()},
                        "surplus": {y: num(r[3]) for y, r in t1.items()},
                        "gdp": {y: num(r[1]) for y, r in t2.items()},
                        "net_interest": ni,
                        "debt_pct_gdp": {y: num(r[8]) for y, r in t7.items()}}).sort_index()
    omb.index.name = "fiscal_year"
    omb.to_csv(HERE / "omb_historical_tables_fy2027.csv")
    print("wrote the CSVs in", HERE)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
