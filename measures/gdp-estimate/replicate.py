"""Econvitals Current-Quarter GDP Estimate: reruns Econvitals' own engine (engine/) on public data and
sets the result beside the estimate econvitals.org shows.

    python replicate.py            # needs FRED_API_KEY, BEA_API_KEY and CENSUS_API_KEY (all free)
    python replicate.py --refit    # also fit the bridges afresh on today's data and show the difference
    python replicate.py --page data.json   # compare with a copy of the site's data saved earlier

Writes output/estimate.csv (the headline), output/components.csv (each component's share of GDP,
growth rate and contribution), output/first_print_gaps.csv (BEA's advance estimate minus today's
figure, by quarter: the first-print adjustment) and, with --refit, output/refit.csv.

The engine reads every source fresh (the downloads are cached for a few hours), fits nothing of its
own unless --refit is given, and uses the bridge coefficients the published estimate was made with,
which the site publishes beside it (data.json `house.bridges`): Econvitals refits them whenever BEA's
published history changes, from the data as they stood that day, so a fit made today can differ (see
README.md). Everything else is computed here.

The estimate is compared only when this run sees the same data the published one did: the same quarter,
and no report the engine reads printed after the day it was made. Otherwise the CSVs are written empty
and the nightly check reports nothing to compare.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from common.econdata import get, save  # noqa: E402
from engine import bridge, model, sources as S, vintages as V  # noqa: E402
from engine import calendar as cal  # noqa: E402
from engine import components as C  # noqa: E402
from engine.public_doors import current_quarter  # noqa: E402

PAGE = "https://econvitals.org/tools/gdp-trackers/data.json"
SOURCE_CACHE = S.RAW          # the engine's own copies of each source; cleared so every run reads fresh


def fresh_sources() -> None:
    """Delete the engine's saved copies of its catalog's sources, which it keeps until told to refresh,
    so each is fetched again when first read. (The downloads themselves are cached for a few hours, by
    common/econdata.py, engine/eits.py and the trade readers in engine/sources.py.)"""
    for name in list(S.MONTHLY) + list(S.QUARTERLY):
        (SOURCE_CACHE / f"{name}.json").unlink(missing_ok=True)


def first_print_vintages(since: str) -> None:
    """The archived versions (ALFRED) of BEA's ten component series, from which the engine measures each
    component's first-print gap: downloaded when missing or when they hold nothing from `since` (BEA's
    latest advance estimate) on, as Econvitals' engine does before it refits."""
    errors = [f"{k}: {v}" for k, v in V.refresh_stale(sorted({C.TARGET[c] for c in C.COMPONENTS}), since).items()
              if str(v).startswith("ERR")]
    if errors:
        sys.exit(f"ALFRED's archive could not be read ({errors[0]}); try again later.")


def changed_since(day: str) -> list[str]:
    """Reports the engine reads that printed after `day`: the data have moved since the site's estimate.
    Every one prints at 8:30 or 10:00 a.m. Eastern, so today's count only from 8:30."""
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    last = now.date().isoformat() if now.time() >= dt.time(8, 30) else (now.date() - dt.timedelta(days=1)).isoformat()
    return sorted({f"{r} ({d})" for r in cal.CARRIES for d in cal.dates(r) if day < d <= last})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refit", action="store_true", help="also fit the bridges afresh and show the difference")
    ap.add_argument("--page", type=Path, help=f"a saved copy of {PAGE} to compare with (default: the live one)")
    args = ap.parse_args()

    page = json.loads(args.page.read_text() if args.page else get(PAGE))
    house = page.get("house") or {}
    published_coefs = (house.get("bridges") or {}).get("components")

    fresh_sources()
    q = current_quarter()
    last_advance = cal.advance_gdp_date(pd.Period(q, freq="Q") - 1) or dt.date.today().isoformat()
    first_print_vintages(last_advance)

    gaps = model.first_print_gaps()
    if not len(gaps):
        sys.exit("The Atlanta Fed's GDPNow workbook could not be read, so the first-print adjustment "
                 "cannot be measured; try again later.")

    why_not = []
    if page.get("quarter") != q:
        why_not.append(f"the site shows {page.get('quarter')}, the quarter in progress here is {q}")
    moved = changed_since(house.get("as_of") or "9999")
    if moved:
        why_not.append("reports the engine reads printed after the site's estimate of "
                       f"{house.get('as_of')}: {', '.join(moved)}")
    if not published_coefs:
        why_not.append("the published data carry no bridge coefficients")

    coefs = published_coefs or bridge.fit()
    est = model.Engine(coefs).nowcast(q)
    if not why_not and est["stage_label"] != house.get("stage_label"):
        why_not.append(f"the latest report in hand here is {est['stage_label']!r}, the site's {house.get('stage_label')!r}")

    comparable = not why_not
    # keyed "house", as the site's tracker table keys the Econvitals estimate
    rows = [{"key": "house", "quarter": q, "as_of": house.get("as_of"), "value": est["value"],
             "value_raw": est["value_raw"], "first_print_offset": est["first_print_offset"],
             "stage_label": est["stage_label"], "published": house.get("value")}] if comparable else []
    save(pd.DataFrame(rows, columns=["key", "quarter", "as_of", "value", "value_raw", "first_print_offset",
                                     "stage_label", "published"]).set_index("key"), HERE, "estimate")
    comp_rows = [{"key": k, "label": r["label"], "share": r.get("share"), "growth": r["bridged"],
                  "contribution": r["contribution"], "months": r["months"]}
                 for k, r in est["components"].items()] if comparable else []
    save(pd.DataFrame(comp_rows, columns=["key", "label", "share", "growth", "contribution", "months"])
         .set_index("key"), HERE, "components")
    g = pd.DataFrame({"gap": gaps})
    g["used"] = g.index <= pd.Period(q, freq="Q") - 1 - model.FIRST_PRINT_LAG
    save(g.rename_axis("quarter").set_axis(g.index.astype(str)), HERE, "first_print_gaps")

    print(f"{q}: {est['value']:.4f} percent at an annual rate ({est['stage_label']}): {est['value_raw']:.4f} from "
          f"the components, {est['first_print_offset']:+.4f} first-print adjustment "
          f"(the mean over {int(g['used'].sum())} quarters).")
    print(f"econvitals.org: {house.get('value')} as of {house.get('as_of')} ({house.get('stage_label')}): "
          f"{house.get('value_raw')} from the components, {house.get('first_print_offset')} first-print adjustment.")
    if comparable:
        pub = {c["key"]: c for c in house.get("components") or []}
        print(f"\n{'component':34s} {'share':>7s} {'growth':>8s} {'contrib':>8s} {'site':>8s}")
        for k, r in est["components"].items():
            share = r.get("share")
            print(f"{r['label']:34s} {share if share is not None else float('nan'):7.4f} {r['bridged']:8.4f} "
                  f"{r['contribution']:8.4f} {(pub.get(k) or {}).get('contribution', float('nan')):8.4f}")
        print(f"\nDifference from the site: {est['value'] - house['value']:+.4f} point.")
    else:
        print("Not compared today: " + "; ".join(why_not) + ".")

    if args.refit:
        fresh = bridge.fit()
        alt = model.Engine(fresh).nowcast(q)
        diff = [{"component": c, "published_const": coefs[c]["const"], "refit_const": fresh[c]["const"],
                 "published_coef": json.dumps(coefs[c]["coef"]), "refit_coef": json.dumps(fresh[c]["coef"]),
                 "published_n": coefs[c].get("n"), "refit_n": fresh[c]["n"]} for c in C.COMPONENTS]
        save(pd.DataFrame(diff).set_index("component"), HERE, "refit")
        print(f"\nWith the bridges fit afresh on today's data: {alt['value']:.4f} "
              f"({alt['value'] - est['value']:+.4f} point).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
