#!/usr/bin/env python3
"""
Basic SVG optimizer for repo consistency (lightweight alternative to full svgo dependency).

Actions performed:
 - Strip XML comments (<!-- ... -->) except license/prefix containing 'copyright'
 - Collapse consecutive whitespace inside element tags & between > <
 - Remove trailing spaces
 - Ensure single terminal newline
 - Preserve viewBox, IDs, and inline styles (no semantic rewrites)

Usage:
  python scripts/optimize_svgs.py path/to/file.svg [more.svg ...]
If no args provided, walks ./app/static and ./static (if present) for .svg files.

Exit code non-zero if any file was modified (to integrate with pre-commit fail-then-fix pattern).
"""
from __future__ import annotations
import sys, re, pathlib

COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
WHITESPACE_BETWEEN_TAGS = re.compile(r">\s+<")
MULTISPACE = re.compile(r"[ \t]{2,}")

LICENSE_KEEP_WORDS = {"copyright", "mit", "license"}

def optimize_svg(text: str) -> str:
    original = text
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    def repl_comment(match):
        body = match.group(1)
        lowered = body.lower()
        if any(word in lowered for word in LICENSE_KEEP_WORDS):
            return match.group(0)  # preserve
        # remove otherwise
        return ""
    text = COMMENT_RE.sub(repl_comment, text)

    # Collapse spaces between tags
    text = re.sub(r">\s+<", ">\n<", text)  # keep structural newline

    # Trim leading/trailing whitespace on lines
    lines = [ln.rstrip() for ln in text.split('\n')]
    text = '\n'.join(lines).strip() + '\n'

    return text if text != original else original

def process_file(path: pathlib.Path) -> bool:
    content = path.read_text(encoding='utf-8')
    optimized = optimize_svg(content)
    if optimized != content:
        path.write_text(optimized, encoding='utf-8')
        return True
    return False

def discover_targets() -> list[pathlib.Path]:
    roots = [pathlib.Path('app/static'), pathlib.Path('static')]
    results = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob('*.svg'):
            results.append(p)
    return results

def main(argv: list[str]) -> int:
    if len(argv) > 1:
        targets = [pathlib.Path(a) for a in argv[1:]]
    else:
        targets = discover_targets()
    changed_any = False
    for t in targets:
        if not t.is_file():
            continue
        try:
            if process_file(t):
                print(f"Optimized {t}")
                changed_any = True
        except Exception as e:
            print(f"Error optimizing {t}: {e}", file=sys.stderr)
            return 2
    return 1 if changed_any else 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
