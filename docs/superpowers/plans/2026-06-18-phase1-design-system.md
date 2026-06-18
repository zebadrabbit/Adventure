# Phase 1 — Design System Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragmented brown/Georgia visual identity with one consolidated
"Cold Steel" CSS palette (slate/charcoal + teal accent, sans-serif), shipped through
the existing-but-currently-disconnected `Theme` DB mechanism, with the old look
preserved as a selectable alternate theme.

**Architecture:** A new canonical `--ui-*` CSS variable namespace lives in
`theme.css`'s `:root`, with `--dungeon-*`/`--adv-*` redefined as aliases pointing at
it (zero call-site changes across the 234 existing references). `app/models/theme.py`
gains a `--ui-*` block in `to_css_variables()`. Two `Theme` rows are seeded
("Cold Steel" active, "Classic Dungeon" inactive). `base.html`, `dashboard_base.html`,
`admin_base.html`, and `combat.html` each gain a `<link>` to the already-existing
`/api/admin/themes/active/css` endpoint, wiring the admin theme-switcher to actually
affect player-facing pages for the first time.

**Tech Stack:** Flask/Jinja templates, plain CSS (no preprocessor), SQLAlchemy,
pytest. No new dependencies.

## Global Constraints

- No new web fonts — typography uses the system sans-serif stack
  (`'Segoe UI', system-ui, -apple-system, sans-serif`) only.
- No `Theme` model migration — only existing columns are used (mapping: `primary`,
  `secondary`, `success`, `danger`, `warning`, `info`, `light`, `dark`, `body_bg`,
  `body_color`, `border_color`, `card_bg`).
- `--dungeon-*` and `--adv-*` variable names must keep working unchanged at every
  existing call site (234 references across templates/JS) — they become aliases,
  not removals.
- No layout/markup changes, no new icons — pure CSS variables, typography, and
  `Theme`-DB/template wiring.
- `tactical-theme.css` is confirmed dead (not `<link>`ed from any template) — leave
  it untouched; out of scope.

---

### Task 1: Add the `--ui-*` namespace and aliases to `theme.css`

**Files:**
- Modify: `app/static/css/theme.css:24-35` (the `:root` block) and `:41-51` (the
  `body` rule)
- Test: manual only (CSS has no unit test framework in this repo)

**Interfaces:**
- Produces: `--ui-bg`, `--ui-panel`, `--ui-elevated`, `--ui-accent`,
  `--ui-accent-hover`, `--ui-danger`, `--ui-success`, `--ui-warning`, `--ui-text`,
  `--ui-text-dim` — the canonical variables every later task and later phase reads.
  `--dungeon-*`/`--adv-*` remain as variable names (now aliases) for existing
  consumers.

- [ ] **Step 1: Replace the `:root` block**

Replace `app/static/css/theme.css` lines 24-35 (currently):
```css
:root {
    --dungeon-bg: #0d0a0a;
    --dungeon-panel: #1a1512;
    --dungeon-border: #3d3226;
    --dungeon-accent: #d4a574;
    --dungeon-danger: #8b2e2e;
    --dungeon-success: #4a6741;
    --dungeon-warn: #c17a3a;
    --dungeon-text: #d4c5b0;
    --dungeon-text-dim: #8a7d6f;
    --parchment-texture: url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23noise)' opacity='0.05'/%3E%3C/svg%3E");
}
```

with:
```css
:root {
    /* Canonical "Cold Steel" namespace — the single source of truth.
       --dungeon-* / --adv-* below are aliases for existing call sites. */
    --ui-bg: #0c0e12;
    --ui-panel: #1b1f27;
    --ui-elevated: #2e3440;
    --ui-accent: #5ad1c9;
    --ui-accent-hover: #7adbd4;
    --ui-danger: #c0392b;
    --ui-success: #4caf82;
    --ui-warning: #d6a23a;
    --ui-text: #dfe4ea;
    --ui-text-dim: #8d97a3;
    --ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;

    --dungeon-bg: var(--ui-bg);
    --dungeon-panel: var(--ui-panel);
    --dungeon-border: var(--ui-elevated);
    --dungeon-accent: var(--ui-accent);
    --dungeon-danger: var(--ui-danger);
    --dungeon-success: var(--ui-success);
    --dungeon-warn: var(--ui-warning);
    --dungeon-text: var(--ui-text);
    --dungeon-text-dim: var(--ui-text-dim);

    --adv-primary: var(--ui-accent);
    --adv-primary-hover: var(--ui-accent-hover);
    --adv-secondary: var(--ui-elevated);
    --adv-success: var(--ui-success);
    --adv-danger: var(--ui-danger);
    --adv-warning: var(--ui-warning);
    --adv-link-color: var(--ui-accent);
    --adv-link-hover-color: var(--ui-accent-hover);
}
```
(`--parchment-texture` is dropped — it was only ever used inside the `body` rule
being replaced in Step 2, confirm with `grep -rn "parchment-texture" app/` returning
only `theme.css` before deleting it.)

- [ ] **Step 2: Update the `body` rule to drop the parchment background and serif font**

Replace `app/static/css/theme.css` lines 41-51 (currently):
```css
body {
    background: var(--dungeon-bg);
    background-image:
        linear-gradient(rgba(13, 10, 10, 0.8), rgba(20, 15, 12, 0.9)),
        radial-gradient(ellipse at 50% 0%, rgba(61, 50, 38, 0.2) 0%, transparent 60%),
        var(--parchment-texture);
    background-size: cover, cover, 100px 100px;
    min-height: 100vh;
    color: var(--dungeon-text);
    font-family: Georgia, 'Times New Roman', serif;
}
```

with:
```css
body {
    background: var(--ui-bg);
    min-height: 100vh;
    color: var(--ui-text);
    font-family: var(--ui-font);
}
```

- [ ] **Step 3: Verify by grep that no other file references `--parchment-texture`**

Run: `grep -rn "parchment-texture" app/`
Expected: only match is the (now-removed) line in `theme.css` — i.e. no output, or
only matches you already accounted for in Step 1's removal.

- [ ] **Step 4: Commit**

```bash
git add app/static/css/theme.css
git commit -m "feat(theme): introduce canonical --ui-* Cold Steel namespace"
```

---

### Task 2: Replace remaining `Georgia`/`'Trebuchet MS'` font declarations in `theme.css` and `tactical-theme.css`

**Files:**
- Modify: `app/static/css/theme.css` (all remaining `font-family: Georgia...` /
  `font-family: 'Trebuchet MS'...` declarations outside the `body` rule already
  handled in Task 1)
- Modify: `app/static/css/tactical-theme.css` (same patterns — confirmed dead/unused
  by any template, but still worth keeping internally consistent since it shares
  the `--dungeon-*` namespace and could be re-linked later)

**Interfaces:**
- Consumes: `--ui-font` from Task 1.
- Produces: no new interface — this task only removes leftover serif/mixed-font
  declarations so `--ui-font` is the only font-family in play within these two files.

- [ ] **Step 1: Confirm the exact set of declarations to replace**

Run: `grep -n "font-family: Georgia\|font-family: 'Trebuchet MS'" app/static/css/theme.css app/static/css/tactical-theme.css`

Expected output (line numbers may shift slightly if Task 1 changed line counts in
`theme.css`, but the set of distinct declaration strings is exactly these two):
```
font-family: Georgia, serif;
font-family: 'Trebuchet MS', sans-serif;
```
(plus the one `Georgia, 'Times New Roman', serif` variant already removed in Task 1
for `theme.css`'s `body` — `tactical-theme.css` has its own copy of that exact same
`body` rule at its own line ~30, which Step 2 below also fixes.)

- [ ] **Step 2: Replace every occurrence in both files**

Run (exact, idempotent — safe to re-run):
```bash
sed -i \
  -e "s/font-family: Georgia, 'Times New Roman', serif;/font-family: var(--ui-font);/g" \
  -e "s/font-family: Georgia, serif;/font-family: var(--ui-font);/g" \
  -e "s/font-family: 'Trebuchet MS', sans-serif;/font-family: var(--ui-font);/g" \
  app/static/css/theme.css app/static/css/tactical-theme.css
```

- [ ] **Step 3: Verify no Georgia/Trebuchet references remain**

Run: `grep -n "Georgia\|Trebuchet" app/static/css/theme.css app/static/css/tactical-theme.css`
Expected: no output.

- [ ] **Step 4: Add the same canonical `:root` block to `tactical-theme.css` for consistency**

`tactical-theme.css` has its own duplicate `:root` block (lines 4-14) with the
*same* hardcoded values `theme.css` used to have. Replace it (the block starting
`:root {` through its closing `}`, currently `--dungeon-bg: #0d0a0a;` ...
`--dungeon-text-dim: #8a7d6f;`) with:
```css
:root {
    --ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --dungeon-bg: var(--ui-bg, #0c0e12);
    --dungeon-panel: var(--ui-panel, #1b1f27);
    --dungeon-border: var(--ui-elevated, #2e3440);
    --dungeon-accent: var(--ui-accent, #5ad1c9);
    --dungeon-danger: var(--ui-danger, #c0392b);
    --dungeon-success: var(--ui-success, #4caf82);
    --dungeon-warn: var(--ui-warning, #d6a23a);
    --dungeon-text: var(--ui-text, #dfe4ea);
    --dungeon-text-dim: var(--ui-text-dim, #8d97a3);
}
```
(Uses `var(--ui-x, fallback)` rather than a bare `var(--ui-x)` because this file is
not currently `<link>`ed anywhere — if it's ever reintroduced standalone without
`theme.css` also loaded, the fallback keeps it from going invisible/transparent.)

- [ ] **Step 5: Commit**

```bash
git add app/static/css/theme.css app/static/css/tactical-theme.css
git commit -m "feat(theme): unify typography on --ui-font, drop Georgia/Trebuchet"
```

---

### Task 3: Point `app.css`'s `--adv-*` definitions and `glass-theme.css` at the canonical namespace

**Files:**
- Modify: `app/static/css/app.css:31-59` (the `:root` block defining `--adv-*` with
  its own hardcoded hex, duplicating what `theme.css` now defines)
- Test: manual

**Interfaces:**
- Consumes: `--ui-*` from Task 1 (CSS custom property resolution is cascade-order
  independent across stylesheets — `app.css`'s `:root` rule referencing
  `var(--ui-accent)` resolves correctly regardless of whether `app.css` or
  `theme.css` loads first, as long as both apply to the same `:root` element, which
  they do in every template that includes both).
- Produces: no new interface — eliminates the second, independently-hardcoded copy
  of the `--adv-*` palette so there is exactly one source of truth.

- [ ] **Step 1: Read the current block to confirm exact text before editing**

Run: `sed -n '31,60p' app/static/css/app.css`

Expected to see (already confirmed during planning):
```css
:root {
  --adv-bg: #0d0a0a;
  --adv-bg-secondary: #1a1512;
  --adv-surface: #1a1512;
  --adv-surface-hover: #26211c;

  --adv-primary: #d4a574;
  --adv-primary-hover: #e8c9a0;
  --adv-secondary: #c17a3a;
  --adv-accent: #8b6f47;
  --adv-success: #4a6741;
  --adv-warning: #c17a3a;
  --adv-danger: #8b2e2e;

  --adv-text: #d4c5b0;
  --adv-text-muted: #a89c8a;
  --adv-text-dim: #8a7d6f;

  --adv-border: rgba(61, 50, 38, 0.5);
  --adv-border-hover: rgba(212, 165, 116, 0.3);

  --adv-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
  --adv-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --adv-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
}
```
If the file differs from this (e.g. already edited), stop and re-read the live file
rather than applying Step 2 blind.

- [ ] **Step 2: Replace the color values with `--ui-*` references**

Replace the block from Step 1 with:
```css
:root {
  --adv-bg: var(--ui-bg);
  --adv-bg-secondary: var(--ui-panel);
  --adv-surface: var(--ui-panel);
  --adv-surface-hover: var(--ui-elevated);

  --adv-primary: var(--ui-accent);
  --adv-primary-hover: var(--ui-accent-hover);
  --adv-secondary: var(--ui-elevated);
  --adv-accent: var(--ui-accent);
  --adv-success: var(--ui-success);
  --adv-warning: var(--ui-warning);
  --adv-danger: var(--ui-danger);

  --adv-text: var(--ui-text);
  --adv-text-muted: var(--ui-text-dim);
  --adv-text-dim: var(--ui-text-dim);

  --adv-border: var(--ui-elevated);
  --adv-border-hover: var(--ui-accent);

  --adv-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
  --adv-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --adv-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
}
```
(Shadows are pure black-alpha values, not part of the named palette — left as-is.)

- [ ] **Step 3: Replace `--adv-*` redefinitions further down in the same file, if any**

Run: `grep -n "^\s*--adv-" app/static/css/app.css`
Expected: only the block just edited in Step 2 (lines 31-59-ish) defines these — if
the grep shows a second `:root` block redefining any `--adv-*` name later in the
file, apply the same `var(--ui-*)` substitution there too, using the same mapping
table from Step 2.

- [ ] **Step 4: Replace any literal Georgia/serif font-family in `app.css`**

Run: `grep -n "Georgia\|serif\|Trebuchet" app/static/css/app.css`
Expected (confirmed during planning): no output — `app.css` does not declare any
serif font today. If this grep does return a match (file changed since planning),
replace it with `var(--ui-font)` following the same pattern as Task 2.

- [ ] **Step 5: Commit**

```bash
git add app/static/css/app.css
git commit -m "feat(theme): point app.css's --adv-* palette at canonical --ui-* vars"
```

---

### Task 4: Extend `Theme.to_css_variables()` to emit the `--ui-*` block

**Files:**
- Modify: `app/models/theme.py:101-168` (`to_css_variables` method)
- Test: `tests/test_theme_css_variables.py` (new file)

**Interfaces:**
- Consumes: `Theme` model's existing columns (`primary`, `secondary`, `success`,
  `danger`, `warning`, `body_bg`, `body_color`, `border_color`, `card_bg`).
- Produces: `to_css_variables()` now also emits `--ui-bg`, `--ui-panel`,
  `--ui-elevated`, `--ui-accent`, `--ui-accent-hover`, `--ui-danger`, `--ui-success`,
  `--ui-warning`, `--ui-text`, `--ui-text-dim`, `--ui-font` inside the same `:root {}`
  block the method already returns — read by Task 6's template wiring once that's
  added.

- [ ] **Step 1: Write the failing test**

Create `tests/test_theme_css_variables.py`:
```python
from app.models.theme import Theme


def test_to_css_variables_includes_ui_namespace():
    theme = Theme(
        name="Cold Steel Test",
        primary="#5ad1c9",
        secondary="#2e3440",
        success="#4caf82",
        danger="#c0392b",
        warning="#d6a23a",
        info="#5ad1c9",
        light="#dfe4ea",
        dark="#0c0e12",
        body_bg="#0c0e12",
        body_color="#dfe4ea",
        link_color="#5ad1c9",
        link_hover_color="#7adbd4",
        border_color="#2e3440",
        card_bg="#1b1f27",
        card_opacity=1.0,
        gradient_angle=135,
        gradient_start="#0c0e12",
        gradient_end="#1b1f27",
    )

    css = theme.to_css_variables()

    assert "--ui-bg: #0c0e12;" in css
    assert "--ui-panel: #1b1f27;" in css
    assert "--ui-elevated: #2e3440;" in css
    assert "--ui-accent: #5ad1c9;" in css
    assert "--ui-danger: #c0392b;" in css
    assert "--ui-success: #4caf82;" in css
    assert "--ui-warning: #d6a23a;" in css
    assert "--ui-text: #dfe4ea;" in css
    assert "--ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;" in css
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_theme_css_variables.py -v`
Expected: FAIL — `assert "--ui-bg: #0c0e12;" in css` fails because `to_css_variables()`
doesn't emit it yet.

- [ ] **Step 3: Extend `to_css_variables()`**

In `app/models/theme.py`, inside `to_css_variables` (currently builds `css` starting
with the `:root {{ ... }}` f-string at lines ~106-131), add the `--ui-*` block to the
same `:root` f-string, right after the existing `--adv-link-hover-color` line and
before the closing `}}`:

```python
    --adv-link-color: {self.link_color};
    --adv-link-hover-color: {self.link_hover_color};

    --ui-bg: {self.body_bg};
    --ui-panel: {self.card_bg};
    --ui-elevated: {self.border_color};
    --ui-accent: {self.primary};
    --ui-accent-hover: {self.secondary};
    --ui-danger: {self.danger};
    --ui-success: {self.success};
    --ui-warning: {self.warning};
    --ui-text: {self.body_color};
    --ui-text-dim: {self.light};
    --ui-font: 'Segoe UI', system-ui, -apple-system, sans-serif;
}}
```
(replacing the existing closing `}}` of that `:root` block — there is exactly one
`}}` immediately before the blank line and `body {{` that follows, per the file as
read during planning.)

- [ ] **Step 4: Run test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_theme_css_variables.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/models/theme.py tests/test_theme_css_variables.py
git commit -m "feat(theme): emit --ui-* canonical namespace from Theme.to_css_variables"
```

---

### Task 5: Seed the "Cold Steel" and "Classic Dungeon" `Theme` rows

**Files:**
- Create: `app/seed_themes.py` (mirrors `app/seed_skills.py`'s pattern)
- Modify: `run.py` (add `seed-themes` subcommand, mirroring `seed-skills`)
- Test: `tests/test_seed_themes.py` (new file)

**Interfaces:**
- Consumes: `app.models.theme.Theme` (Task 4's `to_css_variables` not directly
  needed here — this task only creates rows).
- Produces: `seed_themes(verbose: bool = True) -> int` (returns count of themes
  seeded/updated), importable as `from app.seed_themes import seed_themes`, and a
  `python run.py seed-themes` CLI command — both consumed by deployment docs (Task
  7) and usable ad hoc by an admin.

- [ ] **Step 1: Write the failing test**

Create `tests/test_seed_themes.py`:
```python
import pytest

from app import app, db
from app.models.theme import Theme
from app.seed_themes import seed_themes


@pytest.mark.db_isolation
def test_seed_themes_creates_cold_steel_and_classic_dungeon():
    with app.app_context():
        count = seed_themes(verbose=False)
        assert count == 2

        cold_steel = Theme.query.filter_by(name="Cold Steel").first()
        assert cold_steel is not None
        assert cold_steel.is_active is True
        assert cold_steel.primary == "#5ad1c9"
        assert cold_steel.body_bg == "#0c0e12"

        classic = Theme.query.filter_by(name="Classic Dungeon").first()
        assert classic is not None
        assert classic.is_active is False
        assert classic.primary == "#d4a574"


@pytest.mark.db_isolation
def test_seed_themes_is_idempotent():
    with app.app_context():
        seed_themes(verbose=False)
        first_count = Theme.query.count()
        seed_themes(verbose=False)
        second_count = Theme.query.count()
        assert first_count == second_count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_seed_themes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.seed_themes'`

- [ ] **Step 3: Create `app/seed_themes.py`**

```python
"""Programmatic, idempotent seeding of the Cold Steel and Classic Dungeon themes.

Like app/seed_skills.py, this seeds via the ORM so the Theme-driven design system
(Phase 1 of the UI redesign) has real data from a fresh database. Idempotent:
themes are upserted by name. Activating "Cold Steel" deactivates every other theme
first, matching the same exclusivity rule the admin "activate" endpoint enforces
(app/routes/theme_api.py).

Usage:
    from app.seed_themes import seed_themes
    seed_themes()

CLI:
    python run.py seed-themes
"""

from __future__ import annotations

from app import app as flask_app
from app import db
from app.models.theme import Theme

THEMES = [
    {
        "name": "Cold Steel",
        "description": "Slate/charcoal hub with a teal accent — the default look.",
        "primary": "#5ad1c9",
        "secondary": "#2e3440",
        "success": "#4caf82",
        "danger": "#c0392b",
        "warning": "#d6a23a",
        "info": "#5ad1c9",
        "light": "#dfe4ea",
        "dark": "#0c0e12",
        "body_bg": "#0c0e12",
        "body_color": "#dfe4ea",
        "link_color": "#5ad1c9",
        "link_hover_color": "#7adbd4",
        "border_color": "#2e3440",
        "card_bg": "#1b1f27",
        "card_opacity": 1.0,
        "gradient_angle": 135,
        "gradient_start": "#0c0e12",
        "gradient_end": "#1b1f27",
        "is_active": True,
    },
    {
        "name": "Classic Dungeon",
        "description": "The original warm-brown medieval palette, preserved as an alt theme.",
        "primary": "#d4a574",
        "secondary": "#c17a3a",
        "success": "#4a6741",
        "danger": "#8b2e2e",
        "warning": "#c17a3a",
        "info": "#8b6f47",
        "light": "#d4c5b0",
        "dark": "#0d0a0a",
        "body_bg": "#0d0a0a",
        "body_color": "#d4c5b0",
        "link_color": "#d4a574",
        "link_hover_color": "#e8c9a0",
        "border_color": "#3d3226",
        "card_bg": "#1a1512",
        "card_opacity": 1.0,
        "gradient_angle": 135,
        "gradient_start": "#0d0a0a",
        "gradient_end": "#1a1512",
        "is_active": False,
    },
]


def seed_themes(verbose: bool = True) -> int:
    """Create or update the Cold Steel and Classic Dungeon themes. Returns count.

    Idempotent: themes are upserted by name. If a theme in THEMES is marked
    is_active=True, every other theme row (seeded or not) is deactivated first,
    so there is never more than one active theme after this runs.
    """
    with flask_app.app_context():
        count = 0
        for spec in THEMES:
            theme = Theme.query.filter_by(name=spec["name"]).first()
            if not theme:
                theme = Theme(name=spec["name"])
                db.session.add(theme)
            for key, value in spec.items():
                if key != "is_active":
                    setattr(theme, key, value)
            count += 1

        db.session.flush()

        for spec in THEMES:
            if spec.get("is_active"):
                Theme.query.update({"is_active": False})
                theme = Theme.query.filter_by(name=spec["name"]).first()
                theme.is_active = True

        db.session.commit()
        if verbose:
            print(f"[seed-themes] {count} themes seeded.")
        return count


__all__ = ["seed_themes"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_seed_themes.py -v`
Expected: PASS

- [ ] **Step 5: Wire the `seed-themes` CLI subcommand**

In `run.py`, immediately after the existing `seed-skills` subparser block (the one
ending in `seed_skills_parser.set_defaults(command="seed-skills")`), add:
```python
    # seed-themes subcommand
    seed_themes_parser = subparsers.add_parser(
        "seed-themes",
        help="Create/update the Cold Steel and Classic Dungeon themes (idempotent)",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Seed the Phase 1 design-system themes via the ORM. Safe to run repeatedly.",
    )
    seed_themes_parser.set_defaults(command="seed-themes")
```

And immediately after the existing `elif mode == "seed-skills":` block (the one
calling `seed_skills(verbose=True)` then `return 0`), add:
```python
    elif mode == "seed-themes":
        from app.seed_themes import seed_themes

        seed_themes(verbose=True)
        return 0
```

- [ ] **Step 6: Manually verify the CLI command runs against the dev DB**

Run: `.venv/bin/python run.py seed-themes`
Expected output: `[seed-themes] 2 themes seeded.` with exit code 0.

- [ ] **Step 7: Commit**

```bash
git add app/seed_themes.py tests/test_seed_themes.py run.py
git commit -m "feat(theme): seed Cold Steel (active) and Classic Dungeon themes"
```

---

### Task 6: Wire `GET /api/admin/themes/active/css` into the player-facing templates

**Files:**
- Modify: `app/templates/base.html` (after the existing `theme.css` `<link>`,
  around line 11)
- Modify: `app/templates/dashboard_base.html`
- Modify: `app/templates/admin_base.html` (after the `glass-theme.css` `<link>`)
- Modify: `app/templates/combat.html` (after the `glass-theme.css` `<link>`)
- Test: manual (no template-rendering test harness for `<head>` contents exists in
  this repo today — verified via the `run`/`verify` skills per the spec's testing
  section)

**Interfaces:**
- Consumes: the existing `theme.get_active_theme_css` Flask endpoint
  (`app/routes/theme_api.py:232`, route `/api/admin/themes/active/css`, no auth
  required — confirmed during brainstorming).
- Produces: every page that extends these four base templates now has the active
  `Theme` row's CSS applied last (highest cascade priority among same-specificity
  rules), so toggling the active theme in the admin panel has real, immediate
  effect on player-facing pages.

- [ ] **Step 1: Read each file's current theme-related `<link>` lines to confirm exact text**

Run:
```bash
grep -n "theme.css\|glass-theme.css" app/templates/base.html app/templates/dashboard_base.html app/templates/admin_base.html app/templates/combat.html
```
Expected (confirmed during planning): `base.html:11` has `theme.css`,
`admin_base.html:6` and `combat.html:135` have `glass-theme.css`,
`dashboard_base.html` extends `base.html` (no direct theme link of its own — confirm
this with `grep -n "extends" app/templates/dashboard_base.html`; if it does extend
`base.html`, skip editing it directly in Step 2 below, since it inherits `base.html`'s
`<head>`).

- [ ] **Step 2: Add the `Theme`-CSS link to `base.html`**

In `app/templates/base.html`, immediately after the line:
```html
  <link rel="stylesheet" href="{{ asset_url('css/theme.css') }}">
```
add:
```html
  <link rel="stylesheet" href="{{ url_for('theme.get_active_theme_css') }}">
```

- [ ] **Step 3: Add the same link to `admin_base.html` and `combat.html`**

In `app/templates/admin_base.html`, immediately after:
```html
<link rel="stylesheet" href="{{ asset_url('css/glass-theme.css') }}">
```
add:
```html
<link rel="stylesheet" href="{{ url_for('theme.get_active_theme_css') }}">
```

Apply the identical addition in `app/templates/combat.html` immediately after its
own `glass-theme.css` link (line 135 per planning-time read).

- [ ] **Step 4: Handle `dashboard_base.html` per Step 1's finding**

If Step 1 confirmed `dashboard_base.html` extends `base.html` (inherits its
`<head>`), no edit is needed here — skip this step. If it does NOT extend
`base.html` (renders its own independent `<head>`), add the same
`<link rel="stylesheet" href="{{ url_for('theme.get_active_theme_css') }}">` line
after whichever theme-related stylesheet it links directly.

- [ ] **Step 5: Manually verify via the `run` skill**

Use the `run` skill to launch the dev server, then load `/dashboard` (or
`/adventure`) in a browser and confirm via devtools' Network tab that a request to
`/api/admin/themes/active/css` returns `200` with `Content-Type: text/css` and a
body containing `--ui-bg: #0c0e12;` (Cold Steel's seeded value from Task 5).
Also load `/combat` and an admin page (e.g. `/admin/themes`) and confirm the same
request succeeds there.

- [ ] **Step 6: Commit**

```bash
git add app/templates/base.html app/templates/admin_base.html app/templates/combat.html
git commit -m "feat(theme): wire active-theme CSS endpoint into player-facing templates"
```

(If Task 6 Step 4 required editing `dashboard_base.html` too, `git add` that file
as well before committing.)

---

### Task 7: End-to-end manual verification and TODO update

**Files:**
- Modify: `docs/superpowers/TODO.md` (mark Phase 1 done, consistent with how Spec
  4b/5c entries were marked there previously)
- Test: manual, via the `run`/`verify` skills

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: nothing new — this is the final verification + documentation task that
  closes out Phase 1.

- [ ] **Step 1: Run the full backend test suite to confirm no regressions**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -c "from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: all tests pass (the suite was green at session start per
`docs/superpowers/TODO.md`'s "Known issues" section; this phase added 2 new test
files and touched no backend gameplay logic, so it should stay green).

- [ ] **Step 2: Seed themes on the dev DB**

Run: `.venv/bin/python run.py seed-themes`
Expected: `[seed-themes] 2 themes seeded.`

- [ ] **Step 3: Manual visual verification via `run`/`verify` skills**

Launch the dev server and, in a browser:
- Load `/dashboard`: confirm slate/charcoal background, teal accent buttons/links,
  sans-serif text throughout (no Georgia serif anywhere), zero console errors.
- Load `/adventure` and `/combat`: same palette/typography, zero console errors.
- Load `/admin/themes`: confirm both "Cold Steel" and "Classic Dungeon" appear in
  the theme list, with "Cold Steel" marked active.
- In the admin panel, activate "Classic Dungeon", then reload `/dashboard`: confirm
  the page now shows the old brown/amber/Georgia look — this confirms the
  `Theme`-DB wiring (Task 6) has real effect, not just the new default.
- Re-activate "Cold Steel" afterward so the dev DB is left in the intended default
  state.

- [ ] **Step 4: Update `docs/superpowers/TODO.md`**

Add a new entry under a "Phase 1 — UI redesign" heading (create the heading if the
"Remaining"/"Done so far" sections don't already have a slot for it), following the
existing checkmark convention used for Spec 4b/5c entries:
```markdown
### UI Redesign Phase 1 — Design system foundation ✅
Consolidated the 4 competing CSS palettes into one canonical `--ui-*` namespace
("Cold Steel": slate/charcoal + teal accent, sans-serif), with `--dungeon-*`/
`--adv-*` kept as aliases so no call site needed to change. Shipped via the
existing `Theme` DB model — seeded "Cold Steel" (active) and "Classic Dungeon"
(the old look, still selectable) via `python run.py seed-themes`. Also discovered
and fixed: the admin theme-switcher's `/api/admin/themes/active/css` endpoint was
never linked from any template — now wired into `base.html`/`admin_base.html`/
`combat.html`, so switching themes in the admin panel actually affects what
players see for the first time. Design: `specs/2026-06-18-phase1-design-system-design.md`.
Next: Phase 2 (hub/dashboard layout redesign).
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark UI redesign Phase 1 (design system) done"
```
