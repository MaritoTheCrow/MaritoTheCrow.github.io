#!/usr/bin/env python3
"""Fail if a gated file (access: contact / subscriber) is staged or tracked in git.

Used by the pre-commit hook (tools/hooks/pre-commit). Rules:
  1. A reports.yml entry with access != free must not have a url.
  2. Anything under assets/reports/ must be registered as a *free* report (its url).
  3. Office files (xlsx, xlsm, xls, docx, doc, pptx, ppt) are only allowed under assets/reports/
     and only if registered as free.
  4. Paths containing gated/, _gated/, private/ or ".gated." are never allowed.

    py tools/check_gated.py --staged   # what is about to be committed (default)
    py tools/check_gated.py --all      # every tracked file
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPORTS_YML = "_data/merval/reports.yml"
OFFICE = {".xlsx", ".xlsm", ".xls", ".docx", ".doc", ".pptx", ".ppt"}
FORBIDDEN = re.compile(r"(^|/)(gated|_gated|private)/|\.gated\.")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout


def load_reports(staged):
    text = git("show", f":{REPORTS_YML}") if staged else ""
    if not text:
        p = ROOT / REPORTS_YML
        text = p.read_text(encoding="utf-8") if p.exists() else ""
    return yaml.safe_load(text) or []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--all", action="store_true")
    args = ap.parse_args()
    staged = not args.all

    reports = load_reports(staged)
    errors = []
    free_urls = set()
    for r in reports:
        url = (r.get("url") or "").lstrip("/")
        if r.get("access", "free") == "free":
            if url and not url.startswith("http"):
                free_urls.add(url)
        elif url:
            errors.append(f"{REPORTS_YML}: {r.get('id')} is '{r.get('access')}' but has a url ({url}). Remove the url.")

    if staged:
        files = git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines()
    else:
        files = git("ls-files").splitlines()

    for f in files:
        suffix = Path(f).suffix.lower()
        if FORBIDDEN.search(f):
            errors.append(f"{f}: path is reserved for gated/private files")
        elif f.startswith("assets/reports/"):
            if Path(f).name == ".gitkeep":
                continue
            if f not in free_urls:
                errors.append(f"{f}: not registered as a free report in reports.yml (gated files must stay out of the repo)")
        elif suffix in OFFICE:
            errors.append(f"{f}: Office files are not allowed in the repo outside assets/reports (could be a gated file)")

    if errors:
        print("GATED-FILE CHECK FAILED:")
        for e in errors:
            print("  -", e)
        print("Unstage with: git restore --staged <file>   (and keep the file outside the repo)")
        return 1
    print(f"Gated-file check OK ({len(files)} file(s) checked, {len(free_urls)} free report file(s) registered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
