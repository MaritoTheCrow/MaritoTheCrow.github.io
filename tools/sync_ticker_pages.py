#!/usr/bin/env python3
"""Create / update / remove the per-ticker page stubs from _data/merval/tickers.yml.

GitHub Pages cannot run custom Jekyll plugins, so each ticker gets a tiny stub file
(front matter only) in two Jekyll collections:

    _merval/<ticker>.md      ->  /valuations/merval/<ticker>/
    _merval_es/<ticker>.md   ->  /es/valuations/merval/<ticker>/

The page content comes from _layouts/ticker.html. Run this after editing tickers.yml.

    py tools/sync_ticker_pages.py          # write the stubs
    py tools/sync_ticker_pages.py --check  # only verify they are in sync (exit 1 if not)
"""
import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TICKERS = ROOT / "_data" / "merval" / "tickers.yml"
DIRS = {"en": ROOT / "_merval", "es": ROOT / "_merval_es"}


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(t, lang):
    name = t["company"]
    sector = t["sector"][lang]
    desc = t["description"][lang]
    if lang == "es":
        meta = f"{name} ({t['ticker']}), {sector}. {desc} Investigación independiente de MCB Advisor."
    else:
        meta = f"{name} ({t['ticker']}), {sector}. {desc} Independent equity research by MCB Advisor."
    return (
        "---\n"
        f"ticker: {t['ticker']}\n"
        f"title: {q('MCB Advisor | ' + t['ticker'] + ' – ' + name)}\n"
        f"description: {q(meta)}\n"
        "---\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 if out of sync")
    args = ap.parse_args()

    tickers = yaml.safe_load(TICKERS.read_text(encoding="utf-8")) or []
    expected = {}
    for t in tickers:
        for lang, d in DIRS.items():
            expected[d / (t["ticker"].lower() + ".md")] = render(t, lang)

    problems = []
    for path, text in expected.items():
        if not path.exists():
            problems.append(("missing", path))
        elif path.read_text(encoding="utf-8") != text:
            problems.append(("outdated", path))
    for d in DIRS.values():
        if d.exists():
            for p in d.glob("*.md"):
                if p not in expected:
                    problems.append(("orphan", p))

    if args.check:
        for kind, p in problems:
            print(f"{kind}: {p.relative_to(ROOT)}")
        if problems:
            print("Ticker pages are out of sync. Run: py tools/sync_ticker_pages.py")
            return 1
        print(f"Ticker pages in sync ({len(tickers)} tickers x 2 languages).")
        return 0

    for kind, p in problems:
        if kind == "orphan":
            p.unlink()
            print(f"removed {p.relative_to(ROOT)}")
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(expected[p], encoding="utf-8", newline="\n")
            print(f"{'created' if kind == 'missing' else 'updated'} {p.relative_to(ROOT)}")
    print(f"Done: {len(tickers)} tickers x 2 languages, {len(problems)} change(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
