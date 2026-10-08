#!/usr/bin/env python3
"""Add or update reports in _data/merval/reports.yml.

TWO WAYS TO FEED IT

1) Release-folder mode (recommended): point it at an "Informes" batch folder
       py tools/add_reports.py --source "D:\\...\\01 Valuations\\01. AGRO - Agrometal\\02. Informes\\1. 10_2026" [--dry-run]
   Folder convention:
       01. Capital Markets\\01 Valuations\\<NN>. <TICKER> - <Company>\\02. Informes\\<N>. <MM>_<YYYY>\\
   * ticker  <- the folder "01. AGRO - Agrometal"      -> AGRO
   * batch   <- the folder "1. 10_2026"                -> 2026-10  (stored as batch: '2026-10')
   * date    <- a date in the file name (2026-10-07 / 20261007) if any, else the file's modified date
   * type    <- guessed from the file name and format (initiation, update, valuation_model,
                financial_data, presentation, note); override in the CSV
   The source folder is only READ (never moved, renamed or modified). Sub-folders are included;
   temporary files (~$*, *.tmp, Thumbs.db, desktop.ini) are ignored.

2) File-naming mode (still supported): a folder of files named <TICKER>_<YYYY-MM-DD>_<type>.<ext>
       py tools/add_reports.py FOLDER [--csv overrides.csv] [--dry-run]

DEFAULT ACCESS (when the CSV does not say otherwise)
   --source mode:  pdf -> free | docx, pptx -> contact | xlsx and anything else -> subscriber
   naming mode:    --default-access (default subscriber)
   free        file is copied byte-for-byte into assets/reports/<TICKER>/<date>_<TICKER>_<type>.<ext>
   contact     metadata only; the file is NEVER copied into the repo
   subscriber  metadata only; the file is NEVER copied into the repo

OPTIONAL CSV (UTF-8, header row; only filename required):
   filename, type, date, access, title_en, title_es, summary_en, summary_es,
   rating, target_price, currency, language, batch
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
ICON_FORMATS = {"pdf", "xlsx", "docx", "pptx"}
NAMING_FORMATS = ICON_FORMATS
ACCESS = {"free", "contact", "subscriber"}
LANGS = {"en", "es", "both"}
LARGE = 50 * 1024 * 1024
IGNORE = re.compile(r"^(~\$.*|.*\.tmp|thumbs\.db|desktop\.ini|\.ds_store)$", re.I)

NAME_RE = re.compile(r"^(?P<ticker>[A-Za-z0-9]+)_(?P<date>\d{4}-\d{2}-\d{2})_(?P<type>[A-Za-z_]+)\.(?P<ext>[A-Za-z]+)$")
TICKER_DIR_RE = re.compile(r"^\s*\d+\.\s*([A-Za-z0-9]+)\s*-\s*(.+?)\s*$")
BATCH_DIR_RE = re.compile(r"^\s*\d+\.\s*(\d{1,2})_(\d{4})\s*$")
DATE_IN_NAME = re.compile(r"(?<!\d)(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)")
HEADER = (
    "# One entry per document. Managed by tools/add_reports.py (you can also edit by hand).\n"
    "# access: free | contact | subscriber.  Only \"free\" entries may have a url.\n"
    "# size_bytes: file size in bytes.  language: en | es | both.\n"
    "# batch: release folder (YYYY-MM) the file came from.\n"
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


# ---------------------------------------------------------------- release-folder helpers
def detect_ticker_batch(source: Path):
    """Walk the path upwards: batch from '<N>. <MM>_<YYYY>', ticker from '<NN>. <TICKER> - <Company>'."""
    ticker = company = batch = None
    for part in [source.name] + [p.name for p in source.parents]:
        if batch is None:
            m = BATCH_DIR_RE.match(part)
            if m:
                batch = f"{m.group(2)}-{int(m.group(1)):02d}"
                continue
        if ticker is None:
            m = TICKER_DIR_RE.match(part)
            if m and m.group(1).upper() == m.group(1):
                ticker, company = m.group(1).upper(), m.group(2)
    return ticker, company, batch


def guess_type(name, ext):
    n = re.sub(r"[^a-z0-9]+", " ", name.lower())
    if re.search(r"initiation|inicio|iniciacion", n):
        return "initiation"
    if ext == "pptx" or re.search(r"presentation|presentacion|slides", n):
        return "presentation"
    if re.search(r"financ|balance|estados|datos|statements", n):
        return "financial_data"
    if re.search(r"model|valuac|valuation|dcf", n):
        return "valuation_model"
    if re.search(r"update|actualiz", n):
        return "update"
    return "note"


def guess_language(name):
    n = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return "es" if re.search(r"valuacion|informe|inicio|estados|balance|actualiz|presentacion", n) else "en"


def default_access(ext):
    if ext == "pdf":
        return "free"
    if ext in ("docx", "pptx"):
        return "contact"
    return "subscriber"


def file_date(src, ov):
    """Return (date_iso, how)."""
    if ov.get("date"):
        return ov["date"], "csv"
    m = DATE_IN_NAME.search(src.stem)
    if m:
        try:
            d = datetime.date(int(m[1]), int(m[2]), int(m[3]))
            return d.isoformat(), "file name"
        except ValueError:
            pass
    return datetime.datetime.fromtimestamp(src.stat().st_mtime).date().isoformat(), "modified date"


def collect_source(source, tickers, overrides, errors):
    ticker, company, batch = detect_ticker_batch(source)
    if not ticker:
        errors.append(f"{source}: cannot detect the ticker from the path (expected a folder like '01. AGRO - Agrometal')")
        return []
    if ticker not in tickers:
        errors.append(f"{source}: ticker {ticker} is not in tickers.yml")
        return []
    print(f"Source: {source}\n  ticker = {ticker} ({company}); batch = {batch or '(none detected)'}")
    items = []
    for src in sorted(p for p in source.rglob("*") if p.is_file() and not IGNORE.match(p.name) and p.suffix.lower() != ".csv"):
        ext = src.suffix.lower().lstrip(".")
        ov = overrides.get(src.name, {})
        date, how = file_date(src, ov)
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            errors.append(f"{src.name}: invalid date {date}")
            continue
        rtype = (ov.get("type") or guess_type(src.stem, ext)).lower()
        if rtype not in TYPES:
            errors.append(f"{src.name}: unknown type '{rtype}'")
            continue
        items.append(dict(src=src, ticker=ticker, date=date, date_how=how, type=rtype, ext=ext, ov=ov,
                          batch=ov.get("batch") or batch, auto_access=default_access(ext),
                          auto_lang=guess_language(src.stem), shown=str(src.relative_to(source))))
    return items


def collect_naming(folder, tickers, overrides, errors, default_acc, default_lang):
    items = []
    for src in sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() != ".csv" and not IGNORE.match(p.name)):
        m = NAME_RE.match(src.name)
        if not m:
            errors.append(f"{src.name}: name does not match <TICKER>_<YYYY-MM-DD>_<type>.<ext>")
            continue
        ticker, rtype, ext, date = m["ticker"].upper(), m["type"].lower(), m["ext"].lower(), m["date"]
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
        if ext not in NAMING_FORMATS:
            errors.append(f"{src.name}: unsupported format .{ext} (use: {', '.join(sorted(NAMING_FORMATS))})")
            continue
        ov = overrides.get(src.name, {})
        items.append(dict(src=src, ticker=ticker, date=date, date_how="file name", type=rtype, ext=ext, ov=ov,
                          batch=ov.get("batch"), auto_access=default_acc, auto_lang=default_lang, shown=src.name))
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", help="naming mode: folder of <TICKER>_<date>_<type>.<ext> files")
    ap.add_argument("--source", help="release-folder mode: an 'Informes' batch folder, e.g. '...\\01. AGRO - Agrometal\\02. Informes\\1. 10_2026'")
    ap.add_argument("--csv", help="CSV with per-file overrides")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen, change nothing")
    ap.add_argument("--default-access", default="subscriber", choices=sorted(ACCESS), help="naming mode only")
    ap.add_argument("--language", default="en", choices=sorted(LANGS), help="naming mode: default language")
    ap.add_argument("--currency", default="ARS")
    args = ap.parse_args()

    if bool(args.folder) == bool(args.source):
        ap.error("give exactly one of: FOLDER (naming mode) or --source (release-folder mode)")
    folder = Path(args.source or args.folder)
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a folder")
        return 2

    tickers = {t["ticker"].upper(): t for t in (yaml.safe_load(TICKERS_YML.read_text(encoding="utf-8")) or [])}
    overrides = load_csv(args.csv)
    reports = load_reports()
    by_id = {r["id"]: r for r in reports}
    errors, warnings, plan = [], [], []

    if args.source:
        items = collect_source(folder, tickers, overrides, errors)
    else:
        items = collect_naming(folder, tickers, overrides, errors, args.default_access, args.language)

    for it in items:
        src, ticker, rtype, ext, date, ov = it["src"], it["ticker"], it["type"], it["ext"], it["date"], it["ov"]
        access = (ov.get("access") or "").lower()
        if access and access not in ACCESS:
            errors.append(f"{src.name}: invalid access '{access}' in CSV")
            continue
        rid = f"{ticker.lower()}-{date}-{rtype.replace('_', '-')}-{ext}"
        old = by_id.get(rid)
        access = access or (old or {}).get("access") or it["auto_access"]
        size = src.stat().st_size
        entry = dict(old) if old else {}
        entry.update({"id": rid, "ticker": ticker, "type": rtype, "date": date, "format": ext,
                      "size_bytes": size, "access": access})
        lang = ov.get("language") or entry.get("language") or it["auto_lang"]
        if lang not in LANGS:
            errors.append(f"{src.name}: invalid language '{lang}'")
            continue
        entry["language"] = lang
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
        entry["currency"] = ov.get("currency") or entry.get("currency") or args.currency
        if it["batch"]:
            entry["batch"] = it["batch"]
        entry.pop("pending", None)

        rel = f"{ticker}/{date}_{ticker}_{rtype}.{ext}"
        dest = REPORTS_DIR / rel
        action = "update" if old else "add"
        if old and old.get("pending"):
            action = "fill"

        if access == "free":
            if size > LARGE:
                warnings.append(f"{src.name}: {fmt_bytes(size)} is over 50 MB; NOT copied. Host it elsewhere and set "
                                f"'url' to the external link in reports.yml (entry marked pending until then).")
                entry["pending"] = True
                entry.pop("url", None)
                plan.append((action, src, None, entry, it))
                continue
            entry["url"] = f"/assets/reports/{rel}"
            plan.append((action, src, dest, entry, it))
        else:
            if (old or {}).get("url") or dest.exists():
                warnings.append(f"{src.name}: access is now '{access}' but a public copy exists "
                                f"(assets/reports/{rel}). Remove it with: git rm \"assets/reports/{rel}\"")
            entry.pop("url", None)
            plan.append((action, src, None, entry, it))

    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("WARNING:", w)

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}PLAN")
    for action, src, dest, entry, it in plan:
        where = f"COPY -> assets/reports/{dest.relative_to(REPORTS_DIR).as_posix()}" if dest else "metadata only (not copied)"
        print(f"  {action:6} {it['shown']}\n         id={entry['id']}  type={entry['type']}  date={entry['date']} (from {it['date_how']})  "
              f"access={entry['access']}  {entry['format']}  {fmt_bytes(entry['size_bytes'])}  lang={entry['language']}  "
              f"batch={entry.get('batch', '-')}\n         {where}")

    if not args.dry_run:
        for action, src, dest, entry, it in plan:
            if dest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)  # byte-for-byte; the source is only read
                a, b = sha256(src), sha256(dest)
                print(f"  verify {dest.name}: sha256 {a[:16]}… {'IDENTICAL' if a == b else 'MISMATCH'}")
                if a != b:
                    dest.unlink()
                    print(f"ERROR: checksum mismatch copying {src.name}; copy removed")
                    return 1
            by_id[entry["id"]] = entry
        save_reports(list(by_id.values()))

    pack, loose, rep = repo_size()
    print(f"\n{prefix}Done: {len(plan)} file(s) processed, {len(errors)} error(s), {len(warnings)} warning(s).")
    print(f"Repo size: git pack {pack}, loose {loose}; assets/reports {fmt_bytes(rep)}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
