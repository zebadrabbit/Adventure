#!/usr/bin/env python3
"""Prune unused SVG iconography assets.

This utility scans the repository for references to SVG filenames inside the
`app/static/iconography/` directory and (optionally) deletes those not found.

Default behavior is a dry run: lists used / unused counts and prints paths.

Heuristics:
  * Matches exact svg filenames that appear in code/text files (not binary) with
    patterns: 'iconography/<name>.svg' or just '<name>.svg' when preceded by common
    static path markers.
  * Scans .py, .js, .ts, .html, .css, .md, .json, .yml, .yaml, .txt.
  * Excludes the iconography directory itself from textual word splitting to avoid
    a file counting as its own usage.

Limitations:
  * Dynamic construction of filenames (e.g., template string building slug + '.svg')
    may not be detected; provide a keep-list file for those.

CLI:
  --delete           Actually delete unused icons.
  --keep-file FILE   A newline-delimited list of filenames to always keep.
  --only-print       Only print unused filenames (one per line) for piping.
  --extensions       Comma list of extra extensions to scan.
  --root PATH        Repository root (auto-detected if omitted).
  --pattern REGEX    Additional regex (filename) to force keep if it matches.

Examples:
  Dry run summary:
    python scripts/prune_iconography.py
  Delete after review:
    python scripts/prune_iconography.py --delete
  Keep specific sprites:
    python scripts/prune_iconography.py --keep-file keep-icons.txt --delete
  Pipe only unused into xargs (dry run):
    python scripts/prune_iconography.py --only-print
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Set

SCAN_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".md", ".json", ".yml", ".yaml", ".txt"}
ICON_DIR = Path("app/static/iconography")
SVG_EXT = ".svg"
REFERENCE_REGEX = re.compile(r"iconography/([a-zA-Z0-9_\-]+)\.svg")
LOOSE_REGEX = re.compile(r"([a-zA-Z0-9_\-]+)\.svg")


def iter_code_files(root: Path, extra_ext: Set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        ext = path.suffix.lower()
        if ext in SCAN_EXT or ext in extra_ext:
            # Skip scanning iconography SVG files themselves for references (noise)
            if ICON_DIR in path.parents:
                continue
            # Skip obvious binary (very rough heuristic)
            try:
                if path.stat().st_size > 2_000_000:
                    continue
            except OSError:
                continue
            yield path


def collect_used_filenames(root: Path, extra_ext: Set[str]) -> Set[str]:
    used: Set[str] = set()
    for file in iter_code_files(root, extra_ext):
        try:
            text = file.read_text(errors="ignore")
        except Exception:
            continue
        for m in REFERENCE_REGEX.finditer(text):
            used.add(m.group(1) + SVG_EXT)
        # Loose matches: ensure we only add if a file with that basename exists
        for m in LOOSE_REGEX.finditer(text):
            candidate = m.group(1) + SVG_EXT
            used.add(candidate)
    return used


def load_keep_list(path: Path | None) -> Set[str]:
    keep: Set[str] = set()
    if not path:
        return keep
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not line.lower().endswith(".svg"):
                line += ".svg"
            keep.add(Path(line).name)
    except Exception:
        pass
    return keep


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Prune unused SVG icons.")
    ap.add_argument("--delete", action="store_true", help="Delete unused assets.")
    ap.add_argument("--keep-file", type=Path, help="List of filenames (one per line) to always keep.")
    ap.add_argument("--only-print", action="store_true", help="Only print unused filenames (no summary).")
    ap.add_argument("--extensions", type=str, help="Extra comma-separated extensions to scan (e.g., .jinja,.vue)")
    ap.add_argument("--root", type=Path, help="Repo root (defaults to current working directory).")
    ap.add_argument("--pattern", type=str, help="Regex for names to force-keep (applied to basename).")
    args = ap.parse_args(argv)

    root = args.root or Path.cwd()
    icon_dir = root / ICON_DIR
    if not icon_dir.exists():
        print(f"[error] icon directory not found: {icon_dir}", file=sys.stderr)
        return 2

    extra_ext: Set[str] = set()
    if args.extensions:
        for part in args.extensions.split(","):
            part = part.strip()
            if part and part.startswith("."):
                extra_ext.add(part.lower())

    used = collect_used_filenames(root, extra_ext)
    all_icons = {p.name for p in icon_dir.glob("*.svg")}

    keep = load_keep_list(args.keep_file)
    if args.pattern:
        try:
            pat = re.compile(args.pattern)
            for name in list(all_icons):
                if pat.search(name):
                    keep.add(name)
        except re.error as e:
            print(f"[warn] invalid regex '{args.pattern}': {e}", file=sys.stderr)

    # Unused = icons present but not referenced, excluding forced keep list
    unused = sorted([n for n in all_icons if n not in used and n not in keep])

    if args.only_print:
        for name in unused:
            print(name)
        return 0

    deleted = []
    if args.delete:
        for name in unused:
            try:
                (icon_dir / name).unlink()
                deleted.append(name)
            except Exception as e:
                print(f"[warn] failed to delete {name}: {e}")

    used_count = len(used & all_icons)
    print(f"[prune] total icons: {len(all_icons)}")
    print(f"[prune] referenced icons: {used_count}")
    print(f"[prune] unused icons: {len(unused)}")
    if keep:
        print(f"[prune] kept (forced): {len(keep)}")
    if args.delete:
        print(f"[prune] deleted: {len(deleted)}")
    else:
        print("[prune] (dry run) nothing deleted. Use --delete to remove above.")

    if unused:
        print("\nUnused icon filenames:")
        for name in unused:
            print("  ", name)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
