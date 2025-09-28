#!/usr/bin/env python3
"""Fail if manual ?v= cache-busting tokens are detected in templates or JS.
Use asset_url() instead.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pattern = re.compile(r"\?v=\d{6,}")
violations = []

for path in (ROOT / "app" / "templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    if pattern.search(text):
        violations.append(str(path.relative_to(ROOT)))

if violations:
    print("[FAIL] Manual version tokens found:")
    for v in violations:
        print("  -", v)
    print('Use asset_url("file") instead of manual ?v= tokens.')
    sys.exit(1)
else:
    print("[OK] No manual ?v= tokens detected.")
