#!/usr/bin/env python3
"""Version bump utility.

Usage:
  python scripts/bump_version.py patch
  python scripts/bump_version.py minor
  python scripts/bump_version.py major
  python scripts/bump_version.py set 1.2.3

Behavior:
  - Reads current version from VERSION file.
  - Computes new version per semantic bump.
  - Writes VERSION.
  - Inserts an UNRELEASED changelog stub if not present.
  - Optionally updates README What's New header if previous latest matches old version (skipped for now).

Exit codes:
  0 success
  1 invalid args
  2 git dirty (unless --force)
"""
from __future__ import annotations
import sys, re, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / 'VERSION'
def find_changelog() -> pathlib.Path | None:
    candidates = [ROOT / 'docs' / 'CHANGELOG.md', ROOT / 'CHANGELOG.md']
    for p in candidates:
        if p.exists():
            return p
    return None

CHANGELOG = find_changelog()

SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')


def read_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding='utf-8').strip()
    return '0.0.0'

def write_version(v: str) -> None:
    VERSION_FILE.write_text(v + '\n', encoding='utf-8')

def git_dirty() -> bool:
    try:
        out = subprocess.check_output(['git', 'status', '--porcelain'], text=True)
        return bool(out.strip())
    except Exception:
        return False

def bump(v: str, kind: str, explicit: str | None) -> str:
    if kind == 'set':
        if not explicit or not SEMVER_RE.match(explicit):
            raise ValueError('Explicit version must be semver (X.Y.Z)')
        return explicit
    m = SEMVER_RE.match(v)
    if not m:
        raise ValueError(f'Current version {v} is not semver')
    major, minor, patch = map(int, m.groups())
    if kind == 'major':
        return f'{major+1}.0.0'
    if kind == 'minor':
        return f'{major}.{minor+1}.0'
    if kind == 'patch':
        return f'{major}.{minor}.{patch+1}'
    raise ValueError('Unknown bump kind')

def ensure_changelog_stub(new_version: str):
    if CHANGELOG is None or not CHANGELOG.exists():
        return
    text = CHANGELOG.read_text(encoding='utf-8')
    header = f'# [{new_version}] - UNRELEASED'
    if header in text:
        return
    # Insert at top
    lines = text.splitlines()
    # Find first non-empty line (should be first heading)
    insertion_index = 0
    # Prepend stub
    stub = [
        header,
        '### Added',
        '### Changed',
        '### Fixed',
        '### Notes',
        '',
    ]
    new_text = '\n'.join(stub + lines)
    CHANGELOG.write_text(new_text + ('\n' if not new_text.endswith('\n') else ''), encoding='utf-8')

def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {'patch','minor','major','set'}:
        print('Usage: bump_version.py [patch|minor|major|set X.Y.Z] [--force]')
        return 1
    force = '--force' in argv
    kind = argv[1]
    explicit = None
    if kind == 'set':
        if len(argv) < 3:
            print('Usage: bump_version.py set X.Y.Z')
            return 1
        explicit = argv[2]
    current = read_version()
    try:
        new_version = bump(current, kind, explicit)
    except ValueError as e:
        print(f'Error: {e}')
        return 1
    if not force and git_dirty():
        print('Refusing to bump: git working directory not clean (use --force to override)')
        return 2
    write_version(new_version)
    ensure_changelog_stub(new_version)
    print(f'Version bumped: {current} -> {new_version}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
