# Phase 2 — Hub/Dashboard Visual Hierarchy Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove leftover dead CSS variables and convert `theme.css`'s remaining
hardcoded amber/brown color literals to the Cold Steel namespace, plus small
spacing/contrast polish on character cards and panels — no layout or markup
changes.

**Architecture:** `dashboard.css` loses an unused variable block. `theme.css`'s
48 embedded `rgba()` literals (6 distinct old-palette RGB triples) are converted
to `color-mix(in srgb, var(--dungeon-X) N%, transparent)` expressions, preserving
each rule's original alpha — a mechanical, alpha-preserving color-source swap.
Two small spacing/opacity tweaks finish the polish pass.

**Tech Stack:** Plain CSS (`color-mix()`, already used elsewhere in this
codebase's `app.css`/`glass-theme.css`). No new dependencies.

## Global Constraints

- No template, JS, or backend changes — CSS-only.
- `--dungeon-*`/`--adv-*` aliases (from Phase 1) must keep resolving correctly;
  this phase only changes how `theme.css`'s component rules *reference* color,
  not the alias definitions themselves.
- Per-class badge colors (`.fighter-badge`, `.rogue-badge`, `.mage-badge`,
  `.cleric-badge`, `.ranger-badge`, `.druid-badge`) are explicitly out of scope —
  do not touch them.
- The 6 RGB-triple-to-alias mapping (exact, from the spec):
  - `rgb(13, 10, 10)` → `var(--dungeon-bg)`
  - `rgb(26, 21, 18)` → `var(--dungeon-panel)`
  - `rgb(18, 15, 13)` → `var(--dungeon-bg)`
  - `rgb(61, 50, 38)` → `var(--dungeon-border)`
  - `rgb(40, 33, 26)` → `var(--dungeon-panel)`
  - `rgb(212, 165, 116)` → `var(--dungeon-accent)`

---

### Task 1: Remove dead `--mud-*` variable block from `dashboard.css`

**Files:**
- Modify: `app/static/css/dashboard.css:4-12`

**Interfaces:**
- Produces: nothing consumed elsewhere — this is pure dead-code removal,
  confirmed zero consumers exist anywhere in the codebase.

- [ ] **Step 1: Confirm zero consumers exist before deleting**

Run:
```bash
grep -rn "mud-orange\|mud-grey\|mud-purple\|mud-dark\|mud-olive\|mud-bg" app/templates/*.html app/static/js/*.js app/static/css/dashboard.css
```
Expected: matches only within `app/static/css/dashboard.css` itself (the
definitions about to be deleted) — no template or JS file references any
`--mud-*` variable or a class built from one.

- [ ] **Step 2: Delete the dead block**

In `app/static/css/dashboard.css`, delete this entire block (currently lines 4-12):
```css
:root {
    --mud-orange: #BA5624;
    --mud-grey: #C0C5C1;
    --mud-purple: #6C3A5C;
    --mud-dark: #153131;
    --mud-olive: #6F732F;
    --mud-bg: #10191a;
    --mud-bg-dark: #153131;
}

```
After deletion, the file should start directly with the `/* dashboard.css:
Dashboard-specific styles */` / `/* Glass theme imported via base template */`
comment lines, followed immediately by:
```css
/* Background applied by theme system */
body {
    min-height: 100vh;
    color: #fff;
}
```

- [ ] **Step 3: Verify the file is otherwise unchanged**

Run: `git diff app/static/css/dashboard.css`
Expected: only the `:root { ... }` block (and its trailing blank line) appears
as removed — no other lines touched.

- [ ] **Step 4: Commit**

```bash
git add app/static/css/dashboard.css
git commit -m "chore(theme): remove dead --mud-* variable block from dashboard.css"
```

---

### Task 2: Convert `theme.css`'s embedded color literals to `color-mix()`

**Files:**
- Modify: `app/static/css/theme.css` (48 occurrences across the file)
- Test: manual grep verification (no CSS unit test framework in this repo)

**Interfaces:**
- Consumes: `--dungeon-bg`, `--dungeon-panel`, `--dungeon-border`,
  `--dungeon-accent` (all defined in Task 1 of the already-merged Phase 1 plan,
  in `theme.css`'s `:root` block — unchanged by this task).
- Produces: no new interface — every occurrence of the 6 old RGB triples
  becomes a `color-mix()` expression referencing an existing alias, with the
  exact same alpha value preserved.

- [ ] **Step 1: Write and run the conversion script**

This is a mechanical, alpha-preserving substitution across 48 occurrences of 6
distinct RGB triples — doing it via a small Python script is far less
error-prone than 48 manual edits. Create a temporary script (not committed —
delete it after running):

```python
# /tmp/convert_theme_colors.py
import re

PATH = "app/static/css/theme.css"

MAPPING = {
    (13, 10, 10): "--dungeon-bg",
    (26, 21, 18): "--dungeon-panel",
    (18, 15, 13): "--dungeon-bg",
    (61, 50, 38): "--dungeon-border",
    (40, 33, 26): "--dungeon-panel",
    (212, 165, 116): "--dungeon-accent",
}

def fmt_pct(alpha_str: str) -> str:
    pct = float(alpha_str) * 100
    if pct == int(pct):
        return str(int(pct))
    return str(pct)

def replace(match: re.Match) -> str:
    r, g, b, alpha = match.groups()
    key = (int(r), int(g), int(b))
    var_name = MAPPING[key]
    return f"color-mix(in srgb, var({var_name}) {fmt_pct(alpha)}%, transparent)"

pattern = re.compile(
    r"rgba\((\d+), (\d+), (\d+), ([\d.]+)\)"
)

with open(PATH) as f:
    content = f.read()

new_content, count = pattern.subn(replace, content)

with open(PATH, "w") as f:
    f.write(new_content)

print(f"Replaced {count} occurrences")
```

Run: `.venv/bin/python /tmp/convert_theme_colors.py`
Expected output: `Replaced 48 occurrences`

- [ ] **Step 2: Verify zero old-literal occurrences remain**

Run:
```bash
grep -c "rgba(13, 10, 10\|rgba(26, 21, 18\|rgba(18, 15, 13\|rgba(61, 50, 38\|rgba(40, 33, 26\|rgba(212, 165, 116" app/static/css/theme.css
```
Expected: `0` (or the command exits non-zero with no output, depending on your
shell's grep — either way, no matches).

- [ ] **Step 3: Verify the per-class badge rules were NOT touched**

Run: `grep -n "fighter-badge\|rogue-badge\|mage-badge" -A2 app/static/css/theme.css | head -15`
Expected: these rules still show their own distinct hardcoded hex/rgba values
(e.g. `rgba(139, 46, 46, 0.25)` for `.fighter-badge`), unchanged — the script's
`MAPPING` dict only matches the 6 specific RGB triples from the Global
Constraints table, so unrelated literals were never touched. Confirm this by
inspection.

- [ ] **Step 4: Spot-check 3 converted rules render the expected expression**

Run: `grep -n "color-mix" app/static/css/theme.css | head -10`
Expected output includes lines matching this shape (exact percentages will vary
per original alpha):
```
    background: linear-gradient(135deg, color-mix(in srgb, var(--dungeon-panel) 95%, transparent), color-mix(in srgb, var(--dungeon-bg) 98%, transparent));
```
and
```
        inset 0 1px 0 color-mix(in srgb, var(--dungeon-accent) 10%, transparent);
```
Confirm the percentages match each rule's original alpha (e.g. original `0.95`
→ `95%`, original `0.1` → `10%`).

- [ ] **Step 5: Delete the temporary conversion script**

Run: `rm /tmp/convert_theme_colors.py`
(It was a one-off tool, not part of the codebase — do not commit it.)

- [ ] **Step 6: Commit**

```bash
git add app/static/css/theme.css
git commit -m "feat(theme): convert theme.css's embedded color literals to color-mix() on the Cold Steel namespace"
```

---

### Task 3: Hierarchy polish — stat grid spacing and panel header contrast

**Files:**
- Modify: `app/static/css/theme.css:408-421` (`.stat-grid` and `.stat-grid div`)
- Modify: `app/static/css/theme.css` (`.panel-header` rule, now using
  `color-mix()` after Task 2 — find it via `grep -n "^.panel-header {" -A5
  app/static/css/theme.css`)

**Interfaces:**
- Consumes: the `color-mix()` conversion from Task 2 (this task edits the
  *already-converted* `.panel-header` rule, not the old literal).

- [ ] **Step 1: Tighten `.stat-grid` spacing**

Replace (currently, per the spec, at original lines 408-414 — confirm via
`grep -n "^.stat-grid {" -A6 app/static/css/theme.css` since Task 1/2 may have
shifted line numbers slightly):
```css
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    font-size: 0.85rem;
    font-family: var(--ui-font);
}
```
with:
```css
.stat-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    font-size: 0.85rem;
    font-family: var(--ui-font);
}
```

- [ ] **Step 2: Tighten `.stat-grid div` cell padding**

Replace (find via `grep -n "^.stat-grid div {" -A5 app/static/css/theme.css`):
```css
.stat-grid div {
    padding: 6px;
    background: color-mix(in srgb, var(--dungeon-bg) 60%, transparent);
    border: 1px solid color-mix(in srgb, var(--dungeon-border) 40%, transparent);
    text-align: center;
}
```
with:
```css
.stat-grid div {
    padding: 8px 6px;
    background: color-mix(in srgb, var(--dungeon-bg) 60%, transparent);
    border: 1px solid color-mix(in srgb, var(--dungeon-border) 40%, transparent);
    text-align: center;
}
```
(Only the `padding` value changes from `6px` to `8px 6px` — the
`background`/`border` lines shown here reflect Task 2's already-applied
`color-mix()` conversion of what was previously `rgba(13, 10, 10, 0.6)` and
`rgba(61, 50, 38, 0.4)`; if Task 2's exact percentages differ slightly from
`60%`/`40%` as written here due to floating-point formatting, keep whatever
Task 2 actually produced — only edit the `padding` line in this step.)

- [ ] **Step 3: Bump `.panel-header`'s background opacity one step**

Find the rule via `grep -n "^.panel-header {" -A5 app/static/css/theme.css`. It
should read (after Task 2's conversion):
```css
.panel-header {
    background: color-mix(in srgb, var(--dungeon-border) 30%, transparent);
    border-bottom: 2px solid var(--dungeon-border);
    padding: 14px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
```
Change only the `background` line's percentage from `30%` to `35%`:
```css
.panel-header {
    background: color-mix(in srgb, var(--dungeon-border) 35%, transparent);
    border-bottom: 2px solid var(--dungeon-border);
    padding: 14px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
```

- [ ] **Step 4: Commit**

```bash
git add app/static/css/theme.css
git commit -m "feat(theme): tighten stat-grid spacing and bump panel-header contrast"
```

---

### Task 4: End-to-end visual verification and TODO update

**Files:**
- Modify: `docs/superpowers/TODO.md`
- Test: manual, via real browser screenshots (Playwright, as used for Phase 1's
  final verification)

**Interfaces:**
- Consumes: all of Tasks 1-3.
- Produces: nothing new — closing verification + documentation task.

- [ ] **Step 1: Run the full backend test suite to confirm no regressions**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py --deselect tests/test_gear_party_payload.py::test_payload_reflects_gear_hp
```
Expected: all tests pass (the second deselect is a confirmed pre-existing
failure unrelated to any UI-redesign work, found during Phase 1's merge — not
introduced by this phase). This phase makes no backend changes, so the suite
should be unaffected either way.

- [ ] **Step 2: Launch the dev server and take real browser screenshots**

Use a Playwright install available on the host (as used for Phase 1's
verification) to screenshot `/login` and `/dashboard` (logged in as a fresh
throwaway test account, per the same registration approach used in Phase 1's
verification — register via curl, inject the session cookie into a Playwright
browser context, navigate, screenshot). Confirm:
- Character cards (`.operative-card`), panel headers, and the stat grid show
  only teal/charcoal tones with zero amber/brown tint anywhere, including on
  the `.selected` card state and any visible hover-adjacent styling.
- The stat grid reads slightly denser/tighter than before (smaller `gap`,
  taller cell padding).
- Panel headers show a visibly distinct band from the body content below them.
- Primary action buttons (Enter Dungeon / Hire Adventurer) still read clearly
  more prominent than secondary ones.

Clean up the throwaway test account afterward (delete it via `python run.py
admin`'s `delete user <username>` command, after first deleting any
`DungeonInstance` rows it created, same as Phase 1's cleanup pattern, to avoid
a foreign-key constraint error on delete).

- [ ] **Step 3: Update `docs/superpowers/TODO.md`**

Add a new entry immediately after the "UI Redesign Phase 1" entry added during
Phase 1's merge (find it via `grep -n "UI Redesign Phase 1" docs/superpowers/TODO.md`),
following the same heading/checkmark convention:
```markdown
### UI Redesign Phase 2 — Hub/dashboard visual hierarchy polish ✅
Removed a dead `--mud-*` CSS variable block from `dashboard.css` (zero
consumers, confirmed via grep). Converted the last 48 hardcoded amber/brown
`rgba()` literals embedded in `theme.css`'s component rules (character cards,
panel headers, stat blocks) to `color-mix()` expressions on the Cold Steel
namespace — Phase 1 only converted `:root` variable definitions and fonts, not
these embedded literals, so faint amber tints were still leaking through on
card backgrounds/glows despite borders and text already looking correct.
Small spacing/contrast polish: tighter `.stat-grid` spacing, stronger
`.panel-header` visual separation from body content. No layout/markup
changes — deeper hub restructuring (zoned roster/merchants/hoard layout,
folding `skill-tree.js` onto the Bootstrap Modal API) deferred to a later
pass. Design: `specs/2026-06-19-phase2-hub-visual-hierarchy-design.md`.
Next: Phase 3 (Three.js dungeon view).
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 2 (hub visual hierarchy) done"
```
