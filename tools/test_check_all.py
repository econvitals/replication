"""Tests for the nightly check's revision rule (check_all.py, "A revision alone is not a failure").

    python tools/test_check_all.py          # or: python -m pytest tools/test_check_all.py

Builds a throwaway copy of the checker with one made-up measure and replays nights against it with
--compare-only: a match, an agency revision the site has not rebuilt from (waiting, not a failure),
the site catching up (a match again), a site rebuild that still differs (a failure), a code change
during a revision (a failure), and a site that never catches up (a failure after site_rebuild_days).
No network, no keys.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATES = ["2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01"]


def _layout(tmp: Path) -> Path:
    (tmp / "tools").mkdir()
    shutil.copy(HERE / "check_all.py", tmp / "tools" / "check_all.py")
    shutil.copytree(HERE.parent / "common", tmp / "common", ignore=shutil.ignore_patterns("__pycache__"))
    m = tmp / "measures" / "demo"
    (m / "output").mkdir(parents=True)
    (m / "README.md").write_text("# Demo Measure\n")
    (m / "replicate.py").write_text("print('demo')\n")
    (m / "check.json").write_text(json.dumps({"status": "reproduces", "compare": [
        {"output": "output/demo.csv", "output_column": "v", "published": "data/demo.json",
         "published_column": "v", "last_n": 10, "tolerance": 0.001}]}))
    (tmp / "pub" / "data").mkdir(parents=True)
    return m


def _ours(m: Path, vals):
    (m / "output" / "demo.csv").write_text("date,v\n" + "".join(f"{d},{v}\n" for d, v in zip(DATES, vals)))


def _site(tmp: Path, vals):
    (tmp / "pub" / "data" / "demo.json").write_text(json.dumps(
        {"data": [{"date": d, "v": v} for d, v in zip(DATES, vals)]}))


def _night(tmp: Path, today: str, state: str = "state.json"):
    p = subprocess.run([sys.executable, str(tmp / "tools" / "check_all.py"), "--compare-only",
                        "--today", today, "--published-dir", str(tmp / "pub"),
                        "--state", str(tmp / state), "--report", str(tmp / "report.json")],
                       capture_output=True, text=True, cwd=tmp)
    rep = json.loads((tmp / "report.json").read_text())["results"][0]
    return p.returncode, rep["result"], rep


def test_revision_rule():
    old, new = [1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.1, 4.2]
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        m = _layout(tmp)
        _ours(m, old); _site(tmp, old)
        assert _night(tmp, "2026-11-24")[:2] == (0, "MATCHES")
        shutil.copy(tmp / "state.json", tmp / "after_match.json")

        # The agency revises; the site's file is unchanged since the match: waiting, not a failure.
        _ours(m, new)
        rc, res, rep = _night(tmp, "2026-11-25")
        assert (rc, res) == (0, "WAITING FOR THE SITE"), rep
        assert rep["name"] == "Demo Measure" and rep["matched_last"] == "2026-11-24"
        assert rep["series"][0]["where"] == "latest"
        shutil.copy(tmp / "state.json", tmp / "waiting.json")

        # Still waiting six days on; failing once the site has had seven days to catch up.
        shutil.copy(tmp / "waiting.json", tmp / "s6.json")
        assert _night(tmp, "2026-12-01", "s6.json")[:2] == (0, "WAITING FOR THE SITE")
        shutil.copy(tmp / "waiting.json", tmp / "s7.json")
        rc, res, rep = _night(tmp, "2026-12-02", "s7.json")
        assert (rc, res) == (1, "DOES NOT MATCH") and "7 days" in rep["why"], rep

        # The site rebuilds on the new data: a match again.
        _site(tmp, new)
        assert _night(tmp, "2026-11-26")[:2] == (0, "MATCHES")
        assert "demo" not in json.loads((tmp / "state.json").read_text())["_waiting_since"]

        # The site rebuilds but disagrees with the script: a real divergence, a failure.
        _site(tmp, [1.0, 2.0, 3.1, 4.5])
        assert _night(tmp, "2026-11-27")[:2] == (1, "DOES NOT MATCH")

        # A changed script never counts as a revision, even with the site's file unchanged.
        _site(tmp, old); _ours(m, new)
        shutil.copy(tmp / "after_match.json", tmp / "code.json")
        (m / "replicate.py").write_text("print('demo, changed')\n")
        assert _night(tmp, "2026-11-25", "code.json")[:2] == (1, "DOES NOT MATCH")

        # A difference only further back is reported as history, not the latest values.
        (m / "replicate.py").write_text("print('demo')\n")
        _ours(m, [1.5, 2.0, 3.0, 4.0]); _site(tmp, old)
        rep = _night(tmp, "2026-11-28", "fresh.json")[2]
        assert rep["series"][0]["where"] == "history", rep


def test_text_and_shared_path():
    """A `published` path given once at the top of check.json serves every series that names none, and a
    `text` series compares words exactly (a nested data file, read with published_glob)."""
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        m = _layout(tmp)
        (m / "check.json").write_text(json.dumps({"status": "reproduces", "published": "data/nested.json", "compare": [
            {"output": "output/kinds.csv", "output_index": "key", "output_column": "kind", "text": True,
             "published_glob": "rows.*.alarms.*.kind", "last_n": 100, "at_least": 3},
            {"output": "output/kinds.csv", "output_index": "key", "output_column": "n",
             "published_glob": "rows.*.alarms.*.n", "last_n": 100, "at_least": 3, "tolerance": 0}]}))
        site = {"rows": [{"id": "a", "alarms": [{"kind": "hit", "n": 3}, {"kind": "false", "n": 1}]},
                         {"id": "b", "alarms": [{"kind": "late", "n": 7}]}]}
        (tmp / "pub" / "data" / "nested.json").write_text(json.dumps(site))
        (m / "output" / "kinds.csv").write_text("key,kind,n\n0|0,hit,3\n0|1,false,1\n1|0,late,7\n")
        assert _night(tmp, "2026-11-28")[:2] == (0, "MATCHES")
        (m / "output" / "kinds.csv").write_text("key,kind,n\n0|0,hit,3\n0|1,open,1\n1|0,late,7\n")
        rc, res, rep = _night(tmp, "2026-11-29", "fresh.json")
        assert (rc, res) == (1, "DOES NOT MATCH") and "'open' here, 'false' on the site" in rep["series"][0]["why"], rep
        assert rep["series"][1]["ok"]


if __name__ == "__main__":
    test_revision_rule()
    print("PASS test_revision_rule")
    test_text_and_shared_path()
    print("PASS test_text_and_shared_path")
