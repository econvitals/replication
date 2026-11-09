#!/usr/bin/env python3
"""make_zip.py: write a clean zip of the package, for distribution.

The zip is what `git archive` makes of a commit: the files under version control, less those marked export-ignore in
.gitattributes. So it leaves out the git history, output/, .venv/, caches and the maintainer's to-do file.

    python make_zip.py                       # -> output/data-center-boom-replication.zip, from HEAD
    python make_zip.py --out DIR [--ref REF] # another folder, or another commit or tag

Every file sits under data-center-boom-replication/ in the zip. Needs git and a checkout of the repository. It zips
a commit, never the working tree, so it stops if tracked files have uncommitted changes, and it names any untracked
files it leaves out.
"""
import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "data-center-boom-replication"
NEVER = (".git/", "output/", ".venv/", "__pycache__/", "NEXT.md", "NEXT-ARCHIVE.md", "data_refreshed/", ".DS_Store")


def git(*args):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"make_zip: git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "output"), help="folder to write the zip to (default output/)")
    ap.add_argument("--ref", default="HEAD", help="the commit or tag to zip (default HEAD)")
    a = ap.parse_args()
    git("rev-parse", "--is-inside-work-tree")
    if a.ref == "HEAD":
        dirty = git("status", "--porcelain", "--untracked-files=no").strip()
        if dirty:
            sys.exit("make_zip: tracked files have uncommitted changes; commit them first (the zip is a commit):\n" + dirty)
        untracked = [l[3:] for l in git("status", "--porcelain").splitlines() if l.startswith("?? ")]
        if untracked:
            print("make_zip: not in the zip (untracked): " + ", ".join(untracked))
    commit = git("rev-parse", "--short", a.ref).strip()
    out = Path(a.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    zf = out / f"{NAME}.zip"
    git("archive", "--format=zip", f"--prefix={NAME}/", "-o", str(zf), a.ref)
    with zipfile.ZipFile(zf) as z:
        names = [n[len(NAME) + 1:] for n in z.namelist()]
        bad = [n for n in names if any(n == p or n.startswith(p) or f"/{p}" in f"/{n}" for p in NEVER)]
        if bad:
            zf.unlink()
            sys.exit(f"make_zip: these should not be in the zip: {bad[:10]}")
        nfiles = sum(1 for n in z.namelist() if not n.endswith("/"))
    print(f"make_zip: wrote {zf} ({zf.stat().st_size / 1e6:.1f} MB, {nfiles} files, commit {commit})")


if __name__ == "__main__":
    main()
