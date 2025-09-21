# Rebase & History Hygiene Helper

Keeping a clean, readable history makes it easier to review changes and bisect regressions. This helper outlines common patterns used in this project.

## When to Rebase vs. Merge
- Use `git rebase` for feature branches that have not yet been pushed for shared review or that you explicitly coordinate with collaborators to rewrite.
- Use merge commits for integrating long‑lived branches if preserving chronological context matters.
- Before opening a PR, squash fixup commits ("typo", "lint", "address review") into the logical commits they refine.

## Golden Rules
1. Never rebase the `main` branch.
2. Never rebase a branch that others have already pulled unless coordinated.
3. Favor meaningful commit messages: imperative mood, present tense, concise subject (< 72 chars) + wrapped body.
4. Group commits by logical unit (feature, refactor, test addition) not by timestamp.

## Typical Workflow (Interactive Squash Before PR)
```bash
# Ensure branch is up to date
git fetch origin

# Rebase onto latest main
git rebase origin/main

# If you have multiple fixups, use interactive rebase to squash them
git rebase -i origin/main
# In the editor:
# pick  abc1234  add websocket tests
# fixup def5678  address lint
# fixup 7890abc  adjust doc phrasing
# Result: a single commit with clean message.

# Force push ONLY if branch already published and you rewrote commits
git push --force-with-lease
```

## Using Autosquash for Fixup Commits
```bash
git commit --fixup <commit-hash>
# Later:
git rebase -i --autosquash origin/main
```

## Split a Large Commit
```bash
git reset -p HEAD^  # interactively unstage portions
# Stage logical chunks
git add path/to/file_a
git commit -m "feat: add dungeon repair helper"
# Repeat staging for the next logical chunk
```

## Abort / Recover
```bash
git rebase --abort      # abandon current rebase
git reflog              # find previous state if needed
```

## Amend Latest Commit (small tweak)
```bash
git add forgotten_file
git commit --amend --no-edit
```

## Commit Message Template
```
feat: short summary (< 50-72 chars)

Optional detailed explanation: what & why (not how). Wrap at 72 chars.
Refs: #123 (issue/PR) if applicable.
```

## Conventional Commit Types Used Here
- feat, fix, refactor, test, docs, chore, perf, build, ci

## Pre-Push Checklist
- [ ] Tests pass locally (`pytest -q`)
- [ ] Lint passes (`ruff check .`)
- [ ] No stray debug prints / large assets
- [ ] CHANGELOG updated if user-visible change
- [ ] Version bumped (if release-worthy) using `python scripts/bump_version.py patch|minor|major`

## Scripted Helper (Optional Alias)
Add to your shell profile for quick interactive cleanup:
```bash
alias grb='git fetch origin && git rebase -i origin/main'
```

---
Maintainers may request history cleanup before merge to keep `main` bisect-friendly.
