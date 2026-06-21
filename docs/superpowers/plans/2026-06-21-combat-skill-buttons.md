# Combat Skill Buttons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each combat party member's unlocked talent-tree active
skills as buttons in the combat action panel, alongside (not replacing)
the existing universal Firebolt/Ice Shard/Lightning spells, wired to the
existing `POST /api/combat/<id>/cast_skill` endpoint.

**Architecture:** Backend: one additive field (`cooldown`) added to the
existing `GET /api/characters/<id>/skills` response. Frontend: `combat.js`
fetches that endpoint per active character (cached in a module-level
`Map`), renders one button per unlocked `skill_type === 'active'` skill
into the existing `#combat-action-panel` button-grid, and extends the
existing `doAction()` dispatcher to POST to `cast_skill` for these.

**Tech Stack:** Flask routes (`app/routes/skill_api.py`), SQLAlchemy
models (`app/models/skill.py`), vanilla JS (`app/static/js/combat.js`),
pytest + Flask test client.

## Global Constraints

- No JS test infra exists in this repo for `combat.js` — confirmed via
  grep, and explicitly accepted precedent in
  `docs/superpowers/TODO.md` for other client-only combat behaviors
  (e.g. the version-monotonicity guard). Frontend changes in this plan
  are verified manually, not via automated test.
- Backend changes must keep `tests/ -q --deselect tests/test_combat_persistence.py`
  fully green (402 passed baseline as of this plan).
- `DATABASE_URL` and `TEST_DATABASE_URL` must both be exported to the test
  DB before running pytest (see `docs/superpowers/TODO.md`'s "How to run
  the suite").

---

### Task 1: Add `cooldown` to the character-skills API response

**Files:**
- Modify: `app/routes/skill_api.py:101-129` (`get_character_skills`)
- Test: `tests/test_character_skills_api.py` (new file)

**Interfaces:**
- Produces: `GET /api/characters/<id>/skills` response array, each entry
  now additionally has `"cooldown": <int|null>` (seconds, from
  `Skill.cooldown`). All other existing fields (`skill_id`, `skill_name`,
  `skill_type`, `effect_json`, `last_used`, etc.) unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/test_character_skills_api.py`:

```python
"""Tests for GET /api/characters/<id>/skills."""

import json
import uuid

from app import db
from app.models.skill import CharacterSkill, Skill, SkillTree
from tests.factories import create_character, create_user


def _setup_unlocked_skill(char_id, skill_type="active", cooldown=12):
    tree = SkillTree(name="T_" + uuid.uuid4().hex[:6], max_tier=5)
    db.session.add(tree)
    db.session.flush()
    skill = Skill(
        tree_id=tree.id,
        name="S_" + uuid.uuid4().hex[:6],
        description="x",
        tier=1,
        required_level=1,
        cost=1,
        effect_json=json.dumps({"damage": 10}),
        skill_type=skill_type,
        cooldown=cooldown,
    )
    db.session.add(skill)
    db.session.flush()
    cs = CharacterSkill(character_id=char_id, skill_id=skill.id)
    db.session.add(cs)
    db.session.commit()
    return skill


def test_get_character_skills_includes_cooldown(client):
    user = create_user("skapi_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero", items=[])
    db.session.commit()
    skill = _setup_unlocked_skill(char.id, cooldown=12)

    resp = client.get(f"/api/characters/{char.id}/skills")
    assert resp.status_code == 200
    body = resp.get_json()
    match = next(s for s in body if s["skill_id"] == skill.id)
    assert match["cooldown"] == 12


def test_get_character_skills_cooldown_null_when_unset(client):
    user = create_user("skapi2_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Hero2", items=[])
    db.session.commit()
    skill = _setup_unlocked_skill(char.id, cooldown=None)

    resp = client.get(f"/api/characters/{char.id}/skills")
    body = resp.get_json()
    match = next(s for s in body if s["skill_id"] == skill.id)
    assert match["cooldown"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_character_skills_api.py -v
```
Expected: `test_get_character_skills_includes_cooldown` FAILs with `KeyError: 'cooldown'` (or `StopIteration` is wrong — should be a clean `assert None == 12`-style failure since the key is simply missing, causing a `KeyError` when indexed via `match["cooldown"]`). The second test should pass already (since `None == None` would hold even without the fix) — that's expected; it exists to lock in the null case once the fix lands, not to be red itself.

- [ ] **Step 3: Write minimal implementation**

In `app/routes/skill_api.py`, inside `get_character_skills`'s loop (around line 113-127), add the `cooldown` key:

```python
        result.append(
            {
                "character_skill_id": cs.id,
                "skill_id": skill.id,
                "skill_name": skill.name,
                "skill_description": skill.description,
                "skill_type": skill.skill_type,
                "tier": skill.tier,
                "effect_json": skill.effect_json,
                "cooldown": skill.cooldown,
                "skill_rank": cs.skill_rank,
                "times_used": cs.times_used,
                "unlocked_at": cs.unlocked_at.isoformat() if cs.unlocked_at else None,
                "last_used": cs.last_used.isoformat() if cs.last_used else None,
            }
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
.venv/bin/python -m pytest tests/test_character_skills_api.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Run the full suite to check for regressions**

Run:
```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: same pass count as baseline plus the 2 new tests (404 passed, 2 skipped, 3 deselected, 1 xpassed).

- [ ] **Step 6: Commit**

```bash
git add app/routes/skill_api.py tests/test_character_skills_api.py
git commit -m "feat(skills): expose cooldown on GET /api/characters/<id>/skills"
```

---

### Task 2: Render unlocked active-skill buttons in the combat action panel

**Files:**
- Modify: `app/static/js/combat.js`

**Interfaces:**
- Consumes: `GET /api/characters/<id>/skills` (Task 1's response shape:
  array of `{skill_id, skill_name, skill_type, effect_json, cooldown,
  last_used}`).
- Consumes: existing `POST /api/combat/<id>/cast_skill` with body
  `{version, actor_id, skill_id}` (already implemented in
  `combat_service.player_cast_skill`; unmodified by this plan). Success
  response is `{ok: true, state: {...}, skill: <name>, damage?: <int>,
  heal?: <int>}`; failure is `{error: "<code>", ...}` (no `state` key on
  most error paths except `inactive`/`version_conflict`/`not_your_turn`).
- Produces: no new exports — this is a self-contained addition inside the
  existing IIFE in `combat.js`.

- [ ] **Step 1: Add a per-character skill cache and fetch helper**

In `app/static/js/combat.js`, after the existing `let lastLogCount = 1;`
block (around line 32, alongside the other module-level `let`
declarations), add:

```javascript
    // Cache of unlocked active skills per character, populated lazily the
    // first time each character becomes the active turn-taker. Avoids
    // refetching on every combat_update/poll tick (render() runs far more
    // often than a character's skill list can change mid-combat).
    const activeSkillsCache = new Map(); // charId -> array of skill objects (or null while loading)

    async function fetchActiveSkills(charId) {
        if (activeSkillsCache.has(charId)) return activeSkillsCache.get(charId);
        activeSkillsCache.set(charId, []); // placeholder so concurrent calls don't double-fetch
        try {
            const r = await fetch(`/api/characters/${charId}/skills`);
            const all = await r.json();
            const active = Array.isArray(all) ? all.filter(s => s.skill_type === 'active') : [];
            activeSkillsCache.set(charId, active);
            return active;
        } catch (e) {
            activeSkillsCache.set(charId, []);
            return [];
        }
    }
```

- [ ] **Step 2: Render skill buttons after the existing action-panel button setup**

In `combat.js`'s `render()` function, the existing action-panel block ends
at the `else if (actionPanel) { actionPanel.style.display = 'none'; }`
around line 362. Immediately before that `else if` (i.e., right after the
`actionPanel.querySelectorAll('button[data-action]').forEach(...)` block
closes, around line 361), add a call to a new render function and define
it. Replace:

```javascript
                newBtn.addEventListener('click', () => doAction(action, state.version, activeCharId));
            });
        } else if (actionPanel) {
            actionPanel.style.display = 'none';
        }
```

with:

```javascript
                newBtn.addEventListener('click', () => doAction(action, state.version, activeCharId));
            });

            renderSkillButtons(actionPanel, activeCharId, canAct, state.version);
        } else if (actionPanel) {
            actionPanel.style.display = 'none';
            const stale = actionPanel.querySelector('.skill-buttons-group');
            if (stale) stale.remove();
        }
```

Then define `renderSkillButtons` as a new top-level function in the IIFE
(place it right after the `fetchActiveSkills` function added in Step 1):

```javascript
    function renderSkillButtons(actionPanel, charId, canAct, version) {
        const grid = actionPanel.querySelector('.d-grid.gap-2');
        if (!grid) return;
        const existing = grid.querySelector('.skill-buttons-group');
        if (existing) existing.remove();

        const cached = activeSkillsCache.get(charId);
        if (cached === undefined) {
            fetchActiveSkills(charId).then(() => {
                // Re-render once the fetch resolves; safe even if the active
                // character has since changed (renderSkillButtons no-ops
                // against a panel that's been hidden/reparented since).
                renderSkillButtons(actionPanel, charId, canAct, version);
            });
            return;
        }

        const group = document.createElement('div');
        group.className = 'btn-group-combat skill-buttons-group';

        cached.forEach(skill => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn-combat btn-combat-spell';
            btn.dataset.action = `cast_skill_${skill.skill_id}`;
            btn.dataset.skillId = String(skill.skill_id);
            btn.innerHTML = `<i class="bi bi-stars"></i> ${skill.skill_name}`;

            if (!canAct) {
                btn.disabled = true;
            } else if (skill.last_used && skill.cooldown) {
                const elapsedSec = (Date.now() - Date.parse(skill.last_used)) / 1000;
                const remaining = skill.cooldown - elapsedSec;
                if (remaining > 0) {
                    btn.disabled = true;
                    btn.title = `On cooldown (${Math.ceil(remaining)}s)`;
                }
            }

            btn.addEventListener('click', () => doSkillAction(skill.skill_id, version, charId));
            group.appendChild(btn);
        });

        if (cached.length > 0) {
            // Insert right before the Flee button (the grid's last child)
            // so skills sit with the other action buttons, not after Flee.
            const fleeBtn = grid.querySelector('[data-action="flee"]');
            if (fleeBtn) grid.insertBefore(group, fleeBtn);
            else grid.appendChild(group);
        }
    }
```

- [ ] **Step 3: Add the `doSkillAction` POST handler**

`appendLog(lines)` (defined at `combat.js:120`) is NOT a generic logger —
it tracks `processedLogCount`/`lastLogSignature` module-level state and
treats any array shorter than what it's already processed as the server
log having "shrunk", which wipes and rebuilds the entire visible log from
that short array. Calling it with a one-off synthetic message would erase
the real combat log. Instead, write a small dedicated helper that appends
a single transient line directly to the log DOM element without touching
`appendLog`'s state.

Immediately after the existing `async function doAction(...)` function
(it ends with the closing `}` after its `try`/`catch` block, around line
503), add:

```javascript
    function appendTransientLogLine(text) {
        // Mirrors the plain createElement('div') + classify-class pattern
        // appendLog() itself uses (combat.js:149-150) — 'log-system' is the
        // same class already used for "Encounter starts"/"defeated!" lines.
        const line = document.createElement('div');
        line.classList.add('log-system');
        line.textContent = text;
        logEl.appendChild(line);
        logEl.scrollTop = logEl.scrollHeight;
    }

    async function doSkillAction(skillId, version, actorId) {
        try {
            const r = await fetch(`/api/combat/${combatId}/cast_skill`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ version: version, actor_id: actorId, skill_id: skillId }),
            });
            const j = await r.json();
            if (j.state) {
                render(j.state);
            } else if (j.error === 'on_cooldown') {
                appendTransientLogLine(`Skill is on cooldown (${j.remaining_seconds}s remaining).`);
            } else if (j.error) {
                appendTransientLogLine(`Skill could not be used (${j.error}).`);
            }
        } catch (e) { /* ignore */ }
    }
```

- [ ] **Step 4: Manual verification in a running dev server**

1. Start the dev server (use the project's normal run command, e.g.
   `./manage.sh` or `python run.py` — check `README.md`/`DEVELOPMENT.md`
   for the current invocation if unsure).
2. Log in, ensure a character has at least one unlocked active skill —
   if none exist on the dev DB, unlock one via the skill-tree UI
   (`/skills` or equivalent route) on a character with available talent
   points.
3. Start or resume a combat encounter with that character in the active
   party.
4. Confirm: when that character's turn is active, a new button labeled
   with the skill's name appears in the action panel, alongside
   Attack/Defend/Firebolt/etc. and before Flee.
5. Click it — confirm the request hits `/api/combat/<id>/cast_skill`
   (check browser devtools Network tab), the monster takes damage or the
   caster heals as appropriate, and the button is now disabled with a
   cooldown tooltip if the skill has a cooldown.
6. Pass turn to a different party member — confirm the skill button(s)
   shown change to match that character's own unlocked skills (or
   disappear if they have none).
7. Confirm no console errors appear in devtools during any of the above.

- [ ] **Step 5: Commit**

```bash
git add app/static/js/combat.js
git commit -m "feat(combat): render unlocked active skills as combat action buttons"
```

---

## Post-implementation

Update `docs/superpowers/TODO.md`: mark the "Combat action panel is one
static spell list for every character" entry (currently unchecked) as
done, summarizing what was wired (Task 1 + Task 2) and noting the
manual-verification status from Task 2 Step 5.
