#!/usr/bin/env python3
"""Fail build if any template contains an inline <script>...</script> with code instead of a src attribute.
Allowed patterns: <script src=...> only.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
pattern = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.DOTALL | re.IGNORECASE)

# Grandfathered pre-existing violations -- now empty (the full inline-script
# extraction follow-up logged in docs/superpowers/TODO.md is complete). Keep
# this set so a future regression has somewhere obvious to add an entry
# without restructuring the script, but do not add to it casually: any new
# inline <script> block should be moved to a real .js file instead.
ALLOWED_FILES = set()
violations = []

for html in TEMPLATES.rglob("*.html"):
    rel = str(html.relative_to(ROOT))
    if rel in ALLOWED_FILES:
        continue
    text = html.read_text(encoding="utf-8", errors="ignore")
    for m in pattern.finditer(text):
        # Ignore empty or whitespace-only
        inner = m.group(2).strip()
        if inner:
            violations.append(rel)
            break

if violations:
    print("[FAIL] Inline script blocks detected in:")
    for v in violations:
        print("  -", v)
    sys.exit(1)
else:
    print("[OK] No inline script blocks detected.")
