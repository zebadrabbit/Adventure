# Phase 5a — Cold Steel Remaining Literals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `home.css`'s remaining old-palette `rgba()` literals to
`color-mix()` expressions on the Cold Steel namespace, the same mechanical
technique Phase 2 already proved on `theme.css`.

**Architecture:** A small Python regex-substitution script (mirroring Phase
2's exact approach), extended with 2 new RGB-triple mappings `home.css`
introduces beyond Phase 2's original 6.

**Tech Stack:** Plain CSS (`color-mix()`, already used elsewhere in this
codebase). No new dependencies.

## Global Constraints

- Single file touched: `app/static/css/home.css`. No template, JS, or
  backend changes.
- The `rgba(99, 102, 241, ...)` indigo hero-badge colors
  (`home.css:91-92`) and the `#a5b4fc` text color (`home.css:97`) must NOT be
  touched — confirmed intentional, not part of the old amber/brown palette.
- Mapping table (exact, from the spec):
  - `rgb(212, 165, 116)` → `var(--dungeon-accent)`
  - `rgb(61, 50, 38)` → `var(--dungeon-border)`
  - `rgb(26, 21, 18)` → `var(--dungeon-panel)`
  - `rgb(13, 10, 10)` → `var(--dungeon-bg)`
  - `rgb(193, 122, 58)` → `var(--dungeon-accent)`
  - `rgb(139, 111, 71)` → `var(--dungeon-border)`

---

### Task 1: Convert `home.css`'s old-palette literals to `color-mix()`

**Files:**
- Modify: `app/static/css/home.css` (17 occurrences across 6 distinct RGB
  triples)
- Test: manual grep verification (no CSS unit test framework in this repo)

**Interfaces:**
- Consumes: `--dungeon-bg`, `--dungeon-panel`, `--dungeon-border`,
  `--dungeon-accent` (all defined in `theme.css`'s `:root` block from Phase
  1, unchanged by this task).
- Produces: no new interface — every occurrence of the 6 old RGB triples in
  `home.css` becomes a `color-mix()` expression, exact alpha preserved.

- [ ] **Step 1: Write and run the conversion script**

Create a temporary script (not committed — delete it after running):

```python
# /tmp/convert_home_colors.py
import re

PATH = "app/static/css/home.css"

MAPPING = {
    (212, 165, 116): "--dungeon-accent",
    (61, 50, 38): "--dungeon-border",
    (26, 21, 18): "--dungeon-panel",
    (13, 10, 10): "--dungeon-bg",
    (193, 122, 58): "--dungeon-accent",
    (139, 111, 71): "--dungeon-border",
}

def fmt_pct(alpha_str: str) -> str:
    pct = float(alpha_str) * 100
    if pct == int(pct):
        return str(int(pct))
    return str(pct)

def replace(match: re.Match) -> str:
    r, g, b, alpha = match.groups()
    key = (int(r), int(g), int(b))
    if key not in MAPPING:
        return match.group(0)
    var_name = MAPPING[key]
    return f"color-mix(in srgb, var({var_name}) {fmt_pct(alpha)}%, transparent)"

pattern = re.compile(
    r"rgba\((\d+), ?(\d+), ?(\d+), ?([\d.]+)\)"
)

with open(PATH) as f:
    content = f.read()

new_content, count = pattern.subn(replace, content)

with open(PATH, "w") as f:
    f.write(new_content)

print(f"Replaced {count} occurrences")
```

Run: `.venv/bin/python /tmp/convert_home_colors.py`
Expected output: `Replaced 17 occurrences`

Note: the regex matches every `rgba(...)` call including the indigo
`rgba(99, 102, 241, ...)` ones, but the `replace` function's `key not in
MAPPING` check returns the original match unchanged for any triple not in
`MAPPING` — so the indigo hero-badge literals pass through untouched while
still counting toward the regex's total match count. Verify this in Step 2.

- [ ] **Step 2: Verify zero old-palette literal occurrences remain, and the indigo literals are untouched**

Run:
```bash
grep -c "rgba(212, 165, 116\|rgba(61, 50, 38\|rgba(26, 21, 18\|rgba(13, 10, 10\|rgba(193, 122, 58\|rgba(139, 111, 71" app/static/css/home.css
```
Expected: `0` (no matches for any of the 6 old-palette triples).

Run:
```bash
grep -c "rgba(99, 102, 241" app/static/css/home.css
```
Expected: `2` (the hero-badge background and border declarations,
unchanged).

- [ ] **Step 3: Spot-check 2 converted rules render the expected expression**

Run: `grep -n "color-mix" app/static/css/home.css | head -6`
Expected output includes lines matching this shape (exact percentages vary
per original alpha), for example:
```
        radial-gradient(circle at 80% 50%, color-mix(in srgb, var(--dungeon-accent) 8%, transparent) 0%, transparent 50%),
```
Confirm the percentages match each rule's original alpha (e.g. original
`0.08` → `8%`).

- [ ] **Step 4: Delete the temporary conversion script**

Run: `rm /tmp/convert_home_colors.py`

- [ ] **Step 5: Commit**

```bash
git add app/static/css/home.css
git commit -m "feat(home): convert home.css's remaining embedded color literals to color-mix() on the Cold Steel namespace"
```

---

### Task 2: Verification and TODO update

**Files:**
- Modify: `docs/superpowers/TODO.md`
- Test: manual, via real browser screenshot (Playwright, as used for prior
  phases).

**Interfaces:**
- Consumes: Task 1.
- Produces: nothing new — closing verification + documentation task.

- [ ] **Step 1: Run the full backend test suite to confirm no regressions**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py --deselect tests/test_gear_party_payload.py::test_payload_reflects_gear_hp
```
Expected: all tests pass (the second deselect is the confirmed pre-existing
failure from prior phases, unrelated to this CSS-only work).

- [ ] **Step 2: Take a real browser screenshot of the landing page**

Use a Playwright install available on the host (as used for prior phases).
Navigate to `/` (no login required) and confirm:
- The hero section's background glow blobs read as Cold Steel teal/charcoal
  tones, not amber/brown.
- The hero badge (with the indigo `rgba(99, 102, 241, ...)` background)
  still renders with its original indigo color, unchanged.
- No console errors.

- [ ] **Step 3: Update `docs/superpowers/TODO.md`**

Find the Phase 3d entry via `grep -n "UI Redesign Phase 3d" docs/superpowers/TODO.md`.
Add a new entry immediately after it:

```markdown
### UI Redesign Phase 5a — Cold Steel: remaining embedded literals ✅
Converted `home.css`'s 17 remaining old-palette `rgba()` literals (6 RGB
triples — 4 reused from Phase 2's `theme.css` mapping, plus 2 new ones found
only here: `rgb(193, 122, 58)` and `rgb(139, 111, 71)`, both low-opacity
hero-section background-glow blobs) to `color-mix()` expressions on the Cold
Steel namespace, via the same mechanical script-based technique Phase 2
used. Investigated and ruled out two other Phase-5-shaped candidates before
landing on this scope: (1) `auth.css` (login/register page styles) — already
clean, zero old-palette literals; (2) `account/profile.html` and
`account/settings.html`'s use of `glass-theme.css` — initially suspected as
a leftover "third palette" inconsistency per Phase 1's findings, but
confirmed on inspection that the specific classes these pages actually use
(`.section-card`, `.stat-card`) are already neutral frosted-glass cards
already referencing `var(--adv-primary)`, and the literally-purple
`.theme-purple-gradient`/`.purple-gradient` body-class rules in
`glass-theme.css` are dead code (no template ever applies either class to
`<body>`) — no fix needed there. Left `home.css`'s indigo hero-badge accent
(`rgba(99, 102, 241, ...)`) untouched — confirmed intentional, not a
leftover from the old amber/brown palette. Design:
`specs/2026-06-19-phase5a-coldsteel-remaining-literals-design.md`.
Next: the dead `glass-theme.css` body-class rules are a candidate
follow-up (need to confirm they're also unused on `admin_themes.html`
before removing), and Phase 4 (combat visuals) remains deferred pending
live user availability for its visual judgment calls.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 5a (remaining Cold Steel literals) done"
```
