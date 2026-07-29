# Paper Doll Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One character panel instead of two, reachable from the party rail during a run — which is also what makes looted gear equippable in the dungeon for the first time.

**Architecture:** `equipment-enhanced.js` is promoted to a container-scoped renderer, `equipment-panel.js`, that mounts into whatever element it is handed: a Bootstrap modal body on the dashboard, a HUD panel beside the party rail on `/adventure`. `equipment.js`, `equipment-enhanced.js` and `equipment-shared.js` are deleted. The panel is restyled onto `tokens.css`, and the party frame gains the one piece of state that has to be visible before a fight rather than inside a panel: encumbrance.

**Tech Stack:** Vanilla JS (no build step, no bundler), plain CSS with custom properties, Flask + Jinja2, pytest, Playwright.

**Spec:** [specs/2026-07-28-character-panel-redesign.md](../specs/2026-07-28-character-panel-redesign.md)

**Plan 2 of 2** for the character-panel chunk. Plan 1 ([gear-slot-unification](2026-07-28-gear-slot-unification.md)) unified the slot vocabularies and is merged.

## Global Constraints

- **One token file.** `app/static/css/tokens.css`. Never open a second `:root` block.
- **Semantic tokens only.** No hard-coded hex. `--rarity-common` … `--rarity-mythic`, `--class-fighter` … `--class-warlock`, `--hp`, `--mp`, `--xp` all already exist — use them.
- **`--radius` is `0`.** Hard edges; no `border-radius` beyond the tokens, no diffuse `box-shadow`. `--elev-overlay` is permitted only for things genuinely above the page; `--inset-well` is the sunken-track shadow.
- **Page CSS styles the page, not the app.** No bare element selectors. `adventure-hud.css` has one documented exception (the account anchor, scoped `body[data-realm="dungeon"]`, because it renders in `<header>` outside `.adv-hud`).
- **No `!important` in static CSS.**
- **Terminology is styling.** Player-facing copy uses D&D register — party, roster, provisions, delve, hoard, spoils. Not "Party Stash", not "operatives".
- **The canonical gear vocabulary is the eight slots** at `app/loot/data/archetypes.py:8`: `weapon, offhand, head, chest, hands, feet, ring, amulet`. The server serves this list at `/api/characters/state` as `slots`; do not restate it as a JS literal.
- **Target floor 1366×768,** nothing essential scrolled, clipped or unreachable. Below 1200px a stacked fallback that must not overlap.
- **Panel geometry derives from `--hud-inset-left` / `--hud-inset-bottom`,** never restated pixels — `DungeonCanvas.hudInsets()` reads those and `centerOnPlayer` uses them.

## The bug this exists to fix

`equip_item` has two paths. Procedural gear instances live in `items` as dicts carrying a `uid`, and the gear-instance path triggers **only** on a `uid` in the request body. `equipment-enhanced.js:384-394` sends one — but it is loaded only by the dashboard. `equipment.js`, the sole equip path on `/adventure` (`adventure.html` loads it and never loads enhanced), posts `{slug, slot}` with no `uid` branch, so a procedural instance falls to the legacy path, which does `Item.query.filter_by(slug=...)`, finds no catalogue row for a generated slug, and returns **404 `item not found`**.

So nothing the dungeon drops can be equipped until the player extracts. Across 176 characters in the development database, every gear dict is exactly `{"weapon": "<slug>"}`.

**Task 2 is where this is fixed**, and it comes free: the panel being promoted is the one that already sends `uid`.

## How to run the tests

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```

Run pytest in the **foreground** with a generous timeout. The full suite takes about 5.5 minutes and currently reports `808 passed, 3 skipped, 1 xpassed`. `tests/test_camp_regen_buff.py` and `tests/test_camp_supplies_and_cooldown.py` have a known pre-existing flake together — if one fails, re-run it alone.

E2E needs a running server (`.venv/bin/python run.py`):

```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```

**Python routes do not hot-reload.** A stale server process has caused false-positive manual checks four times in this project. Make sure the server you test against is running your code, and kill it when done. Never commit `adventure.pid`.

**Do not use `git stash`** — there is an unrelated pre-existing stash belonging to the repo owner.

## File Structure

| File | Change | Responsible for |
|---|---|---|
| `app/static/js/equipment-panel.js` | **create** | The one renderer: slots, portrait, bag, encumbrance, drag-drop, comparison |
| `app/static/js/equipment-enhanced.js` | **delete** | (superseded) |
| `app/static/js/equipment.js` | **delete** | (superseded) |
| `app/static/js/equipment-shared.js` | **delete** | folded in — it existed only to stop two implementations drifting |
| `app/templates/dashboard.html` | modify | Mounts the panel in a modal |
| `app/templates/adventure.html` | modify | Mounts the panel as a HUD panel; drops the Bags button |
| `app/static/css/equipment.css` | modify | Restyled onto tokens |
| `app/static/css/adventure-hud.css` | modify | `.adv-character` panel geometry |
| `app/static/js/adventure-controls.js` | modify | Rail opens the panel; movement closes it; encumbrance marker |
| `app/routes/dashboard_helpers.py` | modify | `build_party_payload` carries encumbrance |
| `app/static/css/tactical-theme.css` | modify | Base styles for three button variants that have none |
| `tests/test_procedural_gear_equip.py` | **create** | Equipping a generated instance by `uid` |
| `tests/test_party_encumbrance.py` | **create** | The party payload carries encumbrance |
| `tests/test_adventure_hud.py` | modify | Panel mount, no Bags button |
| `e2e/test_smoke.py` | modify | The panel opens from a rail frame, beside the rail |

---

### Task 1: Extract the renderer, mount it on the dashboard

A pure refactor with a visible safety net: the dashboard must look and behave exactly as it does now when this task is done. `equipment-enhanced.js` becomes container-scoped so a second mount is possible at all.

**Files:**
- Create: `app/static/js/equipment-panel.js`
- Delete: `app/static/js/equipment-enhanced.js`, `app/static/js/equipment-shared.js`
- Modify: `app/templates/dashboard.html:560-562`

**Interfaces:**
- Consumes: `GET /api/characters/<id>`, which returns `{id, name, level, xp, stats: {base, computed, gold, silver, copper}, gear, bag, encumbrance, ...progression}` (`app/routes/inventory_api.py:394-412`).
- Produces:

  ```js
  window.EquipmentPanel = {
      mount(container),      // render the skeleton into `container`; idempotent
      open(charId),          // fetch, render, reveal
      close(),
      isOpen(),              // -> boolean
      refresh(),             // re-fetch the currently-open character
  }
  ```

  Task 2 mounts the same object into a HUD panel.

- [ ] **Step 1: Read the source you are porting**

Read `app/static/js/equipment-enhanced.js` (657 lines) and `app/static/js/equipment-shared.js` (66 lines) in full. Between them they are the behavioural specification for this task — drag-and-drop, item comparison tooltips, the eight slots, the portrait panel, the bag grid, encumbrance and gear-bonus rendering. **Preserve every feature.** The port is a restructure, not a rewrite.

- [ ] **Step 2: Create the renderer**

Create `app/static/js/equipment-panel.js` carrying over `EquipmentManager`'s behaviour, with four structural changes that make a second mount possible:

1. **Container-scoped queries.** `equipment-enhanced.js` uses `document.getElementById('eq-char-name')`, `document.querySelectorAll('.equipment-slot')` and similar throughout. Every one becomes `this.root.querySelector(...)` / `this.root.querySelectorAll(...)`, where `this.root` is the mounted container. Two mounts on one page would otherwise fight over the same ids; more immediately, a global `querySelectorAll('.equipment-slot')` on `/adventure` would match nothing until the panel exists and everything once it does.
2. **No inline `onclick` globals.** `createSlotHTML` emits `onclick="equipmentManager.unequipItem('${slot}')"` (`equipment-enhanced.js:197`), which hard-codes a global name into markup. Replace with a delegated listener on `this.root` keyed off a `data-action="unequip"` attribute.
3. **Fold in `equipment-shared.js`.** `encumbranceView()` and `gearBonusText()` move into this file as module-private functions. That file exists only because two implementations had drifted; with one implementation there is nothing to drift.
4. **Take the slot list from the server.** `renderEquipmentSlots` hard-codes the eight slots at `equipment-enhanced.js:168`. `/api/characters/state` already returns `{"slots": [...]}` (`inventory_api.py:337`) and nothing consumes it. Fetch it once, cache it, and fall back to the hard-coded eight only if the request fails — the constraint is that the vocabulary has one source, and a JS literal is a second one.

Also fix two things that are plainly wrong in the original while you are moving the code, and say so in your report:

- `renderPortrait` writes `ATK/DEF/HP/MP` labels in the modal HTML (`equipment-enhanced.js:82-96`) and then rewrites them to `STR/CON/DEX/INT` in JS (`:249-253`). Put the right labels in the markup and delete the rewrite.
- `getSlotForItemType` (`:560-575`) still maps to `boots`/`gloves`/`ring1`/`legs`, which plan 1 removed from the vocabulary, and has no entries for `offhand`/`head`/`chest`/`feet` so it falls through to `|| 'weapon'`. That makes `showComparisonTooltip` compare looted boots against the equipped sword. Map it to the canonical eight.

- [ ] **Step 3: Mount it on the dashboard**

In `app/templates/dashboard.html`, replace lines 560-562:

```html
<script src="{{ asset_url('js/equipment-panel.js') }}"></script>
```

The panel mounts itself into a modal it creates, exactly as `equipment-enhanced.js` did — keep that behaviour for the dashboard so this task changes nothing visible. Wire `.btn-equip-panel` clicks to `EquipmentPanel.open(charId)`.

Note `equipment.js` is still loaded by `dashboard.html` at this point and delegates to `window.equipmentManager` when it exists (`equipment.js:222`). It is deleted in Task 2. For this task, make sure the two do not both fire for one click — the simplest way is to have `equipment-panel.js` expose `window.equipmentManager = window.EquipmentPanel` as a compatibility alias, so the existing delegation keeps working and only one handler acts. Remove the alias in Task 2.

- [ ] **Step 4: Delete the superseded files**

```bash
git rm app/static/js/equipment-enhanced.js app/static/js/equipment-shared.js
```

Then confirm nothing still references them:

```bash
grep -rn "equipment-enhanced\|equipment-shared\|EquipmentShared" app/ tests/ e2e/
```
Expected: no hits.

- [ ] **Step 5: Verify the dashboard is unchanged**

This is the whole safety net for this task, and no unit test can see it. With a server running your code, on `/dashboard`:

- Open a character's equipment panel. All eight slots render, with the right labels.
- Drag an item from the bag onto a slot — it equips.
- Click a slot's remove button — it unequips.
- Hover a bag item over a slot — the comparison tooltip appears with sane numbers.
- The carry-weight bar and the gear-bonus line render.
- Open a *second* character without reloading; the panel shows their gear, not the first character's.

Screenshot before and after if you can, and report what you actually observed rather than what should have happened.

- [ ] **Step 6: Run the suite**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -m pytest tests/ -q
```
Expected: `808 passed, 3 skipped, 1 xpassed`, unchanged — this task touches no Python.

- [ ] **Step 7: Commit**

```bash
git add app/static/js/equipment-panel.js app/templates/dashboard.html
git commit -m "refactor(equipment): one container-scoped panel renderer

equipment-enhanced.js becomes equipment-panel.js: queries scoped to a mounted
container instead of document, delegated handlers instead of inline onclick
globals, and the slot list taken from the server rather than a JS literal.
equipment-shared.js folds in -- it existed only to stop two implementations
drifting, and there is one now.

Dashboard behaviour is unchanged. The adventure screen gets this panel next."
```

---

### Task 2: Mount it on the adventure screen

The payoff. The dungeon gets the good panel, the party rail becomes its character selector, and looted gear becomes equippable during a run.

**Files:**
- Modify: `app/templates/adventure.html`
- Modify: `app/static/css/adventure-hud.css`
- Modify: `app/static/js/adventure-controls.js`
- Delete: `app/static/js/equipment.js`
- Modify: `tests/test_adventure_hud.py`, `e2e/test_smoke.py`

**Interfaces:**
- Consumes: `window.EquipmentPanel` from Task 1; `.adv-frame-open` and `.adv-party-rail` from the HUD work; `--hud-inset-left` / `--hud-inset-bottom` declared on `.adv-hud`.
- Produces: `<aside class="adv-character" hidden>` inside `.adv-hud` as the mount point.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_adventure_hud.py`:

```python
def test_adventure_mounts_the_character_panel(client, party):
    html = client.get("/adventure").get_data(as_text=True)

    assert 'class="adv-character"' in html, "no mount point for the character panel"
    assert "equipment-panel.js" in html


def test_adventure_no_longer_ships_the_old_panels(client, party):
    """One paper doll, not two -- the point of this chunk."""
    html = client.get("/adventure").get_data(as_text=True)

    assert "equipment-enhanced.js" not in html
    assert 'js/equipment.js' not in html


def test_bag_button_is_gone_from_the_frames(client, party):
    """Slots, doll and bag live in one panel, so the frame needs one target."""
    html = client.get("/adventure").get_data(as_text=True)

    assert "btn-bag-panel" not in html
```

The bug has two halves and they need two different tests, because no single test can reach both. The server half — does `/equip` accept a `uid` and land the item — is provable in pytest without a browser. The client half — does the dungeon's panel actually *send* one — is only visible in a browser.

**Server half.** Create `tests/test_procedural_gear_equip.py`. There is no route that grants gear, but `generate_item(level, rarity, slot, rng)` (`app/loot/generator.py:273`) is a pure function returning the instance dict, so the fixture can mint one directly:

```python
"""Procedural gear can be equipped, by uid.

Gear instances live in `items` as dicts carrying a `uid`, and equip_item's
gear-instance path triggers only on a uid in the request body. The dungeon's
old panel posted {slug, slot} with no uid branch, so an instance fell to the
legacy path, found no catalogue row for its generated slug, and 404'd --
nothing the dungeon dropped could be equipped until the player extracted.

This covers the server half. That the dungeon's panel now sends a uid is a
browser concern, checked in e2e and by hand.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import json
import random

import pytest

from app import db
from app.loot.generator import generate_item
from app.models.models import Character, User


@pytest.fixture()
def character_with_loot(client):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="uid_equip_user").first()
    if not user:
        user = User(username="uid_equip_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    instance = generate_item(level=3, rarity="common", slot="hands", rng=random.Random(1234))
    char = Character(
        user_id=user.id,
        name="Looter",
        stats=json.dumps({"str": 10, "con": 12, "int": 10, "hp": 20, "mana": 8}),
        gear="{}",
        items=json.dumps([instance]),
        level=3,
    )
    db.session.add(char)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
    return char, instance


def test_generated_gear_carries_a_uid_and_a_canonical_slot(character_with_loot):
    _char, instance = character_with_loot
    from app.loot.data.archetypes import SLOTS

    assert instance.get("uid"), "a procedural instance must carry a uid to be equippable"
    assert instance["slot"] in SLOTS


def test_equipping_by_uid_lands_the_item(client, character_with_loot):
    char, instance = character_with_loot

    resp = client.post(
        f"/api/characters/{char.id}/equip",
        json={"uid": instance["uid"]},
    )

    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["slot"] == instance["slot"]

    state = client.get(f"/api/characters/{char.id}").get_json()
    assert state["gear"][instance["slot"]], "the item is not in the slot it claims"
    assert not any(
        i.get("uid") == instance["uid"] for i in json.loads(Character.query.get(char.id).items) if isinstance(i, dict)
    ), "the instance should have left the bag"


def test_equipping_by_slug_still_404s_for_a_generated_item(client, character_with_loot):
    """The old dungeon panel's request shape, kept as a regression marker.

    A generated slug has no catalogue row, so the legacy path cannot resolve
    it. This is exactly what the dungeon used to send.
    """
    char, instance = character_with_loot

    resp = client.post(
        f"/api/characters/{char.id}/equip",
        json={"slug": instance.get("slug") or instance["uid"], "slot": instance["slot"]},
    )

    assert resp.status_code == 404
```

Check `generate_item`'s returned dict for the key holding its display slug before writing that last test — adapt the argument if the key differs, and say so in your report.

**Client half.** Append to `e2e/test_smoke.py`:

```python
def test_character_panel_opens_from_a_party_frame(page):
    """The rail is the character selector, and the panel it opens is the one
    that can equip procedural gear (it posts uid). The old dungeon panel could
    not, which is the defect this chunk exists to fix."""
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(f"{BASE_URL}/adventure")
    page.wait_for_load_state("networkidle")

    scripts = page.evaluate(
        "() => Array.from(document.scripts).map(s => s.src).filter(Boolean).join(' ')"
    )
    assert "equipment-panel.js" in scripts
    assert "equipment-enhanced.js" not in scripts, "two paper dolls again"
    assert "/equipment.js" not in scripts, "the old dungeon panel is still loaded"

    page.click(".adv-party-rail .adv-frame-open")
    panel = page.locator(".adv-character")
    panel.wait_for(state="visible", timeout=3000)

    box = panel.bounding_box()
    rail = page.locator(".adv-party-rail").bounding_box()
    assert box["x"] >= rail["x"] + rail["width"] - 1, "the panel is covering the rail it selects from"
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py -q
```
Expected: the three new tests FAIL.

- [ ] **Step 3: Add the mount point and drop the Bags button**

In `app/templates/adventure.html`, add the panel inside `.adv-hud`, after the party rail and before `#party-characters-data`:

```html
  {# The character panel. Mounted by equipment-panel.js, revealed on demand.
     It sits beside the rail rather than over it, so clicking another frame
     swaps its contents with the panel still open -- the rail is the character
     selector, and no in-panel selector is built. #}
  <aside class="adv-character" id="adv-character-panel" hidden></aside>
```

In each party frame's button group, delete the Bags button entirely:

```html
                <button class="tactical-btn-secondary btn-bag-panel party-card-action-btn" data-char-id="{{ m.id }}"
                  aria-label="Bags" title="Bags"><i class="bi bi-bag"></i></button>
```

Leave the equip button — it is the explicit affordance, and the whole frame is a click target for the same action.

In the `{% block scripts %}`, replace the two old panel scripts with the one:

```html
  <script src="{{ asset_url('js/equipment-panel.js') }}"></script>
```

- [ ] **Step 4: Wire the rail to the panel**

In `app/static/js/adventure-controls.js`, the frame-click handler currently forwards to the frame's equip button, which `equipment.js` listened for. Point it at the panel directly:

```js
    // The party rail is the character selector: clicking a frame opens that
    // character's panel, and clicking another swaps the contents rather than
    // closing and reopening. The panel sits beside the rail, never over it.
    document.addEventListener('click', (e) => {
        const frame = e.target.closest('.adv-frame-open');
        if (!frame) return;
        if (e.target.closest('button:not(.btn-equip-panel)')) return;
        const charId = frame.dataset.charId;
        if (charId && window.EquipmentPanel) window.EquipmentPanel.open(charId);
    });

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const frame = e.target.closest?.('.adv-frame-open');
        if (!frame || e.target !== frame) return;
        e.preventDefault();
        const charId = frame.dataset.charId;
        if (charId && window.EquipmentPanel) window.EquipmentPanel.open(charId);
    });
```

Mount the panel on load:

```js
    document.addEventListener('DOMContentLoaded', () => {
        const host = document.getElementById('adv-character-panel');
        if (host && window.EquipmentPanel) window.EquipmentPanel.mount(host);
    });
```

**Movement closes the panel.** The panel covers the camera's target point, which the HUD layout spec forbids for persistent furniture; it is allowed here because it is transient, on the condition that the player never walks blind underneath it. Movement is owned by `adventure.js:884-914`, not this file — hook the close where the move is actually issued, and add `Escape` to the panel's own dismissal:

```js
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && window.EquipmentPanel && window.EquipmentPanel.isOpen()) {
            window.EquipmentPanel.close();
        }
    });
```

Check `Escape` does not now do two things at once — `adventure-controls.js` already binds it to close the hotkeys panel.

- [ ] **Step 5: Style the panel's box**

Append to `app/static/css/adventure-hud.css`:

```css
/* --- Character panel ------------------------------------------------------
 * Sits beside the party rail, not over it, so the rail stays live as the
 * character selector. Spans from the rail's right edge to the viewport edge,
 * and from the top down to the band the log and action bar occupy -- both
 * derived from the same properties the camera reads, so the panel and the
 * camera cannot disagree about where the HUD is.
 *
 * It does cover the camera's target point while open, which the layout spec
 * forbids for persistent furniture. This panel is transient and dismissible,
 * and moving closes it, so the player never walks blind underneath it.
 */

.adv-hud .adv-character {
    position: absolute;
    top: var(--space-2);
    left: var(--hud-inset-left);
    right: var(--space-2);
    bottom: var(--hud-inset-bottom);
    z-index: var(--z-hud);
    overflow: auto;
    scrollbar-width: thin;
    background: var(--surface);
    border: 1px solid var(--edge-strong);
    box-shadow: var(--elev-overlay);
}

.adv-hud .adv-character[hidden] {
    display: none;
}

@media (max-width: 1199px) {
    .adv-hud .adv-character {
        position: static;
        margin-top: var(--space-3);
    }
}
```

The panel covers the canvas-drawn minimap and the zoom controls while open. That is acceptable — it is transient — but the account anchor must stay reachable, so raise it above the panel:

```css
body[data-realm="dungeon"] #account-anchor {
    z-index: var(--z-dropdown);
}
```

Add that to the existing account-anchor rule rather than writing a second one. It also closes a known defect: at `≥1200px` `.adv-hud` is `position: fixed` and so a stacking context, but in the narrow fallback it is not, and the zoom buttons could paint over the open account dropdown.

- [ ] **Step 6: Delete the old dungeon panel**

```bash
git rm app/static/js/equipment.js
```

Remove the `window.equipmentManager` compatibility alias added in Task 1 Step 3, and confirm nothing references either:

```bash
grep -rn "equipment.js\|equipmentManager" app/ tests/ e2e/
```
Expected: no hits other than `equipment-panel.js` itself and `equipment.css`.

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_adventure_hud.py tests/test_live_party_panel.py tests/test_procedural_gear_equip.py -q
```
Expected: all PASS.

With a server running your code:
```bash
E2E=1 ADVENTURE_BASE_URL=http://localhost:5000 .venv/bin/python -m pytest e2e -q
```
Expected: all PASS, including the new procedural-equip test.

- [ ] **Step 8: Play it**

At 1366×768, in the dungeon:

- Click a party frame — the panel opens beside the rail, the rail still visible.
- Click a different frame — the panel swaps to that character without closing.
- Press `Escape` — it closes. Press `W` with it open — it closes and the party moves.
- Loot a procedural item, open the panel, drag it onto its slot — **it equips.** This is the bug; confirm it by eye, not only by the e2e test.
- Confirm the panel does not cover the party frames, and that the log and action bar are still reachable when it is closed.

- [ ] **Step 9: Commit**

```bash
git add app/templates/adventure.html app/static/css/adventure-hud.css \
        app/static/js/adventure-controls.js tests/test_adventure_hud.py e2e/test_smoke.py
git commit -m "feat(equipment): the dungeon gets the real character panel

The party rail becomes the character selector: clicking a frame opens that
character beside the rail, clicking another swaps the contents. Moving closes
the panel, so the player never walks blind under an overlay.

This fixes the defect the chunk exists for: equipment.js posted {slug, slot}
with no uid branch, so procedural gear fell to the legacy path, found no
catalogue row for its generated slug and 404'd -- nothing the dungeon dropped
could be equipped until the player extracted. The promoted panel sends uid.

Drops the Bags button: slots, doll and bag are one panel now."
```

---

### Task 3: Restyle the panel onto the token system

The panel arrives in the dungeon carrying Bootstrap-era styling and three colour schemes the design system already replaced.

**Files:**
- Modify: `app/static/css/equipment.css`

**Interfaces:**
- Consumes: the markup emitted by `equipment-panel.js`.
- Produces: no new class names — this is a restyle of existing selectors.

- [ ] **Step 1: Replace the duplicated colour schemes**

`app/static/css/equipment.css:138-151` hard-codes WoW rarity colours:

```css
.rarity-common    { color: #9d9d9d; }
.rarity-uncommon  { color: #1eff00; }
.rarity-rare      { color: #0070dd; }
.rarity-epic      { color: #a335ee; }
.rarity-legendary { color: #ff8000; }
.rarity-mythic    { color: #e6cc80; }
```

`tokens.css` already defines `--rarity-common` … `--rarity-mythic`. Use them, for both the `color` rules and the `.bag-grid-cell.rarity-*` `border-color` rules below them.

`equipment.css:177-188`'s `.eq-class-bg-*` rules are a **fourth** class-colour scheme, with `var(--class-fighter-bg, #7c2d12)` fallbacks to variables that do not exist anywhere. `tokens.css` defines one hue per class (`--class-fighter` … `--class-warlock`) and the design system says never to hard-code a class colour at a call site. Derive the header background and foreground from the single hue with `color-mix()`, as other components do.

- [ ] **Step 2: Hard edges, no floating**

`equipment.css` has 12 `border-radius` / `box-shadow` declarations. `--radius` is `0` and `--elev-flat` is `none`; the design system names Bootstrap's default radius and diffuse shadows as the two biggest reasons the app read as a demo page. Replace them:

- Panels, cells and slots: `border-radius: var(--radius)`, no shadow.
- Sunken tracks (the HP/MP/XP/weight bars): `box-shadow: var(--inset-well)`.
- The modal itself, being genuinely above the page, may keep `--elev-overlay`.

- [ ] **Step 3: Semantic surfaces and ink**

Replace literal greys and panel colours with `--surface`, `--surface-raised`, `--surface-overlay`, `--edge`, `--edge-subtle`, `--edge-strong`, `--ink`, `--ink-muted`, `--ink-faint`. Bars take `--hp`, `--mp`, `--xp`.

The panel now renders in **both realms** — warm on the dashboard, cold in the dungeon. Since every colour derives from the realm tokens, that should follow automatically; verify it does by loading `/dashboard` and `/adventure` and comparing.

- [ ] **Step 4: Verify**

```bash
grep -nE "#[0-9a-fA-F]{3,6}" app/static/css/equipment.css
```
Expected: no hits, or only inside a comment.

```bash
grep -n "!important" app/static/css/equipment.css
```
Expected: no hits.

Then look at the panel on both screens, at 1366×768 and at 2560×1440, and confirm rarity colours still distinguish items and the class header still reads as that class.

- [ ] **Step 5: Commit**

```bash
git add app/static/css/equipment.css
git commit -m "style(equipment): put the character panel on the token system

Replaces three schemes the design system already superseded: hard-coded WoW
rarity hexes (tokens.css has --rarity-*), a fourth class-colour scheme whose
--class-*-bg fallbacks resolve to nothing, and Bootstrap-era radius and
diffuse shadows. The panel now renders correctly in both realms."
```

---

### Task 4: Encumbrance on the party frame

The complaint that started this chunk: the player did not know the game had carry weight, because it was only visible inside a panel you had to go looking for.

**Files:**
- Modify: `app/routes/dashboard_helpers.py:244-275` (`build_party_payload`)
- Modify: `app/static/js/adventure-controls.js` (`refreshPartyCards`'s `paint`)
- Modify: `app/static/css/adventure-hud.css`
- Modify: `app/templates/adventure.html`
- Test: `tests/test_party_encumbrance.py`

**Interfaces:**
- Consumes: `encumbrance_state(str_score, inv)` from `app/inventory/utils.py:178`, returning a dict with `status` (`"normal"` / `"encumbered"` / `"blocked"`), `dex_penalty`, `weight`, `capacity`.
- Produces: each member of `/api/dungeon/party`'s payload gains `"encumbrance": {"status": str, "dex_penalty": int}`. The frame renders `.frame-encumbrance` when status is not `"normal"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_party_encumbrance.py`:

```python
"""The party frame shows encumbrance, because that is where it bites.

Playtest, 2026-07-28: the player did not know the game had carry weight. It was
computed correctly and displayed only inside a panel you had to go looking for.

Past capacity a dex_penalty applies, and combat movement derives from speed
(8 + DEX // 2), so an overloaded character moves fewer squares. The player has
to see that before the fight, not during it. The weight numbers stay one click
away in the panel; the state goes on the frame.

Spec: docs/superpowers/specs/2026-07-28-character-panel-redesign.md
"""

import json

import pytest

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.models import Character, User


@pytest.fixture()
def party(client):
    from werkzeug.security import generate_password_hash

    user = User.query.filter_by(username="enc_user").first()
    if not user:
        user = User(username="enc_user", password=generate_password_hash("pw"))
        db.session.add(user)
        db.session.commit()
    Character.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    members = []
    for name in ("Light", "Heavy"):
        char = Character(
            user_id=user.id,
            name=name,
            stats=json.dumps({"str": 10, "con": 12, "int": 12, "hp": 20, "mana": 8}),
            gear="{}",
            items="[]",
            level=2,
        )
        db.session.add(char)
        members.append(char)
    db.session.commit()

    instance = DungeonInstance(user_id=user.id, seed=99, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(instance)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_instance_id"] = instance.id
        sess["last_party_ids"] = [c.id for c in members]
        sess["party"] = [{"id": c.id, "name": c.name, "class": "Fighter", "level": 2} for c in members]
    return user, members


def test_party_payload_carries_encumbrance(client, party):
    user, members = party

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    for member in members:
        assert "encumbrance" in payload[member.id], "the frame cannot show what the payload omits"
        assert payload[member.id]["encumbrance"]["status"] in ("normal", "encumbered", "blocked")


def test_an_empty_bag_is_not_encumbered(client, party):
    user, members = party

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    assert payload[members[0].id]["encumbrance"]["status"] == "normal"
    assert payload[members[0].id]["encumbrance"]["dex_penalty"] == 0


def test_a_loaded_bag_reports_encumbered_with_its_penalty(client, party):
    """Load one character past capacity and leave the other alone."""
    from app.inventory.utils import compute_capacity, fetch_encumbrance_config

    user, members = party
    heavy = members[1]
    cap = compute_capacity(10, fetch_encumbrance_config())
    # One heavy stack is enough; weight per item comes from the config.
    heavy.items = json.dumps([{"slug": "iron-ingot", "qty": int(cap) * 10}])
    db.session.add(heavy)
    db.session.commit()

    payload = {m["id"]: m for m in client.get("/api/dungeon/party").get_json()["party"]}

    assert payload[heavy.id]["encumbrance"]["status"] != "normal", "an overloaded bag must show on the frame"
    assert payload[heavy.id]["encumbrance"]["dex_penalty"] > 0
    assert payload[members[0].id]["encumbrance"]["status"] == "normal", "the light character is unaffected"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_party_encumbrance.py -q
```
Expected: FAIL on the missing `encumbrance` key.

- [ ] **Step 3: Carry encumbrance in the party payload**

In `app/routes/dashboard_helpers.py`, inside `build_party_payload`'s loop, compute the state and add it to the appended dict:

```python
        from app.inventory.utils import encumbrance_state, load_inventory

        enc = encumbrance_state(int(s.get("str", 10) or 10), load_inventory(c.items))
```

and in the dict:

```python
                # The frame shows the *state*; the weight numbers stay one click
                # away in the character panel. Past capacity a dex_penalty
                # applies and combat movement derives from speed (8 + DEX // 2),
                # so a player has to see this before the fight, not during it.
                "encumbrance": {
                    "status": enc.get("status", "normal"),
                    "dex_penalty": int(enc.get("dex_penalty", 0) or 0),
                },
```

Import at module top rather than inside the loop if the file's conventions allow — check how `compute_hp_mana_max` is imported a few lines above and match it.

- [ ] **Step 4: Paint it on the frame**

In `app/static/js/adventure-controls.js`, inside `paint(member)`, after the HP/MP bars:

```js
        // Encumbrance is state, not a number: "you are slower" belongs on the
        // frame, the weight belongs in the panel.
        const enc = member.encumbrance || {};
        const marker = card.querySelector('.frame-encumbrance');
        if (marker) {
            const status = enc.status || 'normal';
            const pen = Number(enc.dex_penalty) || 0;
            if (status === 'normal') {
                marker.hidden = true;
                marker.textContent = '';
            } else {
                marker.hidden = false;
                marker.textContent = status === 'blocked'
                    ? `Overloaded${pen ? ` (-${pen} DEX)` : ''}`
                    : `Encumbered${pen ? ` (-${pen} DEX)` : ''}`;
            }
            marker.classList.toggle('is-blocked', status === 'blocked');
        }
```

And add the element to each frame in `app/templates/adventure.html`, just after the `last-roll-line` div:

```html
            <div class="frame-encumbrance" data-char-id="{{ m.id }}" hidden></div>
```

- [ ] **Step 5: Style it**

Append to `app/static/css/adventure-hud.css`:

```css
/* Encumbrance state on the frame. Warn by default; danger when the character
   cannot carry any more. The number lives in the character panel. */
.adv-hud .adv-party-rail .frame-encumbrance {
    font-size: var(--text-2xs);
    letter-spacing: var(--tracking-label);
    text-transform: uppercase;
    color: var(--warn);
}

.adv-hud .adv-party-rail .frame-encumbrance.is-blocked {
    color: var(--danger);
}

.adv-hud .adv-party-rail .frame-encumbrance[hidden] {
    display: none;
}
```

- [ ] **Step 6: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_party_encumbrance.py tests/test_live_party_panel.py tests/test_adventure_hud.py -q
```
Expected: all PASS.

```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: no new failures.

- [ ] **Step 7: Look at it**

Load a character up past capacity, enter the dungeon, and confirm the frame says so — and that a normal character's frame shows nothing rather than an empty box.

- [ ] **Step 8: Commit**

```bash
git add app/routes/dashboard_helpers.py app/static/js/adventure-controls.js \
        app/static/css/adventure-hud.css app/templates/adventure.html \
        tests/test_party_encumbrance.py
git commit -m "feat(hud): encumbrance state on the party frame

The complaint that started this chunk was not knowing the game had carry
weight, because it was only visible inside a panel you had to go looking for.
The state now sits on the frame; the numbers stay one click away in the panel.

Past capacity a dex_penalty applies and combat movement derives from speed
(8 + DEX // 2), so an overloaded character moves fewer squares -- which the
player has to see before the fight."
```

---

### Task 5: Base styles for three button variants that have none

`tactical-btn-primary`, `-info` and `-success` are used across the app and defined nowhere, so they render as bare browser buttons. Three of the five buttons in the adventure action bar are affected, which made it obvious.

**Files:**
- Modify: `app/static/css/tactical-theme.css:585-620`

**Interfaces:**
- Consumes: `tokens.css`.
- Produces: `.tactical-btn-primary`, `.tactical-btn-info`, `.tactical-btn-success` with base and hover styles matching `.tactical-btn-secondary` / `-danger` in the same file.

- [ ] **Step 1: Confirm the gap**

```bash
grep -rn "tactical-btn-primary\|tactical-btn-info\|tactical-btn-success" app/static/css/
```
Expected: hits only in `adventure-hud.css`, which sizes them but sets no colour. `tactical-theme.css:585` and `:602` define `-secondary` and `-danger` and nothing else.

- [ ] **Step 2: Add the three variants**

In `app/static/css/tactical-theme.css`, beside the existing `-secondary` and `-danger` rules, add three matching them in structure and differing only in hue. Read those two rules first and follow their shape exactly — same padding, border treatment, transition and hover behaviour.

- `-primary` takes `--accent` (it is the primary game action; the design system notes the primary button *should* have been `.tactical-btn-primary` rather than `.deploy-btn`).
- `-info` takes `--info`.
- `-success` takes `--success`.

Use `--*-wash` and `--*-line` for fills and borders where the existing rules do, and `--ink-on-accent` for text on a filled accent.

- [ ] **Step 3: Verify**

```bash
grep -nE "#[0-9a-fA-F]{3,6}" app/static/css/tactical-theme.css | sed -n '1,5p'
```
Do not introduce new hex; existing hits elsewhere in the file are not your concern.

Then load `/adventure` and confirm all five action-bar buttons look like siblings, and check `/dashboard` for anywhere else these classes are used.

- [ ] **Step 4: Commit**

```bash
git add app/static/css/tactical-theme.css
git commit -m "style(buttons): define the three tactical button variants that had none

tactical-btn-primary, -info and -success were used across the app and defined
nowhere, so they rendered as bare browser buttons -- three of the five in the
adventure action bar."
```

- [ ] **Step 5: Update the TODO**

In `docs/superpowers/TODO.md`, close the character-panel item and the equip bug:

```markdown
- [x] ~~**Character panels & paper doll**~~ — one `equipment-panel.js` mounted
      two ways (HUD panel beside the party rail in the dungeon, modal on the
      dashboard); `equipment.js`, `equipment-enhanced.js` and
      `equipment-shared.js` deleted. Restyled onto the token system.
      Encumbrance state now shows on the party frame. Plan:
      [plans/2026-07-28-paper-doll-consolidation.md](plans/2026-07-28-paper-doll-consolidation.md).
- [x] ~~Looted gear cannot be equipped during a run~~ — the dungeon's only equip
      path posted `{slug, slot}` with no `uid` branch, so procedural instances
      404'd on the legacy path. The promoted panel sends `uid`.
```

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): paper doll consolidated, dungeon equipping fixed"
```

---

## Self-Review

**Spec coverage** — `2026-07-28-character-panel-redesign.md`:

| Spec requirement | Task |
|---|---|
| One paper doll, not two | 1, 2 (three files deleted) |
| `equipment-enhanced.js` promoted, features preserved | 1 |
| One renderer, two mounts | 1 (dashboard), 2 (adventure) |
| Party rail is the character selector | 2 |
| Panel overlays the map rather than suspending play | 2 |
| Moving closes the panel | 2 |
| Bags button dropped | 2 |
| Looted gear equippable during a run | 2 (the `uid` path arrives with the promoted panel) |
| Built on the token system, not beside it | 3 |
| Encumbrance state on the frame, numbers one click away | 4 |
| `tactical-btn-*` base colours | 5 |
| Combat lock surfaced rather than failing silently | **not built** — see below |

**Deliberately not built,** stated so it is not read as an omission:

- **The in-combat reduced mode** (weapons and consumables live, armour locked). Combat is a separate screen and this panel is not mounted there; `equip_item` already refuses with `in_combat` and a message. Surfacing that message is worth doing when the panel reaches the combat screen, which is the tactical-combat chunk.
- **A second ring slot or a legs slot.** Settled in plan 1: D&D body armour is one piece.
- **Item usage in combat.** Its own spec, sharing this inventory model.

**Type consistency:** `window.EquipmentPanel`'s five methods are defined in Task 1's Interfaces block and called in Task 2 Step 4 (`open`, `mount`, `isOpen`, `close`) with those exact names. `member.encumbrance.{status,dex_penalty}` is produced in Task 4 Step 3 and consumed in Step 4. `.adv-character` is created in Task 2 Step 3 and styled in Step 5. `.frame-encumbrance` is added in Task 4 Step 4 and styled in Step 5.

**Known risks:**

1. **Task 1 is the largest single change in either plan** — a 657-line file restructured with no unit tests behind it, because none exist for this JS and the project has no JS test tooling. The safety net is Step 5's manual dashboard check, which is why that step lists six specific behaviours rather than saying "verify it works". If the port goes wrong the failure is silent and visual.
2. **No single test covers the whole bug.** The server half is proved in pytest by minting an instance with `generate_item` and equipping it by `uid`; the client half — that the dungeon's panel *sends* a uid — is only visible in a browser, and the e2e test checks the panel opens and is the right one rather than driving a real drag. The drag itself is covered only by the manual step. That is an honest split, not an oversight, but it means a regression where the panel loads and renders yet posts the wrong body would pass CI. Say so if you find a cheap way to close it.
3. **`equipment.css` is loaded by `dashboard_base.html`**, which `/adventure` inherits, so Task 3's restyle affects both screens at once. Verify both.
