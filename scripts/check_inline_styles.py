#!/usr/bin/env python3
"""Fail if any template (except macros/svg_icon.html historically) contains inline style attributes.
Usage: python scripts/check_inline_styles.py
Exits non-zero on violations.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"

# Grandfathered pre-existing violations -- now empty (the full inline-style
# extraction follow-up logged in docs/superpowers/TODO.md is complete). Keep
# this set so a future regression has somewhere obvious to add an entry
# without restructuring the script, but do not add to it casually: any new
# inline style= attribute should be fixed at the source instead.
ALLOWED_FILES = set()
VIOLATIONS = []

for html in TEMPLATES.rglob("*.html"):
    rel = str(html.relative_to(ROOT))
    if rel in ALLOWED_FILES:
        continue
    text = html.read_text(encoding="utf-8", errors="ignore")
    if "style=" in text:
        VIOLATIONS.append(rel)

if VIOLATIONS:
    print("[FAIL] Inline style attribute usage detected in:")
    for v in VIOLATIONS:
        print("  -", v)
    sys.exit(1)
else:
    print("[OK] No inline style attributes detected.")
