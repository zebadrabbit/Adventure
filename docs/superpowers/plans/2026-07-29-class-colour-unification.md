# Class Colour Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One class palette, twelve distinct hues, `tokens.css` as the only source — so a class reads the same on every screen and all twelve are styled, not six.

**Architecture:** `tokens.css` gains the twelve replacement hues and derives `-bg`, `-fg` and `-border` from each via `color-mix()`. Because consumers already read those derived names, correct colour arrives without touching them. Then the three competing sources go: an orphaned stylesheet, a six-class block in `base.css`, and a runtime injector that `!important`-overrode the token system on one screen.

**Tech Stack:** Plain CSS with custom properties, Flask/Jinja, vanilla JS, pytest.

**Spec:** [specs/2026-07-29-class-colour-unification-design.md](../specs/2026-07-29-class-colour-unification-design.md) — read it first; it carries the measurements behind the palette and the per-screen bug this fixes.

## Global Constraints

- **One token file.** `app/static/css/tokens.css`. Never open a second `:root` block.
- **No hard-coded class colour at a call site** (`DESIGN_SYSTEM.md`, "Class identity"). Every class colour derives from `--class-<name>`.
- **`--radius` is `0`; no diffuse `box-shadow`; no `!important` in static CSS.** The injector's `!important` rules are being deleted, not relocated.
- **Twelve classes, not six.** `CLASS_MAP` (`config_api.py`) is the roster: `fighter, rogue, mage, cleric, ranger, druid, barbarian, bard, monk, paladin, sorcerer, warlock`. A solution that leaves any of them unstyled has not fixed the problem.
- **Both realms.** Values derive from the hue, so a class must read the same in warm (`#0f0c09`) and cold (`#0b0d11`). Verify, don't assume.
- **Contrast floor 4.5:1** for any class colour used as text or as a border carrying meaning.

## The palette

Solved numerically; every hue clears 5.40:1 against both grounds and no pair is close in both hue and lightness.

```css
--class-fighter:   #d1666d;  /* 356° blade red   */
--class-barbarian: #d57434;  /*  24° burnt orange */
--class-cleric:    #d8af4f;  /*  42° lamplight gold (unchanged — it is --ui-accent) */
--class-paladin:   #e0dcb3;  /*  55° pale luminous */
--class-ranger:    #82964a;  /*  76° olive        */
--class-druid:     #5dac68;  /* 128° leaf green   */
--class-monk:      #44a796;  /* 170° jade         */
--class-mage:      #5c94cc;  /* 210° steel blue (unchanged) */
--class-rogue:     #908cb5;  /* 246° slate violet, low saturation */
--class-warlock:   #b179cd;  /* 280° violet       */
--class-bard:      #c964b5;  /* 312° magenta      */
--class-sorcerer:  #d16691;  /* 336° rose         */
```

## How to run the tests

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```

Foreground, generous timeout. Baseline `880 passed, 2 skipped, 1 xpassed`. The skip count varies legitimately — `test_quest_hooks.py::test_kill_increments_daily_quest` self-skips about a third of runs (unseeded `random` in quest generation).

**Python routes do not hot-reload** — a stale server has produced false-positive checks repeatedly in this project. Confirm the server runs your code, kill it when done, never commit `adventure.pid`. **Do not use `git stash`** — there is an unrelated pre-existing stash belonging to the repo owner.

## File Structure

| File | Change | Responsible for |
|---|---|---|
| `app/static/css/tokens.css` | modify | The twelve hues, and `-bg`/`-fg`/`-border` derived from each |
| `app/static/css/classes.css` | **delete** | Orphaned — loaded by no template, and disagreeing |
| `app/static/css/base.css` | modify | Drop its six-class `--class-*-bg/-fg/-border` block |
| `app/routes/config_api.py` | modify | Drop `CLASS_COLORS` and the `/api/config/class_colors` route |
| `app/static/js/adventure.js` | modify | Drop `fetchAndApplyClassColors` |
| `tests/test_class_colour_tokens.py` | **create** | Twelve classes, one source, contrast and distinctness |

---

### Task 1: The palette and its derivations

Put all twelve hues and their derived values in `tokens.css`, so every consumer resolves correctly before anything is deleted. Nothing should look worse at the end of this task, and six classes should start looking right off `/adventure` for the first time.

**Files:**
- Modify: `app/static/css/tokens.css:233-244`
- Test: `tests/test_class_colour_tokens.py`

**Interfaces:**
- Produces, for each of the twelve classes: `--class-<name>` (the hue) plus `--class-<name>-bg`, `--class-<name>-fg`, `--class-<name>-border`, derived from it.
- Consumed by `class-badges.css`, `base.css`, `hoard.js:34`, `equipment.css`'s `.eq-class-bg-*`, and the `border-<class>` / `class-badge-<class>` markup.

- [ ] **Step 1: Write the failing test**

Create `tests/test_class_colour_tokens.py`. It parses `tokens.css` as text — no browser, no app context — so it can assert on the palette directly.

```python
"""Class colours come from one place, cover all twelve classes, and are distinct.

Before this there were five sources. `base.css` styled six classes, an orphaned
`classes.css` styled the same six with fifteen different values, and a runtime
injector (`config_api.CLASS_COLORS` -> `/api/config/class_colors` ->
`adventure.js`) `!important`-overrode both on /adventure only -- so a Fighter's
badge was #7a3314 on the dashboard and #301d0b in the dungeon, and six of the
twelve classes had no colour at all outside the dungeon.

The palette itself also failed: `bard` and `paladin` were the same hue, three
golds sat within 6 degrees, and `fighter`, `warlock` and `rogue` were below the
4.5:1 contrast floor.

Spec: docs/superpowers/specs/2026-07-29-class-colour-unification-design.md
"""

import colorsys
import itertools
import pathlib
import re

TOKENS = pathlib.Path(__file__).resolve().parents[1] / "app" / "static" / "css" / "tokens.css"

CLASSES = [
    "fighter", "rogue", "mage", "cleric", "ranger", "druid",
    "barbarian", "bard", "monk", "paladin", "sorcerer", "warlock",
]

# The two realm grounds a class colour must be legible against.
GROUNDS = {"warm": "#0f0c09", "cold": "#0b0d11"}
CONTRAST_FLOOR = 4.5


def _hues():
    text = TOKENS.read_text()
    found = dict(re.findall(r"--class-([a-z]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text))
    return {k: v for k, v in found.items() if k in CLASSES}


def _rel_luminance(hex_colour):
    parts = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    parts = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(a, b):
    hi, lo = sorted((_rel_luminance(a), _rel_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _hsl(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s * 100, l * 100


def test_every_class_has_a_hue():
    hues = _hues()
    missing = [c for c in CLASSES if c not in hues]
    assert not missing, f"no --class-* hue for: {missing}"


def test_every_class_has_derived_bg_fg_and_border():
    """Six classes used to have these and six did not, which is why a runtime
    injector existed to paper over the gap."""
    text = TOKENS.read_text()
    for name in CLASSES:
        for part in ("bg", "fg", "border"):
            assert re.search(rf"--class-{name}-{part}\s*:", text), f"--class-{name}-{part} is not defined"


def test_derived_values_reference_the_hue_rather_than_restating_a_colour():
    """A derived value that hard-codes a hex is a second source of truth."""
    text = TOKENS.read_text()
    for name in CLASSES:
        for part in ("bg", "fg", "border"):
            m = re.search(rf"--class-{name}-{part}\s*:([^;]+);", text)
            assert m, f"--class-{name}-{part} is not defined"
            value = m.group(1)
            assert f"--class-{name}" in value, f"--class-{name}-{part} must derive from --class-{name}, got:{value}"
            assert "#" not in value, f"--class-{name}-{part} hard-codes a colour:{value}"


def test_every_hue_clears_the_contrast_floor_in_both_realms():
    for name, hue in _hues().items():
        for realm, ground in GROUNDS.items():
            ratio = _contrast(hue, ground)
            assert ratio >= CONTRAST_FLOOR, f"--class-{name} is {ratio:.2f}:1 on the {realm} ground"


def test_no_two_classes_are_close_in_both_hue_and_lightness():
    """`bard` and `paladin` used to be the same hue, and three golds sat within
    six degrees. Hue alone is not the test -- two colours may share a hue if
    lightness separates them clearly, as cleric and paladin now do."""
    hues = _hues()
    collisions = []
    for a, b in itertools.combinations(sorted(hues), 2):
        ha, _, la = _hsl(hues[a])
        hb, _, lb = _hsl(hues[b])
        dh = min(abs(ha - hb), 360 - abs(ha - hb))
        dl = abs(la - lb)
        if dh < 12 and dl < 18:
            collisions.append(f"{a}/{b}: {dh:.0f} deg hue, {dl:.0f} lightness")
    assert not collisions, "indistinguishable class colours: " + "; ".join(collisions)


def test_the_runtime_injector_is_gone():
    """A palette a script rewrites at runtime is not a source of truth."""
    root = TOKENS.parents[3]
    assert not (root / "app" / "static" / "css" / "classes.css").exists(), "orphaned classes.css still present"
    assert "CLASS_COLORS" not in (root / "app" / "routes" / "config_api.py").read_text()
    assert "class_colors" not in (root / "app" / "static" / "js" / "adventure.js").read_text()
```

Note the last test will fail until Task 2 — that is intended; it is the task's own gate.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/test_class_colour_tokens.py -q
```
Expected: `test_every_class_has_a_hue` PASSES (twelve already exist); the derived-value, contrast, distinctness and injector tests FAIL.

- [ ] **Step 3: Replace the twelve hues**

In `app/static/css/tokens.css`, replace the `--class-*` block with the palette from this plan's header. Keep the existing comment's intent — one hue per class, never hard-coded at a call site — and record what changed and why: `bard`/`paladin` were the same hue, three golds sat within 6°, and three colours were below 4.5:1. Note that `cleric` and `mage` are deliberately unchanged.

- [ ] **Step 4: Derive `-bg`, `-fg` and `-border` from each hue**

Still in `tokens.css`, directly under the hues, add the three derived values for all twelve classes. They must reference `--class-<name>` and contain no hex — the test enforces both.

The shape to aim for, per class:

- `-bg`: the hue mixed well down toward the realm ground, so a badge reads as a tinted surface rather than a block of colour. `color-mix(in srgb, var(--class-<name>) 22%, var(--realm-bg))` is the starting point.
- `-fg`: the hue mixed up toward white for legible text on that background — or `var(--ink)` if that reads better. Whichever you choose, it must clear 4.5:1 against the `-bg` you produced; check it rather than assuming.
- `-border`: the hue at partial strength, e.g. `color-mix(in srgb, var(--class-<name>) 55%, transparent)`.

Follow `tokens.css`'s existing derivation style (see `--surface-raised`, `--accent-line`, `--danger-wash`) rather than inventing a new one. **Declare these where the realm tokens are already in scope** — `tokens.css` has a `[data-realm]` block precisely because a custom property that references another resolves on the element that declares it; a derivation left at `:root` would freeze at the town palette and stay warm underground.

Verify the `-fg`/`-bg` contrast for all twelve, in both realms, and put the worst figure in your report.

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_class_colour_tokens.py -q
```
Expected: everything except `test_the_runtime_injector_is_gone` PASSES.

- [ ] **Step 6: Look at it**

With a server running your code, compare a badge for each of the twelve classes on `/dashboard` (warm) and `/adventure` (cold). Six of them had no colour off `/adventure` before this task; they should now. The injector still overrides on `/adventure` at this point, so a difference between the two screens is expected until Task 2 — note what you see rather than treating it as a bug.

- [ ] **Step 7: Commit**

```bash
git add app/static/css/tokens.css tests/test_class_colour_tokens.py
git commit -m "feat(tokens): twelve distinct class hues, with bg/fg/border derived

The palette had bard and paladin on the same hue, three golds within six
degrees, and fighter, warlock and rogue below the 4.5:1 contrast floor. The
replacement is solved for spacing and contrast: every hue clears 5.40:1 against
both realm grounds and no pair is close in both hue and lightness. cleric and
mage are unchanged deliberately -- they are the warm and cold accents.

tokens.css now also derives -bg/-fg/-border from each hue for all twelve
classes. Six classes previously had those only in base.css and six had none at
all, which is why a runtime injector existed to fill the gap."
```

---

### Task 2: Delete the other four sources

**Files:**
- Delete: `app/static/css/classes.css`
- Modify: `app/static/css/base.css:34+`, `app/routes/config_api.py`, `app/static/js/adventure.js:106-148`

**Interfaces:**
- Consumes Task 1's derived tokens. Produces no new interface — this task only removes.

- [ ] **Step 1: Confirm the orphan before deleting it**

```bash
grep -rn "classes\.css" app/ docs/ --include=*.html --include=*.py --include=*.md
```
Expected: no template reference. If a doc mentions it, update the doc.

```bash
git rm app/static/css/classes.css
```

- [ ] **Step 2: Drop `base.css`'s block**

Remove the `--class-*-bg/-fg/-border` declarations from `app/static/css/base.css`. They cover six classes and are superseded by Task 1's twelve. Leave the rest of the file alone.

- [ ] **Step 3: Drop the server side**

In `app/routes/config_api.py`, remove `CLASS_COLORS` and the `/api/config/class_colors` route. **Leave `CLASS_MAP` and the class stat blocks** — they are game data, not colour.

- [ ] **Step 4: Drop the injector**

In `app/static/js/adventure.js`, remove `fetchAndApplyClassColors` (the IIFE at roughly `:112-148`) and its comment. Note what it did, so the reason it is going is legible in the commit: it set `--class-<slug>-bg/-fg/-border` on `document.documentElement` and injected a `<style>` block of `!important` rules for the six classes `base.css` did not cover — overriding the token system on one screen, and invisible to grep because the property names were built by interpolation.

- [ ] **Step 5: Verify nothing still expects the endpoint**

```bash
grep -rn "class_colors\|CLASS_COLORS\|fetchAndApplyClassColors" app/ tests/ e2e/
```
Expected: no hits.

```bash
grep -rn "class-[a-z]*-bg\|class-[a-z]*-fg\|class-[a-z]*-border" app/static app/templates
```
Expected: only *readers* — `class-badges.css`, `hoard.js`, `equipment.css`, and `tokens.css`'s own declarations. No other declaration sites.

- [ ] **Step 6: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_class_colour_tokens.py -q
.venv/bin/python -m pytest tests/ -q
```
Expected: all PASS, including `test_the_runtime_injector_is_gone`. Baseline is `880 passed, 2 skipped, 1 xpassed` plus this file's tests. Watch for tests that hit `/api/config/class_colors` — if any exist, deleting the route is what should change them, and say so.

- [ ] **Step 7: Look at it, on both screens**

All twelve classes, `/dashboard` and `/adventure`, with a browser console open. The two screens must now agree for every class — that is the bug this chunk exists to fix. Confirm no console error from the removed fetch, and check the party rail's `border-<class>` ring and the character panel's class header as well as the badges.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(css): one source for class colours

Deletes the four competing sources. classes.css was orphaned -- loaded by no
template -- and disagreed with base.css on fifteen of eighteen values.
base.css covered six of the twelve classes. And config_api.CLASS_COLORS, served
at /api/config/class_colors and applied by adventure.js, set the properties on
documentElement and injected !important rules for the other six -- overriding
the token system on /adventure alone, which is why a Fighter's badge was
#7a3314 on the dashboard and #301d0b in the dungeon.

tokens.css is now the only place a class colour is defined."
```

---

### Task 3: Record what this leaves

**Files:**
- Modify: `docs/superpowers/TODO.md`, `docs/DESIGN_SYSTEM.md`

- [ ] **Step 1: Close the TODO entry**

The "Class colours have four sources" item under *One vocabulary, four times over* becomes done — noting it was five, that one was an orphan, and that the per-screen disagreement was the visible symptom.

- [ ] **Step 2: Open what it revealed**

Class *icons* have the same six-vs-twelve gap in a different medium: `adventure.html:99-115` is a six-branch `if/elif` on `class_lower` with a letter-avatar fallback, so half the roster gets an initial instead of an icon. Record it with that code pointer.

- [ ] **Step 3: Make the design system's rule enforceable**

`DESIGN_SYSTEM.md`'s "Class identity" section says never to hard-code a class colour at a call site. Update it to state that `--class-<name>` is the hue and `-bg`/`-fg`/`-border` are derived in `tokens.css` for all twelve, and that `tests/test_class_colour_tokens.py` enforces it. A rule with a test behind it is worth more than a rule.

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: class colours unified; record the icon gap it exposed"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Twelve distinct hues, measured | 1 |
| `tokens.css` is the only source | 1 (derivations), 2 (deletions) |
| All twelve classes covered, not six | 1 |
| Contrast floor 4.5:1 in both realms | 1, enforced by test |
| `classes.css` deleted | 2 |
| `base.css` block deleted | 2 |
| `CLASS_COLORS` + route + injector deleted | 2, enforced by test |
| Consumers untouched | 1 — they read the derived names |
| Realm-correct derivation | 1, Step 4 |
| Icons out of scope, recorded | 3 |

**Type consistency:** the twelve names in the plan's palette match `CLASS_MAP`'s keys and the `CLASSES` list in the test. `--class-<name>-bg/-fg/-border` is the shape `class-badges.css` and `hoard.js:34` already read.

**Known risks:**

1. **The derivations must be declared where the realm tokens are in scope.** `tokens.css` has a `[data-realm]` block because a custom property referencing another resolves on the declaring element — a derivation left at `:root` freezes at the town palette and stays warm underground. Task 1 Step 4 says so; it is the most likely thing to get subtly wrong, and it fails visually rather than loudly.
2. **`-fg` on `-bg` contrast is not covered by a test.** The test checks each hue against the realm grounds, which is the case that was actually broken, but a badge is text on a tinted background and that pair is checked by hand in Task 1 Step 4. If a cheap way to assert it presents itself, take it.
3. **Task 1 leaves the two screens disagreeing** until Task 2 removes the injector. That is expected and stated, but it means Task 1 cannot be verified by "the screens match" — only Task 2 can.
