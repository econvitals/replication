"""Run every replication script and compare what it produces with what econvitals.org shows.

    python tools/check_all.py                 # everything
    python tools/check_all.py --only real-wage-growth
    python tools/check_all.py --list          # what would run, and how each is judged

Each folder's `check.json` says which output column must match which published series, over how
many recent dates, and within what tolerance. A folder whose `status` is "documented" has no
runnable comparison (for example, it needs microdata the reader must request themselves); it is
reported as NOT COMPARED, never as a pass. A `published` path that starts with "repo:" names a
CSV in this repository (a track record under history/) instead of a file on econvitals.org;
`published_where` ({"column": "value", ...}) keeps only that CSV's rows that match, for a track
record with several rows per month (for example, only the last estimate made before the release),
and `from` ("YYYY-MM[-DD]") starts the comparison at that date.

Two ways to read a data file that is not a list of dated rows (a tool's own nested data file):
`published_glob` ("paths.*.*.g.*") takes every value at that path, each `*` matching every key of an
object or every item of a list (an item named by its "k" field when it has one, else its position),
and names each value by its matches joined with "|" ("gdp|1953|n10"); `published_fields` names the
columns of rows that are plain lists, and `published_index` may then be a list of fields, joined with
"|" the same way. `at_least` (a count) fails a comparison that finds fewer values in common, so a
script that quietly stopped writing rows cannot pass by matching nothing.

A series whose spec says `"may_be_empty": true` is one the script can rebuild only some of the time
(a tracked quarter after BLS has printed it; the day's estimate when no report has printed since the
site's last update). When the script writes no row for it, that series is reported as compared on
nothing today (`empty_why` says why), not as a pass and not as a mismatch; a folder whose every series
is like that tonight is NOT COMPARED TODAY. Rows written but matching no published date still fail.

A REVISION ALONE IS NOT A FAILURE (2026-11-25). The scripts download today's numbers; the site's
file was built from the numbers on the day it was last rebuilt. When an agency revises its data
in between, the two differ for a day or two without anything being wrong (on November 25, 2026,
FHFA's monthly house price release and the Federal Reserve's full-history revision of industrial
production, both out on the 24th, failed two measures whose site files had not been rebuilt since).
So a folder that stops matching is judged against the last night it matched: if neither the site's
file nor the folder's code has changed since then, the only thing that moved is the data the
script downloaded, and the folder is reported as WAITING FOR THE SITE, not as a mismatch. Once the
site rebuilds its file, a difference that remains is a real one and fails the night; a site file
that has not caught up within `site_rebuild_days` (check.json, default 7) fails it too. A changed
script, check.json, input file or shared reader never counts as a revision.

    python tools/check_all.py --compare-only    # judge the outputs already written, rerunning nothing

Exit code: 0 when every compared series matches or is waiting for the site; 1 when any series does
not match, or a script has failed on two runs in a row (one failure is retried and remembered,
since publishers' servers do go down for an hour).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import econdata  # noqa: E402

DEFAULT_STATE = Path.home() / ".cache" / "econvitals-replication" / "check-state.json"


def folders() -> list[Path]:
    found = sorted(p.parent for p in ROOT.glob("measures/*/check.json"))
    found += sorted(p.parent for p in ROOT.glob("simulator/check.json"))
    found += sorted(p.parent for p in ROOT.glob("posts/*/check.json"))
    return found


def script_env(folder: Path, only_for: dict[str, dict[str, str]]) -> dict[str, str]:
    """The environment for one folder's script. A variable given with --script-env reaches only
    the folder it names: every other script runs without it, even if it is set here."""
    env = os.environ.copy()
    for name in {k for v in only_for.values() for k in v}:
        env.pop(name, None)
    env.update(only_for.get(folder.name, {}))
    return env


def run_script(folder: Path, timeout: int, only_for: dict | None = None) -> tuple[bool, str]:
    script = folder / "replicate.py"
    if not script.exists():
        return False, "no replicate.py"
    try:
        p = subprocess.run([sys.executable, str(script)], cwd=folder, capture_output=True,
                           text=True, timeout=timeout, env=script_env(folder, only_for or {}))
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    if p.returncode != 0:
        tail = (p.stderr or p.stdout).strip().splitlines()[-6:]
        return False, "exit %d: %s" % (p.returncode, " | ".join(tail))
    return True, ""


def _norm(v) -> str:
    """Index values compared as text; anything that parses as a date becomes YYYY-MM-DD."""
    s = str(v).strip()
    try:
        if len(s) >= 7 and s[:4].isdigit() and s[4] in "-/":
            return pd.Timestamp(s).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return s


def _dig(obj, dotted: str | None):
    for part in (dotted or "").split("."):
        if part:
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def _glob(obj, parts: list[str], names: tuple = ()):
    """(names, value) for every value at a dotted path whose `*` parts match every key or item."""
    if not parts:
        yield names, obj
        return
    head, rest = parts[0], parts[1:]
    if head == "*":
        if isinstance(obj, dict):
            items = obj.items()
        elif isinstance(obj, list):
            items = ((x.get("k", i) if isinstance(x, dict) else i, x) for i, x in enumerate(obj))
        else:
            return
        for name, sub in items:
            yield from _glob(sub, rest, names + (str(name),))
        return
    try:
        sub = obj[int(head)] if isinstance(obj, list) else obj[head]
    except (KeyError, IndexError, ValueError, TypeError):
        return
    yield from _glob(sub, rest, names)


def published_series(spec: dict) -> pd.Series:
    if spec["published"].startswith("repo:"):
        # A CSV kept in this repository, e.g. "repo:history/pce-tracking.csv" (a track record).
        df = pd.read_csv(ROOT / spec["published"][5:], dtype=str)
        for col, want in (spec.get("published_where") or {}).items():
            df = df[df[col] == str(want)]
        index = spec.get("published_index") or df.columns[0]
        s = pd.Series(pd.to_numeric(df[spec["published_column"]], errors="coerce").values,
                      index=df[index].map(_norm))
        return s.dropna()
    d = econdata.published(spec["published"])
    out = {}
    if spec.get("published_glob"):
        for names, v in _glob(d, spec["published_glob"].split(".")):
            if v is not None and not isinstance(v, (bool, dict, list)):
                try:
                    out[_norm("|".join(names))] = float(v)
                except (TypeError, ValueError):
                    continue
        return pd.Series(out, dtype=float)
    rows = _dig(d, spec.get("published_rows") or "data")
    if spec.get("published_fields"):
        rows = [dict(zip(spec["published_fields"], r)) for r in rows]
    index = spec.get("published_index") or (d.get("date_col") if isinstance(d, dict) else None) or "date"
    fields = index if isinstance(index, list) else [index]
    col = spec["published_column"]
    for r in rows:
        if all(f in r for f in fields) and col in r and r[col] is not None:
            try:
                out[_norm("|".join(str(r[f]) for f in fields))] = float(r[col])
            except (TypeError, ValueError):
                continue
    return pd.Series(out, dtype=float)


def output_series(folder: Path, spec: dict) -> pd.Series:
    df = pd.read_csv(folder / spec["output"], dtype=str)
    index = spec.get("output_index") or df.columns[0]
    col = spec["output_column"]
    s = pd.Series(pd.to_numeric(df[col], errors="coerce").values, index=df[index].map(_norm))
    return s.dropna()


def fingerprint(s: pd.Series) -> str:
    """A short hash of a series' dates and values: the same published file gives the same text."""
    items = sorted((str(k), repr(round(float(v), 10))) for k, v in s.items())
    return hashlib.sha1(json.dumps(items).encode()).hexdigest()[:16]


def code_fingerprint(folder: Path) -> str:
    """What the folder's result depends on besides downloaded data: its scripts, check.json and
    inputs/, and the shared readers in common/. A change to any of them is never a revision."""
    h = hashlib.sha1()
    files = sorted(folder.glob("*.py")) + [folder / "check.json"] + sorted(
        p for p in (folder / "inputs").rglob("*") if p.is_file()) + sorted((ROOT / "common").glob("*.py"))
    for p in files:
        if p.exists():
            h.update(str(p.relative_to(ROOT)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def plain_name(folder: Path) -> str:
    """The measure's name as its README's first heading gives it ("House Prices Relative to Income
    and Rent"), for anything a person reads; the folder name if there is none."""
    readme = folder / "README.md"
    if readme.exists():
        for line in readme.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return folder.name


def _is_date(k: str) -> bool:
    return len(k) == 10 and k[4] == "-" and k[7] == "-" and k[:4].isdigit()


def compare(folder: Path, spec: dict) -> dict:
    ours, theirs = output_series(folder, spec), published_series(spec)
    published_fp = fingerprint(theirs)
    common = [k for k in theirs.index if k in ours.index]
    common.sort()
    if spec.get("from"):       # compare only from this date on (e.g. after a seasonal revision)
        common = [k for k in common if k >= _norm(spec["from"])]
    n = int(spec.get("last_n", 24))
    tol = float(spec.get("tolerance", 0.01))
    label = f"{spec['output_column']} vs {spec['published']}:{spec.get('published_column') or spec.get('published_glob')}"
    if not common and spec.get("may_be_empty") and not len(ours):
        return {"series": label, "ok": True, "empty": True, "published_fp": published_fp,
                "why": spec.get("empty_why", "the script wrote nothing to compare today")}
    if not common:
        return {"series": label, "ok": False, "why": "no dates in common", "published_fp": published_fp,
                "ours_latest": max(ours.index) if len(ours) else None,
                "published_latest": max(theirs.index) if len(theirs) else None}
    window = common[-n:]
    if len(window) < int(spec.get("at_least", 0)):
        return {"series": label, "ok": False, "compared": len(window), "published_fp": published_fp,
                "why": f"only {len(window)} values in common, fewer than the {spec['at_least']} expected"}
    diff = (ours[window] - theirs[window]).abs()
    worst = diff.idxmax()
    ok = bool(diff.max() <= tol + 1e-12)
    out = {"series": label, "ok": ok, "compared": len(window), "tolerance": tol,
           "max_abs_diff": round(float(diff.max()), 6), "worst_at": worst,
           "ours_latest": max(ours.index), "published_latest": max(theirs.index),
           "published_fp": published_fp}
    if not ok and all(_is_date(k) for k in window):
        # Where the difference is, for the morning mail: in the latest values, or only further back.
        recent = window[-3:]
        out["where"] = "latest" if (diff[recent] > tol + 1e-12).any() else "history"
        out["latest_diff"] = round(float(diff[recent].max()), 6)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", help="folder names to run")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--keys-file", help="KEY=value file to take the four API keys from")
    ap.add_argument("--published-dir", help="a local copy of econvitals-data to compare against")
    ap.add_argument("--report", help="write the full result as JSON here")
    ap.add_argument("--state", default=str(DEFAULT_STATE),
                    help="remembers failures between runs (one failure is not an alarm)")
    ap.add_argument("--marker", help="touch this file when the run finishes")
    ap.add_argument("--script-env", action="append", default=[], metavar="FOLDER:NAME=VALUE",
                    help="set NAME=VALUE for that folder's script only (e.g. "
                         "pce-tracking-estimate:X13PATH=/opt/x13); repeatable")
    ap.add_argument("--compare-only", action="store_true",
                    help="judge the outputs already in each folder's output/, rerunning no script")
    ap.add_argument("--today", help=argparse.SUPPRESS)   # YYYY-MM-DD: replay a past night (tests)
    args = ap.parse_args()

    if args.keys_file:
        os.environ["ECONVITALS_KEYS_FILE"] = os.path.expanduser(args.keys_file)
    if args.published_dir:
        os.environ["ECONVITALS_PUBLISHED_DIR"] = os.path.expanduser(args.published_dir)
    econdata._load_keys_file()

    only_for: dict[str, dict[str, str]] = {}
    for item in args.script_env:
        folder, _, pair = item.partition(":")
        name, eq, value = pair.partition("=")
        if not (folder and name and eq):
            ap.error(f"--script-env {item!r}: expected FOLDER:NAME=VALUE")
        only_for.setdefault(folder, {})[name] = value
    todo = [f for f in folders() if not args.only or f.name in args.only]
    if args.list:
        for f in todo:
            c = json.loads((f / "check.json").read_text())
            print(f"{f.name:42} {c.get('status', '?'):22} {len(c.get('compare', []))} series")
        return 0

    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    # Beside the per-folder failure counts: the last night each folder matched (its published
    # fingerprints and code fingerprint), and since when a folder has been waiting for the site.
    matched = state.setdefault("_matched", {})
    waiting = state.setdefault("_waiting_since", {})
    today = args.today or dt.date.today().isoformat()
    results, alarm = [], False
    for f in todo:
        c = json.loads((f / "check.json").read_text())
        rec = {"folder": f.name, "name": plain_name(f), "status": c.get("status")}
        if c.get("status") == "documented" or not c.get("compare"):
            rec["result"] = "NOT COMPARED"
            rec["why"] = c.get("why_not_compared", "no runnable comparison")
            results.append(rec)
            print(f"  --   {f.name}: not compared ({rec['why']})")
            continue
        t0 = time.time()
        if args.compare_only:
            ok, err = True, ""
        else:
            ok, err = run_script(f, int(c.get("timeout_seconds", 900)), only_for)
            if not ok:
                time.sleep(20)
                ok, err = run_script(f, int(c.get("timeout_seconds", 900)), only_for)
        rec["seconds"] = round(time.time() - t0, 1)
        if not ok:
            fails = state.get(f.name, 0) + 1
            state[f.name] = fails
            rec.update(result="SCRIPT FAILED", why=err, failures_in_a_row=fails)
            alarm = alarm or fails >= 2
            results.append(rec)
            print(f"  !!   {f.name}: script failed ({fails} in a row): {err}")
            continue
        if not args.compare_only:
            state[f.name] = 0
        try:
            rec["series"] = [compare(f, s) for s in c["compare"]]
        except Exception as exc:  # a missing column or file is a mismatch, not a crash
            rec["series"] = [{"ok": False, "why": f"{type(exc).__name__}: {exc}"}]
        good = all(s["ok"] for s in rec["series"])
        idle = good and all(s.get("empty") for s in rec["series"])
        published = {s.get("series", ""): s.get("published_fp") for s in rec["series"]}
        code = code_fingerprint(f)
        rec["result"] = "NOT COMPARED TODAY" if idle else "MATCHES" if good else "DOES NOT MATCH"
        if good and not idle:
            matched[f.name] = {"night": today, "code": code, "published": published}
            waiting.pop(f.name, None)
        elif not good:
            last = matched.get(f.name)
            if last and last["code"] == code and last["published"] == published and None not in published.values():
                # Neither the site's file nor this folder's code has changed since the night it
                # last matched: only the downloaded data moved, i.e. an agency revised or added
                # numbers the site has not rebuilt from yet.
                since = waiting.setdefault(f.name, today)
                days = (dt.date.fromisoformat(today) - dt.date.fromisoformat(since)).days
                limit = int(c.get("site_rebuild_days", 7))
                rec["matched_last"] = last["night"]
                rec["waiting_since"] = since
                if days < limit:
                    rec["result"] = "WAITING FOR THE SITE"
                    rec["why"] = (f"the agencies' data changed after econvitals.org last built this file; the file "
                                  f"is unchanged since it matched on {last['night']}")
                else:
                    rec["why"] = (f"econvitals.org has still not rebuilt this file {days} days after the "
                                  f"agencies' data changed (it gets {limit})")
            else:
                waiting.pop(f.name, None)
        alarm = alarm or rec["result"] == "DOES NOT MATCH"
        results.append(rec)
        mark = "--" if idle else "ok" if good else ".." if rec["result"] == "WAITING FOR THE SITE" else "XX"
        print(f"  {mark}   {f.name}: {rec['result']}" + (f" ({rec['why']})" if rec.get("why") else ""))
        for s in rec["series"]:
            if not s["ok"] or len(rec["series"]) == 1:
                detail = (f"nothing to compare today: {s['why']}" if s.get("empty") else s.get("why")
                          or (f"max diff {s['max_abs_diff']} over {s['compared']} "
                              f"dates (tolerance {s['tolerance']})"))
                print(f"         {s.get('series', '')}: {detail}")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, sort_keys=True))
    counts = {}
    for r in results:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    summary = {"ran_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "counts": counts, "alarm": alarm, "results": results}
    print("\n" + ", ".join(f"{v} {k.lower()}" for k, v in sorted(counts.items())))
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=1, default=str))
    if args.marker:
        Path(args.marker).expanduser().parent.mkdir(parents=True, exist_ok=True)
        Path(args.marker).expanduser().touch()
    return 1 if alarm else 0


if __name__ == "__main__":
    sys.exit(main())
