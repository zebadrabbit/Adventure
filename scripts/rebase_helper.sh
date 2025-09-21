#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/rebase_helper.sh [--autosquash] [upstream_branch]

Safely rebase current branch onto the specified upstream (default: origin/main).
Ensures working tree clean, fetches latest, and provides guidance.

Options:
  --autosquash    Enable autosquash for fixup!/squash! commits
  -h, --help      Show this help
EOF
}

UPSTREAM="origin/main"
AUTOSQUASH="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autosquash) AUTOSQUASH="yes"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) UPSTREAM="$1"; shift ;;
  esac
done

if ! git rev-parse --abbrev-ref HEAD >/dev/null 2>&1; then
  echo "[ERROR] Not a git repository." >&2; exit 1
fi

CURRENT=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT" == "main" ]]; then
  echo "[WARN] You are on main. Aborting to avoid rebasing main." >&2
  exit 2
fi

# Ensure clean state
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "[ERROR] Working tree not clean. Commit or stash changes first." >&2
  exit 3
fi

echo "[INFO] Fetching latest refs..."
git fetch origin

if ! git rev-parse "$UPSTREAM" >/dev/null 2>&1; then
  echo "[ERROR] Upstream ref '$UPSTREAM' not found." >&2
  exit 4
fi

echo "[INFO] Rebasing '$CURRENT' onto '$UPSTREAM'..."
set +e
if [[ "$AUTOSQUASH" == "yes" ]]; then
  git rebase -i --autosquash "$UPSTREAM"
else
  git rebase "$UPSTREAM"
fi
STATUS=$?
set -e

if [[ $STATUS -ne 0 ]]; then
  echo "[ERROR] Rebase failed (exit $STATUS). Resolve conflicts then run: git rebase --continue" >&2
  exit $STATUS
fi

echo "[OK] Rebase complete."
echo "Next steps:"
echo "  1. Run tests: pytest -q"
echo "  2. Push (force-with-lease if branch already published):"
echo "     git push --force-with-lease origin $CURRENT"
