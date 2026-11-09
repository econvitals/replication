#!/usr/bin/env python3
"""stock_gain_calc.py: the AI stock gain from company market values and the Federal Reserve's market totals.

    python refresh/stock_gain_calc.py                     # recompute data/stock_gain.csv's derived columns and check them
    python refresh/stock_gain_calc.py my_values.csv out.csv   # compute them for your own (updated) inputs

Input columns (one row per valuation date; $ billions except s): date, quarter, MV_NVDA, MV_MSFT, MV_GOOGL,
MV_AMZN, MV_META, MV_AVGO, MV_ORCL, M, M_alt_public_ex_funds, s. The first row is the base date (2022-11-30).

Definitions (base = the first row):
  sum7  = the seven companies' market value
  R     = M - sum7                                       the rest of the market (all U.S. corporate equity)
  G     = sum7 - sum7(base) * R / R(base)                 the extra gain: what the seven are worth minus what
                                                          they would be worth had they kept pace with the rest
  H     = s * G                                           the part households own (s = household share)
  R_alt, G_alt, H_alt                                     the same with M_alt (U.S. public companies, net of
                                                          shares issued by investment funds)
How the inputs were built for the post is in data/SOURCES.md (stock_gain.csv); refresh/README.md lists the
steps to update them. Standard library only.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TICKERS = ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "ORCL"]


def compute(rows):
    f = lambda r, k: float(r[k])
    base = rows[0]
    s7b = sum(f(base, f"MV_{t}") for t in TICKERS)
    Rb, Rab = f(base, "M") - s7b, f(base, "M_alt_public_ex_funds") - s7b
    out = []
    for r in rows:
        s7 = sum(f(r, f"MV_{t}") for t in TICKERS)
        R, Ra = f(r, "M") - s7, f(r, "M_alt_public_ex_funds") - s7
        G, Ga = s7 - s7b * R / Rb, s7 - s7b * Ra / Rab
        out.append({**r, "sum7": s7, "R": R, "G": G, "H": f(r, "s") * G, "R_alt": Ra, "G_alt": Ga, "H_alt": f(r, "s") * Ga})
    return out


def main():
    if len(sys.argv) == 3:
        rows = list(csv.DictReader(open(sys.argv[1])))
        out = compute(rows)
        with open(sys.argv[2], "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
        print("wrote", sys.argv[2]); return
    rows = list(csv.DictReader(open(ROOT / "data" / "stock_gain.csv")))
    worst = 0.0
    for r, o in zip(rows, compute(rows)):
        for k in ("sum7", "R", "G", "H", "R_alt", "G_alt", "H_alt"):
            worst = max(worst, abs(float(r[k]) - o[k]))
    # the published file rounds to $0.1 billion, and H/G use the household share rounded to four digits
    print(f"data/stock_gain.csv: derived columns recomputed; largest difference ${worst:.2f} billion "
          f"({'consistent with rounding' if worst < 3 else 'CHECK'})")


if __name__ == "__main__":
    main()
