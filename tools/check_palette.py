#!/usr/bin/env python3
"""Check that no color value exists outside the locked palette (the --mcb-* variables in style.css).

Scans style.css (everything outside the :root palette block), inline style attributes / <style> blocks /
SVG color attributes in layouts, includes and pages, and the JavaScript files.
Exit 1 if any color literal is not one of the palette values.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "css" / "style.css"

NAMED = {"white", "black", "red", "blue", "green", "yellow", "orange", "purple", "gray", "grey", "silver", "navy",
         "maroon", "crimson", "pink", "brown", "teal", "cyan", "magenta", "gold", "lime", "olive", "aqua"}
HEX = re.compile(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\(([^()]|\([^()]*\))*\)")


def norm(v):
    return re.sub(r"\s+", "", v.lower())


def rgb_forms(r, g, b):
    return {f"rgb({r},{g},{b})", "#%02x%02x%02x" % (r, g, b)}


def palette(css_text):
    m = re.search(r":root\s*\{(.*?)\n\}", css_text, re.S)
    block = m.group(1)
    allowed = set()
    for name, val in re.findall(r"--(mcb-[\w-]+)\s*:\s*([^;]+);", block):
        val = re.sub(r"/\*.*?\*/", "", val).strip()
        if name.endswith("-rgb"):
            r, g, b = [int(x) for x in val.split(",")]
            allowed |= rgb_forms(r, g, b)
        else:
            allowed.add(norm(val))
            mm = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", val)
            if mm:
                allowed |= rgb_forms(*[int(x) for x in mm.groups()])
            if re.match(r"#[0-9a-fA-F]{3}$", val):
                h = val[1:]
                allowed.add("#" + "".join(c * 2 for c in h).lower())
    # short form of #fff
    allowed |= {"#fff", "#ffffff"}
    return allowed, block, m.span()


def check_values(text, allowed, where, errors, strip_vars=True):
    for mm in FUNC.finditer(text):
        s = mm.group(0)
        if "var(" in s:
            continue  # rgba(var(--mcb-...-rgb), a): palette variable with opacity
        n = norm(s)
        m2 = re.match(r"rgba\((\d+),(\d+),(\d+),[\d.]+\)", n)
        base = "rgb(%s,%s,%s)" % m2.groups() if m2 else n
        if base not in allowed:
            errors.append(f"{where}: {s}")
    for mm in HEX.finditer(FUNC.sub("", text)):
        if norm(mm.group(0)) not in allowed:
            errors.append(f"{where}: {mm.group(0)}")


def main():
    css = CSS.read_text(encoding="utf-8")
    allowed, block, (s, e) = palette(css)
    errors = []

    # 1. CSS outside :root: no literal colors at all (only var(--mcb-*))
    outside = css[:s] + css[e:]
    outside = re.sub(r"/\*.*?\*/", "", outside, flags=re.S)
    for mm in FUNC.finditer(outside):
        if "var(" not in mm.group(0):
            errors.append(f"style.css: literal {mm.group(0)}")
    for mm in HEX.finditer(re.sub(r"url\([^)]*\)", "", outside)):
        errors.append(f"style.css: literal {mm.group(0)}")
    for decl in re.findall(r"(?:color|background(?:-color)?|border[\w-]*|outline[\w-]*|fill|stroke|box-shadow|text-shadow)\s*:\s*([^;{}]+);", outside):
        for tok in re.findall(r"[a-zA-Z]+", re.sub(r"var\([^)]*\)", "", decl)):
            if tok.lower() in NAMED:
                errors.append(f"style.css: named color '{tok}' in '{decl.strip()}'")

    # 2. HTML/MD: style attributes, <style> blocks, svg color attributes, theme-color
    for p in list(ROOT.glob("_layouts/*.html")) + list(ROOT.glob("_includes/**/*.html")) + \
            [q for q in ROOT.glob("*.md")] + [q for q in ROOT.glob("es/**/*.md")] + [q for q in ROOT.glob("valuations/**/*.md")]:
        text = p.read_text(encoding="utf-8")
        chunks = re.findall(r'style="([^"]*)"', text) + re.findall(r"<style[^>]*>(.*?)</style>", text, re.S) + \
            re.findall(r'(?:fill|stroke|stop-color|flood-color)="([^"]*)"', text) + \
            re.findall(r'name="theme-color"\s+content="([^"]*)"', text)
        for c in chunks:
            if c.strip() in ("none", "currentColor", "transparent", "inherit"):
                continue
            check_values(c, allowed, p.relative_to(ROOT).as_posix(), errors)

    # 3. JS
    for p in ROOT.glob("assets/js/*.js"):
        text = p.read_text(encoding="utf-8")
        for mm in re.finditer(r"""(['"])(#[0-9a-fA-F]{3,8}|(?:rgba?|hsla?)\([^'"]*\))\1""", text):
            check_values(mm.group(2), allowed, p.relative_to(ROOT).as_posix(), errors)

    if errors:
        print("PALETTE CHECK FAILED: colors outside the locked palette:")
        for e_ in sorted(set(errors)):
            print("  -", e_)
        return 1
    print("Palette check OK: no color outside the locked palette variables.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
