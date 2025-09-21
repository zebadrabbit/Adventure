#!/usr/bin/env python
"""Fail commit if legacy SQLAlchemy Query.get usage is detected.

Rationale: SQLAlchemy 2.x deprecates Query.get in favor of Session.get. This
prevents reintroduction after refactor.

Exemptions: None (usage should not reappear). If a false positive occurs,
refactor the line instead of bypassing the hook.
"""
from __future__ import annotations
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Simple scan (avoid importing project modules to stay lightweight & side-effect free)
violations = []
target_pattern = '.query.get('
self_path = pathlib.Path(__file__).resolve()
for path in ROOT.rglob('*.py'):
    if path.resolve() == self_path:
        continue
    if any(part in {'.venv', '__pycache__'} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    if target_pattern in text:
        for idx, line in enumerate(text.splitlines(), 1):
            if target_pattern in line:
                violations.append(f"{path}:{idx}: deprecated Query.get usage")

if violations:
    sys.stderr.write("Deprecated SQLAlchemy Query.get() usages found:\n")
    for v in violations:
        sys.stderr.write(v + "\n")
    sys.stderr.write("Refactor to db.session.get(Model, id) before committing.\n")
    sys.exit(1)

sys.exit(0)
