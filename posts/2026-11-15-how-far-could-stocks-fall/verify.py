#!/usr/bin/env python3
"""verify.py: check the rebuilt numbers against the numbers printed in the post.

expected.csv holds the post's numbers, typed from the post itself (never from the rebuilt output), each with
the sentence, table cell or chart label it comes from. A row passes when
  * expected and tol are given:  |rebuilt - expected| <= tol, where tol is half a unit of the post's last
    printed digit (so "18 percent" passes for anything that rounds to 18), plus 0.0005 for table cells and chart
    labels; a few "about" numbers carry a wider tolerance, stated in the row's note;
  * lo and/or hi are given:       lo <= rebuilt <= hi (approximate or qualitative statements, made explicit in the note);
  * the expected value is text:   an exact match.
A row whose metric needs a licensed file that is not in licensed/ is SKIPPED, not failed (column "needs").

    python verify.py         # PASS / FAIL / SKIPPED for every row; exit status 1 if anything fails
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


def check(row, nums, skipped):
    m = row["metric"]
    if m not in nums:
        if m in skipped:
            return "SKIPPED", None, f"needs licensed/{skipped[m]}"
        return "FAIL", None, "not computed"
    v, exp = nums[m], row["expected"]
    if exp != "" and num(exp) is None:
        return ("PASS" if str(v) == exp else "FAIL"), v, f"expected {exp}"
    v = float(v)
    lo, hi = num(row["lo"]), num(row["hi"])
    if lo is not None or hi is not None:
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        rng = f"range [{'-inf' if lo is None else f'{lo:g}'}, {'inf' if hi is None else f'{hi:g}'}]"
        return ("PASS" if ok else "FAIL"), v, rng
    e, t = float(exp), float(row["tol"])
    return ("PASS" if abs(v - e) <= t + 1e-12 else "FAIL"), v, f"expected {e:g} ± {t:g}"


def main():
    if not (OUT / "numbers.json").exists():
        sys.exit("verify: output/numbers.json is missing; run python run_all.py first")
    nums = json.loads((OUT / "numbers.json").read_text())
    skipped = json.loads((OUT / "skipped.json").read_text())
    rows = list(csv.DictReader(open(ROOT / "expected.csv", encoding="utf-8")))
    out = []
    for r in rows:
        status, v, rule = check(r, nums, skipped)
        out.append({**r, "rebuilt": v, "rule": rule, "status": status})
    w = max(len(r["id"]) for r in rows)
    for where in ("text", "table", "figure"):
        sub = [o for o in out if o["where"] == where]
        n = {s: sum(o["status"] == s for o in sub) for s in ("PASS", "FAIL", "SKIPPED")}
        print(f"\n== {where}: {n['PASS']} pass, {n['FAIL']} fail, {n['SKIPPED']} skipped (of {len(sub)})")
        for o in sub:
            v = o["rebuilt"]
            vs = "" if v is None else (v if isinstance(v, str) else f"{v:.3f}")
            q = o["quote"] if len(o["quote"]) <= 80 else o["quote"][:77] + "..."
            print(f"{o['status']:7s}  {o['id']:<{w}s}  {vs:>11}  {o['rule']:<36s}  {q}")
    with open(OUT / "verify_report.csv", "w", newline="", encoding="utf-8") as f:
        dw = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        dw.writeheader()
        dw.writerows(out)
    n = {s: sum(o["status"] == s for o in out) for s in ("PASS", "FAIL", "SKIPPED")}
    print(f"\nverify: {n['PASS']} PASS, {n['FAIL']} FAIL, {n['SKIPPED']} SKIPPED (need licensed data) "
          f"out of {len(rows)} numbers from the post")
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()
