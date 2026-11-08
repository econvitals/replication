"""Cut the CSVs in this folder out of CBO's original February 2026 workbooks.

You do not need to run this: the CSVs it writes are already here. It is kept so anyone can see
exactly which cells each number came from, and redo the cut for a new CBO vintage.

    python cut_inputs.py <folder holding the original workbooks>

The folder must hold, under these names (download them by hand; CBO refuses scripted downloads):
    51118-2026-02-Budget-Projections.xlsx      cbo.gov/publication/61882
    51134-2026-02-Historical-Budget-Data.xlsx  cbo.gov/publication/61882
    51135-2026-02-Economic-Projections.xlsx    cbo.gov/publication/61882
"""
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent


def rows(path, sheet):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    return [list(r) for r in wb[sheet].iter_rows(values_only=True)]


def num(v):
    return float(v) if isinstance(v, (int, float)) else None


def main(src: Path):
    # Net interest (sheet 3) and debt held by the public (sheet 1), $ billions, 1990-2024.
    hb = src / "51134-2026-02-Historical-Budget-Data.xlsx"
    s1 = {int(r[0]): r for r in rows(hb, "1. Rev, Outlays, Surplus, Debt") if isinstance(r[0], (int, float))}
    s3 = {int(r[0]): r for r in rows(hb, "3. Outlays") if isinstance(r[0], (int, float))}
    pd.DataFrame({"net_interest": {y: num(s3[y][4]) for y in range(1990, 2025)},
                  "debt_held_public": {y: num(s1[y][7]) for y in range(1990, 2025)}}).rename_axis(
        "fiscal_year").to_csv(HERE / "cbo_historical_budget_data_2026-02.csv")

    # The ten-year baseline, Table 1-1: column B is 2025 (actual), C..M are 2026-2036.
    t11 = rows(src / "51118-2026-02-Budget-Projections.xlsx", "Table 1-1")
    years = range(2025, 2037)
    want = {"net_interest": (23, "Net interest"), "debt_held_public": (31, "Debt held by the public"),
            "gdp": (33, "GDP")}
    out = {}
    for name, (r, label) in want.items():
        assert str(t11[r - 1][0]).strip().startswith(label), (name, t11[r - 1][0])
        out[name] = {y: num(t11[r - 1][1 + i]) for i, y in enumerate(years)}
    pd.DataFrame(out).rename_axis("fiscal_year").to_csv(HERE / "cbo_budget_projections_2026-02.csv")

    # CBO's quarterly projection of the PCE price index excluding food and energy (2017=100),
    # "1. Quarterly" sheet of the economic projections.
    q = rows(src / "51135-2026-02-Economic-Projections.xlsx", "1. Quarterly")
    qre = re.compile(r"^\s*(\d{4})Q([1-4])\s*$")
    hdr = next(r for r in q if sum(bool(isinstance(c, str) and qre.match(c)) for c in r) > 8)
    row = next(r for r in q if isinstance(r[0], str) and "excluding food and energy" in r[0].lower()
               and "price index" in r[0].lower())
    pd.Series({c.strip(): num(v) for c, v in zip(hdr, row) if isinstance(c, str) and qre.match(c)},
              name="core_pce_index").rename_axis("quarter").to_csv(
        HERE / "cbo_core_pce_projection_2026-02.csv")
    print("wrote the CSVs in", HERE)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
