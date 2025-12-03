#!/usr/bin/env python3
"""
Manual exception handling fix helper.

This script identifies silent exception handlers and provides
copy-paste replacement code for manual fixing.

Usage:
    python scripts/manual_exception_fixes.py app/routes/dungeon_api.py
    python scripts/manual_exception_fixes.py --all
"""

import argparse
from pathlib import Path
from typing import List, Tuple


def find_exceptions_in_file(filepath: str) -> List[Tuple[int, str, str]]:
    """Find silent exception handlers and generate fixes."""
    fixes = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        # Find all lines with except followed by pass
        for i, line in enumerate(lines, 1):
            # Skip pragma comments
            if "pragma: no cover" in line or "noqa" in line:
                continue

            # Look for patterns
            if i < len(lines) and "except" in line:
                # Check next line for pass
                next_idx = i
                while next_idx < len(lines) and lines[next_idx].strip() == "":
                    next_idx += 1

                if next_idx < len(lines) and lines[next_idx].strip() == "pass":
                    # Get indentation for pass statement
                    pass_indent = len(lines[next_idx]) - len(lines[next_idx].lstrip())

                    # Generate fix
                    indent = " " * pass_indent
                    basename = Path(filepath).stem

                    # Check if 'as e' exists
                    if " as " in line:
                        var = line.split(" as ")[1].strip().rstrip(":").strip()
                        new_except = line
                    else:
                        var = "e"
                        new_except = line.rstrip().rstrip(":") + " as e:"

                    new_body = f'{indent}logger.exception("Error in {basename}", exc_info={var})'

                    fixes.append((i, new_except, new_body))

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

    return fixes


def main():
    parser = argparse.ArgumentParser(description="Generate exception handling fixes")
    parser.add_argument("file", nargs="?", help="File to check")
    parser.add_argument("--all", action="store_true", help="Check all files")

    args = parser.parse_args()

    if args.all:
        files = list(Path("app").rglob("*.py"))
    elif args.file:
        files = [Path(args.file)]
    else:
        parser.print_help()
        return

    print("# Exception Handling Fixes")
    print("\n## Instructions:")
    print("1. Add at top of file if not present:")
    print("   ```python")
    print("   import structlog")
    print("   logger = structlog.get_logger()")
    print("   ```")
    print("\n2. Replace each EXCEPT + PASS with the fix shown below:\n")

    total_fixes = 0
    for filepath in sorted(files):
        if "__pycache__" in str(filepath):
            continue

        fixes = find_exceptions_in_file(str(filepath))
        if fixes:
            print(f"\n### {filepath}")
            print(f"Found {len(fixes)} issues\n")

            with open(filepath, "r") as f:
                lines = f.readlines()

            for line_num, new_except, new_body in fixes:
                # Show context
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 3)

                print(f"**Line {line_num}:**")
                print("```python")
                print("# BEFORE:")
                for i in range(start, end):
                    marker = ">>>" if i == line_num - 1 else "   "
                    print(f"{marker} {lines[i].rstrip()}")

                print("\n# AFTER:")
                for i in range(start, end):
                    if i == line_num - 1:
                        print(f">>> {new_except}")
                        print(f">>>     {new_body}")
                    elif "pass" not in lines[i] or i != line_num:
                        print(f"    {lines[i].rstrip()}")
                print("```\n")

                total_fixes += 1

    if total_fixes == 0:
        print("\n✓ No silent exception handlers found!")
    else:
        print(f"\n---\nTotal fixes needed: {total_fixes}")


if __name__ == "__main__":
    main()
