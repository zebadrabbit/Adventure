#!/usr/bin/env python3
"""Fail if any template (except macros/svg_icon.html historically) contains inline style attributes.
Usage: python scripts/check_inline_styles.py
Exits non-zero on violations.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"

ALLOWED_FILES = set()  # emptied after removing style macro param
VIOLATIONS = []

for html in TEMPLATES.rglob("*.html"):
    text = html.read_text(encoding="utf-8", errors="ignore")
    if "style=" in text:
        VIOLATIONS.append(str(html.relative_to(ROOT)))

if VIOLATIONS:
    print("[FAIL] Inline style attribute usage detected in:")
    for v in VIOLATIONS:
        print("  -", v)
    sys.exit(1)
else:
    print("[OK] No inline style attributes detected.")
