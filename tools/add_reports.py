#!/usr/bin/env python3
"""Add or update reports in _data/merval/reports.yml from a folder of files.

File names must follow:  <TICKER>_<YYYY-MM-DD>_<type>.<ext>
    e.g.  AGRO_2026-01-30_initiation.pdf     ALUA_2026-03-02_valuation_model.xlsx
    type: initiation | update | valuation_model | financial_data | presentation | note
    ext : pdf | xlsx | docx | pptx

Access levels:
    free        file is copied byte-for-byte into assets/reports/<TICKER>/ (public on the web)
    contact     metadata only; the file is NEVER copied into the repo
    subscriber  metadata only; the file is NEVER copied into the repo
Files without an access override get --default-access (default: subscriber, the safe choice).

Optional CSV (UTF-8) with a header row. Columns (all optional except filename):
    filename, title_en, title_es, access, summary_en, summary_es,
    rating, target_price, currency, language

Usage:
    py tools/add_reports.py FOLDER [--csv overrides.csv] [--dry-run]
The source files are only read, never modified or moved.
"""
import argparse
import csv
import datetime
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TICKERS_YML = ROOT / "_data" / "merval" / "tickers.yml"
REPORTS_YML = ROOT / "_data" / "merval" / "reports.yml"
REPORTS_DIR = ROOT / "assets" / "reports"

TYPES = {
    "initiation": ("Initiation report", "Informe de inicio de cobertura"),
    "update": ("Update", "Actualización"),
    "valuation_model": ("Valuation model", "Modelo de valuación"),
    "financial_data": ("Financial data", "Datos financieros"),
    "presentation": ("Presentation", "Presentación"),
    "note": ("Note", "Nota"),
}
FORMATS = {"pdf", "xlsx", "docx", "pptx"}
ACCESS = {"free", "contact", "subscriber"}
LANGS = {"en", "es", "both"}
LARGE = 50 * 1024 * 1024

NAME_RE = re.compile(r"^(?P<ticker>[A-Za-z0-9]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<type>[A-Za-z_]+)\.(?P<ext>[A-Za-z]+)$")
HEADER = (
    "# One entry per document. Managed by tools/add_reports.py (you can also edit by hand).\n"
    "# access: free | contact | subscriber.  Only \"free\" entries may have a url.\n"
    "# size_bytes: file size in bytes.  language: en | es | both.\n"
    "# pending: true marks an entry whose file has not been provided yet.\n"
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_reports():
    if not REPORTS_YML.exists():
        return []
    return yaml.safe_load(REPORTS_YML.read_text(encoding="utf-8")) or []


def save_reports(reports):
    reports = sorted(reports, key=lambda r: (r["date"], r["ticker"], r["id"]), reverse=True)
    body = yaml.safe_dump(reports, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    REPORTS_YML.write_text(HEADER + (body if reports else "[]\n"), encoding="utf-8", newline="\n")


def load_csv(path):
    rows = {}
    if not path:
        return rows
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("filename") or "").strip()
            if name:
                rows[name] = {k.strip(): (v or "").strip() for k, v in row.items() if k}
    return rows


def repo_size():
    out = subprocess.run(["git", "count-objects", "-vH"], cwd=ROOT, capture_output=True, text=True).stdout
    info = dict(line.split(": ", 1) for line in out.splitlines() if ": " in line)
    rep_bytes = sum(p.stat().st_size for p in REPORTS_DIR.rglob("*") if p.is_file()) if REPORTS_DIR.exists() else 0
    return info.get("size-pack", "?"), info.get("size", "?"), rep_bytes


def fmt_bytes(n):
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.1f} KB"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder containing the files to add")
    ap.add_argument("--csv", help="CSV with per-file overrides")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ap.add_argument("--default-access", default="subscriber", choices=sorted(ACCESS))
    ap.add_argument("--language", default="en", choices=sorted(LANGS), help="default language of the documents")
    ap.add_argument("--currency", default="ARS")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a folder")
        return 2

    tickers = {t["ticker"].upper(): t for t in (yaml.safe_load(TICKERS_YML.read_text(encoding="utf-8")) or [])}
    overrides = load_csv(args.csv)
    reports = load_reports()
    by_id = {r["id"]: r for r in reports}
    errors, warnings, plan = [], [], []

    for src in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() != ".csv"):
        m = NAME_RE.match(src.name)
        if not m:
            errors.append(f"{src.name}: name does not match <TICKER>_<YYYY-MM-DD>_<type>.<ext>")
            continue
        ticker = m["ticker"].upper()
        rtype = m["type"].lower()
        ext = m["ext"].lower()
        date = m["date"]
        if ticker not in tickers:
            errors.append(f"{src.name}: ticker {ticker} is not in tickers.yml")
            continue
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            errors.append(f"{src.name}: invalid date {date}")
            continue
        if rtype not in TYPES:
            errors.append(f"{src.name}: unknown type '{rtype}' (use: {', '.join(TYPES)})")
            continue
        if ext not in FORMATS:
            errors.append(f"{src.name}: unsupported format .{ext} (use: {', '.join(sorted(FORMATS))})")
            continue
        ov = overrides.get(src.name, {})
        access = (ov.get("access") or "").lower()
        if access and access not in ACCESS:
            errors.append(f"{src.name}: invalid access '{access}' in CSV")
            continue

        rid = f"{ticker.lower()}-{date}-{rtype.replace('_', '-')}-{ext}"
        old = by_id.get(rid)
        access = access or (old or {}).get("access") or args.default_access
        size = src.stat().st_size
        entry = dict(old) if old else {}
        entry.update({"id": rid, "ticker": ticker, "type": rtype, "date": date, "format": ext,
                      "size_bytes": size, "access": access})
        entry.setdefault("language", ov.get("language") or args.language)
        if ov.get("language"):
            entry["language"] = ov["language"]
        label = TYPES[rtype]
        title = dict(entry.get("title") or {})
        title["en"] = ov.get("title_en") or title.get("en") or f"{ticker} – {label[0]} ({ext.upper()})"
        title["es"] = ov.get("title_es") or title.get("es") or f"{ticker} – {label[1]} ({ext.upper()})"
        entry["title"] = title
        summary = dict(entry.get("summary") or {})
        if ov.get("summary_en"):
            summary["en"] = ov["summary_en"]
        if ov.get("summary_es"):
            summary["es"] = ov["summary_es"]
        if summary:
            entry["summary"] = summary
        if ov.get("rating"):
            entry["rating"] = ov["rating"]
        if ov.get("target_price"):
            entry["target_price"] = float(ov["target_price"].replace(",", "."))
        entry.setdefault("currency", ov.get("currency") or args.currency)
        if ov.get("currency"):
            entry["currency"] = ov["currency"]
        entry.pop("pending", None)

        rel = f"{ticker}/{date}_{ticker}_{rtype}.{ext}"
        dest = REPORTS_DIR / rel
        action = "update" if old else "add"

        if access == "free":
            if size > LARGE:
                warnings.append(f"{src.name}: {fmt_bytes(size)} is over 50 MB; NOT copied. Host it elsewhere and set "
                                f"'url' to the external link in reports.yml (entry marked pending until then).")
                entry["pending"] = True
                entry.pop("url", None)
                plan.append((action, src, None, entry))
                continue
            entry["url"] = f"/assets/reports/{rel}"
            plan.append((action, src, dest, entry))
        else:
            if (old or {}).get("url") or dest.exists():
                warnings.append(f"{src.name}: access is now '{access}' but a public copy exists "
                                f"(assets/reports/{rel}). Remove it with: git rm \"assets/reports/{rel}\"")
            entry.pop("url", None)
            plan.append((action, src, None, entry))

    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("WARNING:", w)

    prefix = "[dry-run] " if args.dry_run else ""
    for action, src, dest, entry in plan:
        where = f"copy -> assets/reports/{dest.relative_to(REPORTS_DIR).as_posix()}" if dest else "metadata only (file not copied)"
        print(f"{prefix}{action:6} {entry['id']}  [{entry['access']}]  {fmt_bytes(entry['size_bytes'])}  {where}")

    if not args.dry_run:
        for action, src, dest, entry in plan:
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)  # byte-for-byte, keeps timestamps; source untouched
                if sha256(src) != sha256(dest):
                    print(f"ERROR: checksum mismatch copying {src.name}")
                    return 1
            by_id[entry["id"]] = entry
        save_reports(list(by_id.values()))

    pack, loose, rep = repo_size()
    print(f"{prefix}Done: {len(plan)} file(s) processed, {len(errors)} error(s), {len(warnings)} warning(s).")
    print(f"Repo size: git pack {pack}, loose {loose}; assets/reports {fmt_bytes(rep)}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
