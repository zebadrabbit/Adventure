#!/usr/bin/env python3
"""
Fix silent exception handling throughout the codebase.

This script identifies and reports files with silent exception handling
(except: pass or except Exception: pass) that should be replaced with
proper logging.

Usage:
    python scripts/fix_exception_handling.py --check      # Report issues
    python scripts/fix_exception_handling.py --fix        # Auto-fix where safe
    python scripts/fix_exception_handling.py --report     # Generate detailed report
"""

import argparse
import ast
import os
from pathlib import Path
from typing import List


class ExceptionHandlerVisitor(ast.NodeVisitor):
    """AST visitor to find silent exception handlers."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []

    def visit_ExceptHandler(self, node):
        """Check if exception handler has only 'pass' statement."""
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            # Check if there's a pragma comment to skip
            self.issues.append(
                {
                    "line": node.lineno,
                    "type": self._get_exception_type(node),
                    "col": node.col_offset,
                }
            )
        self.generic_visit(node)

    def _get_exception_type(self, node):
        """Extract exception type name."""
        if node.type is None:
            return "bare except"
        elif isinstance(node.type, ast.Name):
            return node.type.id
        elif isinstance(node.type, ast.Tuple):
            return "multiple"
        return "unknown"


def find_silent_exceptions(root_dir: str = "app") -> dict:
    """Find all silent exception handlers in Python files."""
    results = {}

    for path in Path(root_dir).rglob("*.py"):
        if "__pycache__" in str(path):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(path))

            visitor = ExceptionHandlerVisitor(str(path))
            visitor.visit(tree)

            if visitor.issues:
                # Check for pragma comments
                lines = content.split("\n")
                filtered_issues = []

                for issue in visitor.issues:
                    line_idx = issue["line"] - 1
                    if line_idx < len(lines):
                        line = lines[line_idx]
                        # Skip if has pragma: no cover or explicit ignore comment
                        if "pragma: no cover" not in line and "noqa" not in line:
                            filtered_issues.append(issue)

                if filtered_issues:
                    results[str(path)] = filtered_issues

        except SyntaxError as e:
            print(f"Syntax error in {path}: {e}")
        except Exception as e:
            print(f"Error processing {path}: {e}")

    return results


def generate_fix_for_file(filepath: str, issues: List[dict]) -> str:
    """Generate logging-based fix for a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Sort issues by line number (reverse order for bottom-up replacement)
    sorted_issues = sorted(issues, key=lambda x: x["line"], reverse=True)

    for issue in sorted_issues:
        line_idx = issue["line"] - 1
        if line_idx >= len(lines):
            continue

        # Check if this is a 'pass' statement
        if "pass" not in lines[line_idx]:
            continue

        indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
        indent_str = " " * indent

        # Find the except line (search backwards from pass statement)
        except_line_idx = line_idx
        while except_line_idx > 0 and "except" not in lines[except_line_idx]:
            except_line_idx -= 1

        # Get the except line
        except_line = lines[except_line_idx]

        # Check if variable is already captured
        var_name = None
        if " as " in except_line:
            # Extract variable name: "except Exception as e:" -> "e"
            var_name = except_line.split(" as ")[1].strip().rstrip(":").strip()
        else:
            # Add 'as e' to except clause
            var_name = "e"
            # Handle both "except Exception:" and "except:"
            if except_line.rstrip().endswith(":"):
                lines[except_line_idx] = except_line.rstrip()[:-1] + " as e:\n"
            else:
                lines[except_line_idx] = except_line.rstrip() + " as e:\n"

        # Replace pass with proper logging
        basename = os.path.basename(filepath).replace(".py", "")
        replacement = f'{indent_str}logger.exception("Error in {basename}", exc_info={var_name})\n'

        lines[line_idx] = replacement

    return "".join(lines)


def check_has_logger_import(filepath: str) -> bool:
    """Check if file imports structlog or logging."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        return "import structlog" in content or "import logging" in content or "logger = " in content


def add_logger_import(filepath: str, content: str) -> str:
    """Add structlog import if not present."""
    if "import structlog" in content or "logger = structlog" in content:
        return content

    lines = content.split("\n")

    # Find the last import line
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            last_import_idx = i

    # Insert after last import
    lines.insert(last_import_idx + 1, "")
    lines.insert(last_import_idx + 2, "import structlog")
    lines.insert(last_import_idx + 3, "logger = structlog.get_logger()")
    lines.insert(last_import_idx + 4, "")

    return "\n".join(lines)


def generate_report(results: dict) -> str:
    """Generate a detailed report of issues."""
    report = ["# Exception Handling Issues Report", ""]
    report.append(f"Found {sum(len(issues) for issues in results.values())} silent exception handlers")
    report.append(f"in {len(results)} files\n")

    for filepath, issues in sorted(results.items()):
        report.append(f"\n## {filepath}")
        report.append(f"Found {len(issues)} issue(s):\n")

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for issue in sorted(issues, key=lambda x: x["line"]):
            line_idx = issue["line"] - 1
            if line_idx < len(lines):
                context_start = max(0, line_idx - 2)
                context_end = min(len(lines), line_idx + 3)

                report.append(f"Line {issue['line']} ({issue['type']}):")
                report.append("```python")
                for i in range(context_start, context_end):
                    prefix = ">>> " if i == line_idx else "    "
                    report.append(f"{prefix}{lines[i].rstrip()}")
                report.append("```\n")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Fix silent exception handling")
    parser.add_argument("--check", action="store_true", help="Check for issues")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    parser.add_argument("--dir", default="app", help="Directory to scan (default: app)")
    parser.add_argument("--output", default="exception_report.md", help="Report output file")

    args = parser.parse_args()

    if not any([args.check, args.fix, args.report]):
        args.check = True  # Default to check mode

    print(f"Scanning {args.dir} for silent exception handlers...")
    results = find_silent_exceptions(args.dir)

    if not results:
        print("✓ No silent exception handlers found!")
        return 0

    total_issues = sum(len(issues) for issues in results.values())
    print(f"\nFound {total_issues} silent exception handlers in {len(results)} files:")

    for filepath, issues in sorted(results.items()):
        print(f"  {filepath}: {len(issues)} issue(s)")

    if args.report:
        report = generate_report(results)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✓ Detailed report written to {args.output}")

    if args.fix:
        print("\nApplying fixes...")
        fixed_count = 0

        for filepath, issues in results.items():
            try:
                # Generate fixed content
                fixed_content = generate_fix_for_file(filepath, issues)

                # Add logger import if needed
                if not check_has_logger_import(filepath):
                    fixed_content = add_logger_import(filepath, fixed_content)

                # Write back
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(fixed_content)

                fixed_count += 1
                print(f"  ✓ Fixed {filepath}")

            except Exception as e:
                print(f"  ✗ Error fixing {filepath}: {e}")

        print(f"\n✓ Fixed {fixed_count} files")
        print("\nNOTE: Please review the changes and run tests to ensure correctness.")
        print("Some fixes may require manual adjustment for proper context.")

    return 1 if results else 0


if __name__ == "__main__":
    exit(main())
