#!/usr/bin/env python3
"""Check the built site (_site/) for broken internal links/anchors/assets and EN/ES parity.

    bundle exec jekyll build
    py tools/check_site.py
"""
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
HOSTS = {"mcbadvisor.com", "www.mcbadvisor.com", "maritothecrow.github.io"}
SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.refs = []  # (tag, attr, value)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for attr in ("href", "src", "data-src"):
            if a.get(attr) and not (tag == "link" and a.get("rel") in ("preconnect",)):
                self.refs.append((tag, attr, a[attr]))


def parse(path):
    p = Page()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p


def resolve(url_path):
    """Map a site path to a file in _site, GitHub Pages style."""
    rel = unquote(url_path).lstrip("/")
    cands = []
    if rel == "" or rel.endswith("/"):
        cands.append(SITE / rel / "index.html")
    else:
        cands += [SITE / rel, SITE / (rel + ".html"), SITE / rel / "index.html"]
    for c in cands:
        if c.is_file():
            return c
    return None


def main():
    if not SITE.exists():
        print("_site/ not found. Run: bundle exec jekyll build")
        return 2
    pages = {p: parse(p) for p in SITE.rglob("*.html")}
    broken = []
    for page, info in pages.items():
        here = "/" + page.relative_to(SITE).as_posix()
        for tag, attr, val in info.refs:
            val = val.strip()
            if not val or val.startswith(SKIP_SCHEMES):
                continue
            u = urlsplit(val)
            if u.scheme in ("http", "https"):
                if u.netloc not in HOSTS:
                    continue
            elif u.netloc:
                continue
            path = u.path
            if not path:  # same-page fragment
                target = page
            else:
                if not path.startswith("/"):
                    base = here.rsplit("/", 1)[0]
                    path = base + "/" + path
                target = resolve(path)
                if target is None:
                    broken.append((here, val, "missing target"))
                    continue
            if u.fragment and target.suffix == ".html":
                ids = pages.get(target).ids if target in pages else parse(target).ids
                if unquote(u.fragment) not in ids:
                    broken.append((here, val, "missing anchor"))

    # EN/ES parity
    en, es = set(), set()
    for page in pages:
        rel = page.relative_to(SITE).as_posix()
        if rel.startswith("es/"):
            es.add(rel[3:])
        elif not rel.startswith(("assets/", "404")):
            en.add(rel)
    # stub pages without a counterpart by design
    missing_es = sorted(en - es)
    missing_en = sorted(es - en)

    print(f"Pages checked: {len(pages)}  (EN {len(en)}, ES {len(es)})")
    for b in broken:
        print("BROKEN:", *b)
    for m in missing_es:
        print("EN page without ES version:", m)
    for m in missing_en:
        print("ES page without EN version:", m)
    ok = not (broken or missing_es or missing_en)
    print("Link/anchor/parity check:", "CLEAN" if ok else "PROBLEMS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
