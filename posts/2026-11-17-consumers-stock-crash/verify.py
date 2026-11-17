#!/usr/bin/env python3
"""verify.py: check the rebuilt numbers against the numbers printed in the post and in its online appendix.

expected.csv holds those numbers, typed from the post and the appendix themselves (never from the rebuilt output),
each with the sentence, table cell or chart label it comes from. A row passes when
  * expected and tol are given:  |rebuilt - expected| <= tol, where tol is half a unit of the last printed digit
    (so "2.1 percent" passes for anything that rounds to 2.1); a few "about" numbers carry a wider tolerance,
    stated in the row's note;
  * lo and/or hi are given:       lo <= rebuilt <= hi (ranges and qualitative statements, made explicit in the note);
  * the expected value is text:   an exact match.
Rows whose note starts "CITED:" quote other people's work (or an earlier post) and are not rebuilt here, and rows
whose note starts "INPUT:" are the post's assumptions (the size of the market fall, the 3 percent rule of thumb);
both are listed as CITED, not checked. A row whose metric needs a file that is not in the package (the column "needs":
licensed/... or county/...) is SKIPPED, not failed.

Second, every cell of the appendix's tables (expected_appendix_tables.csv, read off the published page) is compared,
as printed text, with the same table rebuilt by wealth/appendix_tables.py. The literature table (A1) and the
county table (A17) are typed from the papers and the county study, not rebuilt, so they are not compared.

    python verify.py         # PASS / FAIL / SKIPPED / CITED for every row; exit status 1 if anything fails
Writes output/verify_report.csv.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def check(row, nums):
    if row["note"].startswith("CITED"):
        return "CITED", None, "quotation, not rebuilt"
    if row["note"].startswith("INPUT"):
        return "CITED", None, "assumption of the post, not a result"
    m = row["metric"]
    if m not in nums:
        if row["needs"]:
            return "SKIPPED", None, f"needs {row['needs']}"
        return "FAIL", None, "not computed"
    v, exp = nums[m], row["expected"]
    if exp != "" and num(exp) is None:
        return ("PASS" if str(v) == exp else "FAIL"), v, f"expected {exp}"
    v = float(v)
    lo, hi = num(row["lo"]), num(row["hi"])
    if lo is not None or hi is not None:
        ok = (lo is None or v >= lo - 1e-12) and (hi is None or v <= hi + 1e-12)
        rng = f"range [{'-inf' if lo is None else f'{lo:g}'}, {'inf' if hi is None else f'{hi:g}'}]"
        return ("PASS" if ok else "FAIL"), v, rng
    e, t = float(exp), float(row["tol"])
    return ("PASS" if abs(v - e) <= t + 1e-9 else "FAIL"), v, f"expected {e:g} ± {t:g}"


def main():
    if not (OUT / "numbers.json").exists():
        sys.exit("verify: output/numbers.json is missing; run python run_all.py first")
    nums = json.loads((OUT / "numbers.json").read_text())
    rows = list(csv.DictReader(open(ROOT / "expected.csv", encoding="utf-8")))
    out = []
    for r in rows:
        status, v, rule = check(r, nums)
        out.append({**r, "rebuilt": v, "rule": rule, "status": status})
    w = max(len(r["id"]) for r in rows)
    kinds = ("PASS", "FAIL", "SKIPPED", "CITED")
    for where in dict.fromkeys(o["where"] for o in out):
        sub = [o for o in out if o["where"] == where]
        n = {s: sum(o["status"] == s for o in sub) for s in kinds}
        print(f"\n== {where}: {n['PASS']} pass, {n['FAIL']} fail, {n['SKIPPED']} skipped, {n['CITED']} cited (of {len(sub)})")
        for o in sub:
            if o["status"] == "PASS" and "--all" not in sys.argv:
                continue
            v = o["rebuilt"]
            vs = "" if v is None else (v if isinstance(v, str) else f"{v:.3f}")
            q = o["quote"] if len(o["quote"]) <= 70 else o["quote"][:67] + "..."
            print(f"{o['status']:7s}  {o['id']:<{w}s}  {vs:>11}  {o['rule']:<30s}  {q}")
    with open(OUT / "verify_report.csv", "w", newline="", encoding="utf-8") as f:
        dw = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        dw.writeheader()
        dw.writerows(out)
    # ---- the appendix's tables, cell by cell
    tab_fail = 0
    tables = json.loads((OUT / "appendix_tables.json").read_text()) if (OUT / "appendix_tables.json").exists() else {}
    cells = [c for c in csv.DictReader(open(ROOT / "expected_appendix_tables.csv", encoding="utf-8")) if c["table"] not in ("tA1", "tA17")]
    for c in cells:
        t, i, j = c["table"], int(c["row"]), int(c["col"])
        got = tables.get(t, [])
        v = got[i][j] if i < len(got) and j < len(got[i]) else None
        if v != c["cell"]:
            tab_fail += 1
            print(f"FAIL     appendix {t} row {i} col {j}: published {c['cell']!r}, rebuilt {v!r}")
    print(f"\n== appendix tables A2-A16, A18-A20: {len(cells) - tab_fail} of {len(cells)} cells identical to the published page")
    n = {s: sum(o["status"] == s for o in out) for s in kinds}
    n["FAIL"] += tab_fail
    print(f"\nverify: {n['PASS']} PASS, {n['FAIL']} FAIL, {n['SKIPPED']} SKIPPED (need files not in the package), "
          f"{n['CITED']} CITED (quotations and assumptions) out of {len(rows)} numbers from the post and its appendix"
          + ("" if "--all" in sys.argv else "   (python verify.py --all lists the passes too)"))
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
