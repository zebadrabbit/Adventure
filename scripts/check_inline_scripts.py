#!/usr/bin/env python3
"""Fail build if any template contains an inline <script>...</script> with code instead of a src attribute.
Allowed patterns: <script src=...> only.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
pattern = re.compile(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.DOTALL | re.IGNORECASE)
violations = []

for html in TEMPLATES.rglob('*.html'):
    text = html.read_text(encoding='utf-8', errors='ignore')
    for m in pattern.finditer(text):
        # Ignore empty or whitespace-only
        inner = m.group(2).strip()
        if inner:
            violations.append(str(html.relative_to(ROOT)))
            break

if violations:
    print('[FAIL] Inline script blocks detected in:')
    for v in violations:
        print('  -', v)
    sys.exit(1)
else:
    print('[OK] No inline script blocks detected.')
