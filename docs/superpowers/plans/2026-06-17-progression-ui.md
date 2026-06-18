# Character Progression UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dead/fake parts of the character progression UI with real backend-driven data: a server-rendered XP progress bar, a stat-points allocation badge/modal driven by the real `Character.stat_points` ledger, and a per-character "Skill Tree" button.

**Architecture:** Two small additive backend changes expose already-computed-but-unexposed data (`Character.stat_points`, XP thresholds) through both the dashboard's server-render path (`dashboard_helpers.py`, used by Jinja) and the JSON API (`inventory_api.py`, used by JS on-demand refresh). The dashboard template renders the XP bar's initial state and the stat-points badge directly from already-available server data (no JS fetch needed just to display them). `character-progression.js` is gutted of its dead/fake logic and kept only for the *interactive* parts: opening the allocation modal, fetching live data when it opens, submitting allocations, and updating the bar/badge in place afterward. `skill-tree.js` gains per-character button wiring.

**Tech Stack:** Flask/Jinja2 (server-render), vanilla JS (IIFE-free class-based module, existing pattern in `character-progression.js`/`skill-tree.js`), Bootstrap 5 modal (already present), pytest.

## Global Constraints
- No changes to `grant_xp`, `level_for_xp`, or any combat/extraction XP-granting code — already correct (Spec 5a/5b).
- No new endpoints — only add fields to existing `GET /api/characters/<id>`, `GET /api/characters/state` responses, and to `dashboard_helpers.serialize_character_list`'s per-character dict.
- XP thresholds must use `app.models.xp.xp_for_level` with the `xp_difficulty_mod` from `app.services.progression.progression_config()` — never a hardcoded/guessed curve.
- Out of scope: the active-skill "cast in combat" button (tracked separately in TODO.md); consolidating XP bar/stat-alloc/skill-tree into one page; `skill-tree.js`'s client-side `required_level` check (server already enforces it correctly).
- Malformed/missing data must degrade gracefully (e.g. `stat_points` absent → treated as 0, no bar/badge crash).

---

### Task 1: Expose `stat_points` + XP thresholds in the JSON character APIs

**Files:**
- Modify: `app/routes/inventory_api.py` (`list_characters_state` ~line 268, `get_character_state` ~line 347)
- Test: `tests/test_inventory_encumbrance.py` (same file as the prior sub-spec's regression test — keeps progression-adjacent character-state tests together)

**Interfaces:**
- Produces: both JSON responses gain three new top-level keys per character:
  `stat_points: int`, `xp_for_current_level: int`, `xp_for_next_level: int`.
  Later tasks (Task 4, the JS rewrite) consume these exact key names.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_inventory_encumbrance.py` (after the existing
`test_character_state_with_equipped_gear_instance_does_not_crash` test):

```python
def test_character_state_exposes_stat_points_and_xp_thresholds(client):
    with app.app_context():
        u = create_user("progression-checker", "pw")
        char = create_character(u, "ProgressionChecker", "fighter", items=[])
        char.level = 3
        char.xp = 1000
        char.stat_points = 4
        db.session.commit()
        char_id = char.id

    login(client, "progression-checker", "pw")
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"

    from app.models.xp import xp_for_level

    expected_current = xp_for_level(3)
    expected_next = xp_for_level(4)

    r = client.get(f"/api/characters/{char_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["stat_points"] == 4
    assert body["xp_for_current_level"] == expected_current
    assert body["xp_for_next_level"] == expected_next

    r2 = client.get("/api/characters/state")
    assert r2.status_code == 200
    chars = r2.get_json()["characters"]
    match = next(c for c in chars if c["id"] == char_id)
    assert match["stat_points"] == 4
    assert match["xp_for_current_level"] == expected_current
    assert match["xp_for_next_level"] == expected_next
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_inventory_encumbrance.py::test_character_state_exposes_stat_points_and_xp_thresholds -v`
Expected: FAIL with `KeyError: 'stat_points'` (the field doesn't exist in the response yet).

- [ ] **Step 3: Add the import and a small shared helper**

In `app/routes/inventory_api.py`, find the existing imports near the top (after
`from app.inventory.utils import (...)`, check with
`sed -n '1,25p' app/routes/inventory_api.py` to confirm exact placement), and add:

```python
from app.models.xp import xp_for_level
from app.services.progression import progression_config
```

Then add this small helper function near `_computed_stats` (after its closing line,
currently ending around line 168 — confirm with
`grep -n "^def _computed_stats" -A10 app/routes/inventory_api.py`):

```python
def _progression_fields(ch: Character) -> dict:
    """Stat points + XP thresholds for the progression UI (read-only, derived)."""
    mod = float(progression_config().get("xp_difficulty_mod", 1.0))
    level = ch.level or 1
    return {
        "stat_points": ch.stat_points or 0,
        "xp_for_current_level": xp_for_level(level, mod),
        "xp_for_next_level": xp_for_level(level + 1, mod),
    }
```

- [ ] **Step 4: Wire the helper into both endpoints**

In `list_characters_state`, find the `out.append({...})` block (currently ~line
268-277, confirm with `grep -n '"encumbrance": enc_state,' app/routes/inventory_api.py`
— there are two occurrences, one per endpoint). For the one inside the `for ch in
chars:` loop of `list_characters_state`, change:

```python
            out.append(
                {
                    "id": ch.id,
                    "name": ch.name,
                    "level": ch.level,
                    "stats": {"base": penalized_base, "computed": computed},
                    "gear": {slot: _serialize_gear_slot(val, items_map) for slot, val in (gear or {}).items()},
                    "bag": bag_payload,
                    "encumbrance": enc_state,
                }
            )
```
to:
```python
            out.append(
                {
                    "id": ch.id,
                    "name": ch.name,
                    "level": ch.level,
                    "stats": {"base": penalized_base, "computed": computed},
                    "gear": {slot: _serialize_gear_slot(val, items_map) for slot, val in (gear or {}).items()},
                    "bag": bag_payload,
                    "encumbrance": enc_state,
                    **_progression_fields(ch),
                }
            )
```

In `get_character_state`, find the `return jsonify({...})` block (the second
`"encumbrance": enc_state,` occurrence) and change:
```python
    return jsonify(
        {
            "id": ch.id,
            "name": ch.name,
            "level": ch.level,
            "xp": ch.xp or 0,
            "stats": {"base": penalized_base, "computed": computed},
            "gear": gear_payload,
            "bag": bag_payload,
            "encumbrance": enc_state,
        }
    )
```
to:
```python
    return jsonify(
        {
            "id": ch.id,
            "name": ch.name,
            "level": ch.level,
            "xp": ch.xp or 0,
            "stats": {"base": penalized_base, "computed": computed},
            "gear": gear_payload,
            "bag": bag_payload,
            "encumbrance": enc_state,
            **_progression_fields(ch),
        }
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_inventory_encumbrance.py -v`
Expected: all tests in the file PASS (including the new one).

- [ ] **Step 6: Commit**

```bash
git add app/routes/inventory_api.py tests/test_inventory_encumbrance.py
git commit -m "feat(progression): expose stat_points + xp thresholds in character APIs"
```

---

### Task 2: Expose `stat_points` + current-level XP in the dashboard server-render path

**Files:**
- Modify: `app/routes/dashboard_helpers.py` (`serialize_character_list`, the `out.append({...})` block ~line 153-167)
- Test: `tests/test_gear_party_payload.py`

**Interfaces:**
- Consumes: `Character.stat_points` (existing column, default 0), `app.models.xp.xp_for_level` (already imported in this file per `grep -n "from app.models.xp" app/routes/dashboard_helpers.py`).
- Produces: `serialize_character_list`'s per-character dict gains `stat_points: int` and `xp_current: int` (alongside the existing `xp`/`xp_next`/`level` keys). Task 3 (the template) consumes `c.stat_points` and `c.xp_current` by these exact names.

This task also fixes a pre-existing small inconsistency while touching this line: the
existing `xp_next` computation (`xp_for_level(getattr(c, "level", 1) + 1)`) does not
apply `progression_config()`'s `xp_difficulty_mod`, unlike the real leveling path in
`app/services/progression.py::grant_xp`. Both `xp_current` and `xp_next` should use the
same mod-aware call so the dashboard's displayed thresholds always match what actually
gates a level-up.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gear_party_payload.py`:

```python
from app.routes.dashboard_helpers import serialize_character_list
from app.models.models import db, User


def test_serialize_character_list_exposes_stat_points_and_xp_current(test_app):
    with test_app.app_context():
        u = User(username="progression-dash-checker", email="pdc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character
        import json

        char = Character(
            user_id=u.id,
            name="DashChecker",
            level=3,
            xp=1000,
            stat_points=4,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        from app.models.xp import xp_for_level

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["stat_points"] == 4
        assert match["xp_current"] == xp_for_level(3)
        assert match["xp_next"] == xp_for_level(4)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_gear_party_payload.py::test_serialize_character_list_exposes_stat_points_and_xp_current -v`
Expected: FAIL with `KeyError: 'stat_points'`.

- [ ] **Step 3: Add the import**

In `app/routes/dashboard_helpers.py`, near the existing `from app.models.xp import
xp_for_level` import (confirm exact line with
`grep -n "from app.models.xp import xp_for_level" app/routes/dashboard_helpers.py`),
add directly below it:

```python
from app.services.progression import progression_config
```

- [ ] **Step 4: Update the per-character dict**

Find this block (confirm with `grep -n '"xp_next": xp_for_level' -B10
app/routes/dashboard_helpers.py`):
```python
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "stats": stats,
                "coins": coins,
                "inventory": inventory,
                "gear": gear,
                "class_name": class_name,
                "xp": getattr(c, "xp", 0),
                "level": getattr(c, "level", 1),
                "xp_next": xp_for_level(getattr(c, "level", 1) + 1),
            }
        )
```
Replace with:
```python
        mod = float(progression_config().get("xp_difficulty_mod", 1.0))
        level = getattr(c, "level", 1)
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "stats": stats,
                "coins": coins,
                "inventory": inventory,
                "gear": gear,
                "class_name": class_name,
                "xp": getattr(c, "xp", 0),
                "level": level,
                "xp_current": xp_for_level(level, mod),
                "xp_next": xp_for_level(level + 1, mod),
                "stat_points": getattr(c, "stat_points", 0) or 0,
            }
        )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_gear_party_payload.py -v`
Expected: all tests in the file PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routes/dashboard_helpers.py tests/test_gear_party_payload.py
git commit -m "feat(progression): expose stat_points + current-level xp threshold on the dashboard"
```

---

### Task 3: Server-render the XP bar, stat-points badge, and per-character Skill Tree button

**Files:**
- Modify: `app/templates/dashboard.html`
  - The "XP Progress" div (~line 252-257, confirm with `grep -n "EXPERIENCE:"
    app/templates/dashboard.html`)
  - The operative-footer `btn-group` (~line 329-337, confirm with `grep -n
    "btn-bag-panel" app/templates/dashboard.html`)
  - The sidebar "Skill Trees" section (~line 181-189, confirm with `grep -n "Skill
    Tree" app/templates/dashboard.html`)

**Interfaces:**
- Consumes: `c.xp`, `c.xp_current`, `c.xp_next`, `c.level`, `c.stat_points` from Task 2's
  `serialize_character_list` output (already the template's data source for this loop —
  confirm by checking `app/routes/dashboard_helpers.render_dashboard` passes
  `serialize_character_list(...)` as `characters=` into this template, via `grep -n
  "render_template" app/routes/dashboard_helpers.py`).
- Produces: a `<div class="xp-bar-anchor" data-char-id="{{ c.id }}">` wrapper around the
  XP display with a `.xp-fill` div whose initial inline `width` is server-computed; a
  `.btn-allocate-stats` button (only rendered when `c.stat_points > 0`) with
  `data-char-id="{{ c.id }}"`; a `.btn-skill-panel` button with `data-char-id="{{ c.id
  }}"` in the per-card button group. Task 4 (JS) and Task 5 (JS) attach behavior to these
  by class name and `data-char-id`, not by inventing new selectors — these exact class
  names are the contract.

- [ ] **Step 1: Replace the static XP Progress div with a real bar**

Find (confirm exact current text with `sed -n '250,259p' app/templates/dashboard.html`):
```html
                    <!-- XP Progress -->
                    <div
                        style="font-size: 0.85rem; padding: 8px 12px; background: rgba(13, 10, 10, 0.6); border: 1px solid var(--dungeon-border);">
                        <span style="color: var(--dungeon-text-dim);">EXPERIENCE:</span>
                        <span style="color: var(--dungeon-accent);">{{ c.xp }}</span> /
                        <span style="color: var(--dungeon-text-dim);">{{ c.xp_next }}</span>
                        <span style="opacity: 0.7; margin-left: 8px;">(Next: LV{{ c.level + 1 }})</span>
                    </div>
```
Replace with:
```html
                    <!-- XP Progress -->
                    {% set xp_span = c.xp_next - c.xp_current %}
                    {% set xp_pct = ((c.xp - c.xp_current) / xp_span * 100) if xp_span > 0 else 100 %}
                    {% set xp_pct = xp_pct if xp_pct <= 100 else 100 %}
                    {% set xp_pct = xp_pct if xp_pct >= 0 else 0 %}
                    <div class="xp-bar-anchor" data-char-id="{{ c.id }}"
                        style="font-size: 0.85rem; padding: 8px 12px; background: rgba(13, 10, 10, 0.6); border: 1px solid var(--dungeon-border);">
                        <div class="d-flex justify-content-between">
                            <span style="color: var(--dungeon-text-dim);">EXPERIENCE:</span>
                            <span><span style="color: var(--dungeon-accent);">{{ c.xp }}</span> /
                                <span style="color: var(--dungeon-text-dim);">{{ c.xp_next }}</span></span>
                        </div>
                        <div class="progress mt-1" style="height:6px;">
                            <div class="progress-bar xp-fill" style="width:{{ xp_pct }}%"></div>
                        </div>
                        <span style="opacity: 0.7;">(Next: LV{{ c.level + 1 }})</span>
                        {% if c.stat_points and c.stat_points > 0 %}
                        <button type="button" class="tactical-btn-secondary btn-allocate-stats mt-2"
                            data-char-id="{{ c.id }}" style="width: 100%;">
                            <i class="bi bi-star-fill me-1"></i> Allocate {{ c.stat_points }} Stat Point{{ 's' if c.stat_points != 1 else '' }}
                        </button>
                        {% endif %}
                    </div>
```

- [ ] **Step 2: Add the per-character Skill Tree button**

Find (confirm with `sed -n '328,338p' app/templates/dashboard.html`):
```html
                    <div class="btn-group">
                        <button class="tactical-btn-secondary btn-equip-panel" data-char-id="{{ c.id }}"
                            title="Equipment Panel" style="padding: 8px 12px;">
                            {{ svg_icon('anvil', 18) }}
                        </button>
                        <button class="tactical-btn-secondary btn-bag-panel" data-char-id="{{ c.id }}" title="Inventory"
                            style="padding: 8px 12px;">
                            {{ svg_icon('knapsack', 18) }}
                        </button>
                    </div>
```
Replace with:
```html
                    <div class="btn-group">
                        <button class="tactical-btn-secondary btn-equip-panel" data-char-id="{{ c.id }}"
                            title="Equipment Panel" style="padding: 8px 12px;">
                            {{ svg_icon('anvil', 18) }}
                        </button>
                        <button class="tactical-btn-secondary btn-bag-panel" data-char-id="{{ c.id }}" title="Inventory"
                            style="padding: 8px 12px;">
                            {{ svg_icon('knapsack', 18) }}
                        </button>
                        <button class="tactical-btn-secondary btn-skill-panel" data-char-id="{{ c.id }}"
                            title="Skill Tree" style="padding: 8px 12px;">
                            {{ svg_icon('star-fill', 18) }}
                        </button>
                    </div>
```

- [ ] **Step 3: Remove the global, always-wrong sidebar Skill Tree button**

Find (confirm with `sed -n '180,190p' app/templates/dashboard.html`):
```html
                            <!-- Skill Trees -->
                            <div class="mt-4">
                                <div class="subtitle mb-3">{{ svg_icon('star-fill', 16, 'me-2') }}SKILLS</div>
                                <div class="d-flex flex-column gap-2">
                                    <button type="button" class="tactical-btn-secondary"
                                        onclick="window.skillTreeSystem && skillTreeSystem.openSkillTree({{ characters[0].id if characters else 1 }})">
                                        <i class="bi bi-star-fill me-2"></i> Skill Tree
                                    </button>
                                </div>
                            </div>
```
Replace with (a short pointer to the per-character buttons added in Step 2, matching
this template's existing convention of removing controls that no longer apply rather
than leaving a broken one — see how prior sub-specs handled empty-state hiding):
```html
                            <!-- Skill Trees: opened per-character from each operative card's button -->
```

- [ ] **Step 4: Smoke-check the template still renders**

Run: `.venv/bin/python -c "
from app import create_app
app = create_app()
with app.test_request_context():
    from jinja2 import Environment, FileSystemLoader
    env = app.jinja_env
    tmpl = env.get_template('dashboard.html')
    print('template loads OK')
"`
Expected: `template loads OK` with no Jinja syntax errors (this only validates parsing,
not a full render — full render is covered by Task 6's manual verification, since
`render_dashboard()` needs a real logged-in session/DB character to render meaningfully).

- [ ] **Step 5: Commit**

```bash
git add app/templates/dashboard.html
git commit -m "feat(progression): server-render XP bar, stat-points badge, per-character skill button"
```

---

### Task 4: Rework `character-progression.js` against real data

**Files:**
- Modify: `app/static/js/character-progression.js` (substantial rewrite — see exact
  replacement content below)

**Interfaces:**
- Consumes: `GET /api/characters/<id>` response fields from Task 1
  (`stat_points`, `xp_for_current_level`, `xp_for_next_level`, plus existing
  `stats.base.{str,dex,int,con,wis,cha}`, `level`); DOM hooks from Task 3
  (`.xp-bar-anchor[data-char-id]`, `.xp-fill` inside it, `.btn-allocate-stats[data-char-id]`).
- Produces: clicking `.btn-allocate-stats` opens the allocation modal for that
  character; confirming POSTs to the existing `/api/characters/<id>/level-up` endpoint
  (unchanged contract: `{stat_allocations: {str: n, ...}}` → `{ok, level, stats,
  stat_points}`); on success, updates that character's `.xp-fill` width/text and
  hides/updates the `.btn-allocate-stats` button without a full page reload.

This task replaces the entire file. The dead `createXPBars()` (wrong selector,
`.stats-block` never matches the real `.stat-block` markup), the fake
`getXPForLevel` curve, and the `localStorage`-based level-change detection are all
removed — Task 3 already server-renders the bar's initial state, so this file only
needs to handle the interactive allocation flow.

- [ ] **Step 1: Replace the file content**

Replace the entire contents of `app/static/js/character-progression.js` with:

```javascript
/**
 * Character Progression: stat-point allocation.
 *
 * The XP bar and the "Allocate N Stat Points" badge are server-rendered
 * (app/templates/dashboard.html, from app/routes/dashboard_helpers.py) using
 * already-known data, so no fetch is needed just to display them. This module
 * only handles the interactive allocation flow: opening the modal, fetching the
 * character's live stats/stat_points, submitting allocations, and updating the
 * server-rendered bar/badge in place afterward.
 */
class CharacterProgression {
    constructor() {
        this.activeCharacter = null;
        this.pendingStatPoints = 0;
        this.statAllocations = {};
        this.currentStats = {};
        this.init();
    }

    init() {
        this.createAllocationModal();
        this.attachButtonListeners();
    }

    createAllocationModal() {
        if (document.getElementById('level-up-modal')) return;

        const modalHTML = `
<div class="modal fade" id="level-up-modal" tabindex="-1" data-bs-backdrop="static">
    <div class="modal-dialog modal-lg">
        <div class="modal-content level-up-modal">
            <div class="modal-header" style="border-bottom: 1px solid rgba(100,100,120,0.3);">
                <h5 class="modal-title">Allocate Stat Points</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="level-up-celebration d-none" id="level-up-celebration">
                    <div class="level-up-particles" id="level-up-particles"></div>
                    <div class="level-up-title">LEVEL UP!</div>
                    <div class="level-number" id="level-up-number">1</div>
                </div>
                <div class="stat-allocation">
                    <div class="stat-points-available">
                        <i class="bi bi-star-fill me-2"></i>
                        <span id="stat-points-text">0</span> Stat Points Available
                    </div>
                    <div id="stat-allocation-rows"></div>
                </div>
            </div>
            <div class="modal-footer" style="border-top: 1px solid rgba(100,100,120,0.3);">
                <button type="button" class="btn btn-primary btn-lg" id="confirm-level-up">
                    <i class="bi bi-check-circle me-2"></i>Confirm
                </button>
            </div>
        </div>
    </div>
</div>`;

        document.body.insertAdjacentHTML('beforeend', modalHTML);

        document.getElementById('confirm-level-up').addEventListener('click', () => {
            this.confirmAllocation();
        });
    }

    attachButtonListeners() {
        document.querySelectorAll('.btn-allocate-stats').forEach(btn => {
            if (btn.__progressionWired) return;
            btn.__progressionWired = true;
            btn.addEventListener('click', () => {
                const charId = parseInt(btn.getAttribute('data-char-id'), 10);
                this.openAllocationModal(charId);
            });
        });
    }

    async openAllocationModal(charId) {
        try {
            const r = await fetch(`/api/characters/${charId}`);
            if (!r.ok) throw new Error('Failed to load character');
            const char = await r.json();

            this.activeCharacter = charId;
            this.pendingStatPoints = char.stat_points || 0;
            this.statAllocations = {};
            this.currentStats = (char.stats && char.stats.base) || {};

            document.getElementById('level-up-celebration')?.classList.add('d-none');
            this.maybeCelebrateLevelUp(charId, char.level);
            this.renderStatAllocation();

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('level-up-modal'));
            modal.show();
        } catch (err) {
            console.error('Failed to open allocation modal:', err);
        }
    }

    // The server-rendered card badge ("LV{n}") is this tab's only record of what
    // level the player has already seen for this character. If the live fetch
    // shows a higher level, this is the first time this tab has observed the
    // level-up that granted the stat points being allocated — play the existing
    // celebration animation once, then update the badge so it doesn't repeat.
    maybeCelebrateLevelUp(charId, liveLevel) {
        const card = document.querySelector(`.operative-card[data-id="${charId}"]`);
        const badge = card ? card.querySelector('.operative-meta .badge') : null;
        if (!badge) return;
        const seenLevel = parseInt((badge.textContent || '').replace(/\D/g, ''), 10) || 1;
        if (liveLevel <= seenLevel) return;

        badge.textContent = `LV${liveLevel}`;

        const celebration = document.getElementById('level-up-celebration');
        const numberEl = document.getElementById('level-up-number');
        const particlesEl = document.getElementById('level-up-particles');
        if (!celebration || !numberEl || !particlesEl) return;

        numberEl.textContent = liveLevel;
        particlesEl.innerHTML = '';
        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'level-particle';
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.bottom = '0';
            particle.style.animationDelay = `${Math.random() * 2}s`;
            particlesEl.appendChild(particle);
        }
        celebration.classList.remove('d-none');
    }

    renderStatAllocation() {
        const stats = [
            { key: 'str', name: 'Strength', icon: '<i class="bi bi-heart-fill text-danger"></i>' },
            { key: 'dex', name: 'Dexterity', icon: '<i class="bi bi-lightning-charge-fill text-warning"></i>' },
            { key: 'int', name: 'Intelligence', icon: '<i class="bi bi-star-fill text-primary"></i>' },
            { key: 'con', name: 'Constitution', icon: '<i class="bi bi-shield-fill text-success"></i>' },
            { key: 'wis', name: 'Wisdom', icon: '<i class="bi bi-eye-fill text-info"></i>' },
            { key: 'cha', name: 'Charisma', icon: '<i class="bi bi-chat-heart-fill text-purple"></i>' }
        ];

        const html = stats.map(stat => this.createStatAllocationRow(stat)).join('');
        document.getElementById('stat-allocation-rows').innerHTML = html;

        this.updateStatPointsDisplay();
    }

    createStatAllocationRow(stat) {
        const currentValue = this.currentStats[stat.key] != null ? this.currentStats[stat.key] : 10;
        const pending = this.statAllocations[stat.key] || 0;

        return `
<div class="stat-allocation-row" data-stat-key="${stat.key}">
    <div class="stat-name-icon">
        <div class="stat-icon-box">${stat.icon}</div>
        <div class="stat-name-label">${stat.name}</div>
    </div>
    <div class="stat-allocation-controls">
        <button class="stat-increment-btn" data-action="dec" data-stat="${stat.key}" ${pending === 0 ? 'disabled' : ''}>
            <i class="bi bi-dash"></i>
        </button>
        <div class="stat-current-value">${currentValue}</div>
        <div class="stat-pending-change">${pending > 0 ? `+${pending}` : ''}</div>
        <button class="stat-increment-btn" data-action="inc" data-stat="${stat.key}" ${this.pendingStatPoints === 0 ? 'disabled' : ''}>
            <i class="bi bi-plus"></i>
        </button>
    </div>
</div>`;
    }

    updateStatPointsDisplay() {
        document.getElementById('stat-points-text').textContent = this.pendingStatPoints;
        document.querySelectorAll('#stat-allocation-rows [data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const statKey = btn.getAttribute('data-stat');
                if (btn.getAttribute('data-action') === 'inc') this.incrementStat(statKey);
                else this.decrementStat(statKey);
            });
        });
    }

    incrementStat(statKey) {
        if (this.pendingStatPoints <= 0) return;
        this.statAllocations[statKey] = (this.statAllocations[statKey] || 0) + 1;
        this.pendingStatPoints--;
        this.renderStatAllocation();
    }

    decrementStat(statKey) {
        if (!this.statAllocations[statKey]) return;
        this.statAllocations[statKey]--;
        this.pendingStatPoints++;
        this.renderStatAllocation();
    }

    async confirmAllocation() {
        try {
            const response = await fetch(`/api/characters/${this.activeCharacter}/level-up`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stat_allocations: this.statAllocations })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                console.error('Level-up allocation failed:', err);
                return;
            }

            bootstrap.Modal.getInstance(document.getElementById('level-up-modal'))?.hide();
            await this.refreshCharacterUI(this.activeCharacter);
        } catch (err) {
            console.error('Failed to confirm allocation:', err);
        }
    }

    async refreshCharacterUI(charId) {
        try {
            const r = await fetch(`/api/characters/${charId}`);
            if (!r.ok) return;
            const char = await r.json();

            const anchor = document.querySelector(`.xp-bar-anchor[data-char-id="${charId}"]`);
            if (anchor) {
                const span = char.xp_for_next_level - char.xp_for_current_level;
                const pct = span > 0 ? Math.min(100, Math.max(0, ((char.xp - char.xp_for_current_level) / span) * 100)) : 100;
                const fill = anchor.querySelector('.xp-fill');
                if (fill) fill.style.width = `${pct}%`;
            }

            const btn = document.querySelector(`.btn-allocate-stats[data-char-id="${charId}"]`);
            if (btn) {
                if (char.stat_points > 0) {
                    btn.innerHTML = `<i class="bi bi-star-fill me-1"></i> Allocate ${char.stat_points} Stat Point${char.stat_points !== 1 ? 's' : ''}`;
                } else {
                    btn.remove();
                }
            }
        } catch (err) {
            console.error('Failed to refresh character UI:', err);
        }
    }
}

window.characterProgression = new CharacterProgression();
```

- [ ] **Step 2: Syntax-check the file**

Run: `node --check app/static/js/character-progression.js`
Expected: no output (exit code 0).

- [ ] **Step 3: Commit**

```bash
git add app/static/js/character-progression.js
git commit -m "refactor(progression): rebuild stat-allocation UI against real backend data"
```

---

### Task 5: Fix `skill-tree.js`'s button wiring to be per-character

**Files:**
- Modify: `app/static/js/skill-tree.js` (`init()`, currently lines 20-22)

**Interfaces:**
- Consumes: `.btn-skill-panel[data-char-id]` buttons from Task 3.
- Produces: clicking any `.btn-skill-panel` button opens `openSkillTree(charId)` for
  that button's `data-char-id`, replacing the removed global sidebar button's inline
  `onclick`.

- [ ] **Step 1: Read the current `init()` to confirm exact text**

Run: `sed -n '20,22p' app/static/js/skill-tree.js`

Expected (for reference):
```javascript
    init() {
        console.log('Skill Tree System initialized');
    }
```

- [ ] **Step 2: Add event-delegation wiring**

Replace with:
```javascript
    init() {
        console.log('Skill Tree System initialized');
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-skill-panel');
            if (!btn) return;
            const charId = parseInt(btn.getAttribute('data-char-id'), 10);
            if (charId) this.openSkillTree(charId);
        });
    }
```

- [ ] **Step 3: Syntax-check the file**

Run: `node --check app/static/js/skill-tree.js`
Expected: no output (exit code 0).

- [ ] **Step 4: Commit**

```bash
git add app/static/js/skill-tree.js
git commit -m "fix(skill-tree): open the clicked character's tree instead of always the first"
```

---

### Task 6: Manual verification in a live browser

**Files:** none (verification only)

**Interfaces:**
- Consumes: the running app, a logged-in user with at least one character that has
  `stat_points > 0` (set directly via a DB write for the test, as in the prior
  equipment-panel sub-spec's verification) and at least one with `stat_points == 0`.

- [ ] **Step 1: Start the app via the `run` skill and log in**

Use the `run` skill to launch the dev server. Log in as a test user with two
characters: one with `stat_points` set to a positive value (e.g. via a one-off
Python/DB script, matching the pattern used in the equipment-panel sub-spec's
verification), one left at the default `0`.

- [ ] **Step 2: Verify the XP bar**

Load the dashboard. Confirm each character card shows a progress bar under
"EXPERIENCE:" whose fill width visually matches `(xp - xp_current) / (xp_next -
xp_current)`. Cross-check against `GET /api/characters/<id>`'s
`xp_for_current_level`/`xp_for_next_level` fields in a second tab or via devtools.

- [ ] **Step 3: Verify the stat-points badge and allocation flow**

Confirm the character with `stat_points > 0` shows an "Allocate N Stat Points" button;
the character with `0` does not. Click the button; confirm the modal opens showing
all 6 real current stat values (not a hardcoded `10`) and the correct available point
count. Allocate some points, confirm, and verify: the modal closes, the button's count
updates (or disappears if all points were spent), and `Character.stats`/`stat_points`
in the DB reflect the change (cross-check via `GET /api/characters/<id>`).

- [ ] **Step 3b: Verify the level-up celebration**

With the same `stat_points > 0` character, also bump `Character.level` directly in the
DB to a value higher than what's currently rendered in the page (so the page's
`.badge` text reads an older, lower level than the live DB value), without reloading
the page first. Click "Allocate Stat Points" for that character and confirm the
"LEVEL UP!" particle animation plays once inside the modal before the stat rows
render, and that re-opening the modal afterward (without further level changes) does
not replay the animation.

- [ ] **Step 4: Verify the per-character Skill Tree button**

With at least two characters on the dashboard, click each one's new skill-tree icon
button (in the equip/bag/skill button group) and confirm it opens *that* character's
skill trees/talent points (e.g. by checking the talent-points count differs between
two characters with different `CharacterTalentPoints` rows), not always the first
character's, and that the old global sidebar button is gone.

- [ ] **Step 5: Report results**

Note in the SDD progress ledger whether all four behaviors (XP bar accuracy,
badge show/hide, allocation flow, per-character skill button) verified correctly, with
any observations.
