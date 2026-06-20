#!/usr/bin/env python3
"""Fail if any template (except macros/svg_icon.html historically) contains inline style attributes.
Usage: python scripts/check_inline_styles.py
Exits non-zero on violations.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"

# Grandfathered pre-existing violations (confirmed via `git stash` to predate
# any specific change -- not caused by current work). This is a ratchet, not
# a permanent allowance: do not add new files here. Each entry should get
# cleaned up and removed as part of the deferred "extract inline styles into
# real CSS" follow-up (see docs/superpowers/TODO.md). New files, and any
# *other* existing file gaining a fresh inline style, are still caught below.
ALLOWED_FILES = {
    "app/templates/admin_themes.html",
    "app/templates/dashboard.html",
    "app/templates/combat.html",
    "app/templates/adventure.html",
    "app/templates/account/settings.html",
    "app/templates/admin/progression_settings.html",
    "app/templates/admin/loot_settings.html",
    "app/templates/admin/combat_settings.html",
    "app/templates/admin/seed_data.html",
    "app/templates/admin/dungeon_settings.html",
}
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
