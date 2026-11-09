#!/usr/bin/env python3
"""verify.py: check the rebuilt results against the numbers printed in the post.

expected.csv holds every number in the post's text, its table and its figures, typed from the post itself
(never from the rebuilt outputs), with the sentence or label it comes from. A row passes when
  * expected and tol are given:  |rebuilt - expected| <= tol, where tol is half a unit of the post's last
    printed digit (so "about 0.3" passes for anything that rounds to 0.3), plus 0.0005 for table cells and
    figure labels to allow for last-digit differences across machines; values read off a chart carry a reading tolerance;
  * lo and/or hi are given:       lo <= rebuilt <= hi (qualitative statements, made explicit in the note);
  * the expected value is text:   an exact match (alternatives separated by "|").
The rebuilt values come from output/results/facts.json (written by python -m dcboom.facts).

    python verify.py            # prints PASS/FAIL for every row; exit status 1 if anything fails
Writes output/results/verify_report.csv.
"""
import csv
import json
import sys
from pathlib import Path

from dcboom import paths


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def check(row, facts):
    v = facts.get(row["metric"])
    if v is None:
        return "FAIL", None, "not computed"
    exp = row["expected"]
    if exp != "" and num(exp) is None:                     # text
        ok = str(v) in exp.split("|")
        return ("PASS" if ok else "FAIL"), v, f"expected {exp}"
    v = float(v)
    lo, hi = num(row["lo"]), num(row["hi"])
    if lo is not None or hi is not None:
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
        rng = f"[{'' if lo is None else lo}, {'' if hi is None else hi}]"
        return ("PASS" if ok else "FAIL"), v, f"range {rng}"
    e, t = float(exp), float(row["tol"])
    ok = abs(v - e) <= t + 1e-12
    return ("PASS" if ok else "FAIL"), v, f"expected {e:g} ± {t:g}"


def main():
    facts_f = paths.OUT_RESULTS / "facts.json"
    if not facts_f.exists():
        sys.exit("verify: output/results/facts.json is missing; run python run_all.py first")
    facts = json.loads(facts_f.read_text())
    rows = list(csv.DictReader(open(paths.ROOT / "expected.csv", encoding="utf-8")))
    out, npass = [], 0
    for r in rows:
        status, v, rule = check(r, facts)
        npass += status == "PASS"
        out.append({**r, "rebuilt": v, "rule": rule, "status": status})
    w = max(len(r["id"]) for r in rows)
    for where in ("text", "table", "figure"):
        sub = [o for o in out if o["where"] == where]
        print(f"\n== {where} ({sum(o['status'] == 'PASS' for o in sub)}/{len(sub)} pass)")
        for o in sub:
            v = o["rebuilt"]
            vs = v if isinstance(v, str) or v is None else f"{v:.4f}"
            q = o["quote"] if len(o["quote"]) <= 95 else o["quote"][:92] + "..."
            print(f"{o['status']:4s}  {o['id']:<{w}s}  rebuilt {vs:>10}  {o['rule']:<22s}  {q}")
    with open(paths.OUT_RESULTS / "verify_report.csv", "w", newline="", encoding="utf-8") as f:
        dw = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        dw.writeheader(); dw.writerows(out)
    nfail = len(rows) - npass
    print(f"\nverify: {npass} PASS, {nfail} FAIL out of {len(rows)} numbers from the post")
    news = json.loads((paths.OUT_RESULTS / "news2026.json").read_text())
    if "_did_not_solve" in news:
        print(f"note: as in the original work, expectations switching on in 2026 with a productivity belief of "
              f"{news['_did_not_solve']['prod']} did not solve (the post's parenthetical rests on the beliefs that did)")
    elif "_not_attempted" in news:
        print("note: expectations switching on in 2026 with a productivity belief of 0.5 was not attempted; it does not "
              "solve (python run_all.py --try-unsolved shows this); the post's parenthetical rests on beliefs 0 to 0.4")
    sys.exit(0 if nfail == 0 else 1)


if __name__ == "__main__":
    main()
