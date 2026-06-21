# Character Cards Phase D: Combat Party Card Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the legacy generic spell panel's UI in favor of the existing per-character skill system, and make combat party cards show always-visible buff/debuff chips plus an auto-revealed ATK/DEF/SPD stat breakdown for whichever character is currently acting.

**Architecture:** Move Phase C's `KNOWN_STATUS_EFFECTS`/`describe_status_effect` from `dashboard_helpers.py` to `app/services/status_effects.py` (the shared home both dashboard and combat already import from), give combat's per-character snapshot (`_derive_stats`) an `effects_display` key built the same way, then update `combat.html`'s card template and `combat.js`'s `render()` to display chips on every card and the stat breakdown only on the active card — purely driven by the existing `isActive` check, no new click handling.

**Tech Stack:** Flask, Jinja2, vanilla JS, existing Cold Steel CSS (`color-mix()` on `--ui-*`/`--dungeon-*` tokens), pytest, Playwright for live verification.

## Global Constraints

- No backend changes to `player_cast_spell`, `/api/combat/<id>/cast_spell`, or their existing tests — UI-only removal of the legacy spell buttons.
- No manual click-to-expand on combat cards — purely automatic, tied to `state.active_index`.
- Buff/debuff chips appear on every party card always, regardless of whose turn it is.
- The stat breakdown (ATK/DEF/SPD) appears only on the active character's card.
- Reuse Phase C's exact CSS class names (`.effect-chip`, `.effect-buff`, `.effect-debuff`, `.effect-neutral`) — already defined in `app/static/css/theme.css`, already loaded on the combat page (no new CSS needed for chips).
- No new `GameConfig` keys, no schema migration.

---

### Task 1: Move `KNOWN_STATUS_EFFECTS`/`describe_status_effect` to `app/services/status_effects.py`

**Files:**
- Modify: `app/services/status_effects.py`
- Modify: `app/routes/dashboard_helpers.py`
- Test: `tests/test_status_effects_decay.py` (Phase A/B's existing test file for this module)
- Test: `tests/test_gear_party_payload.py` (Phase C's existing dashboard tests — must still pass unmodified after the import changes)

**Interfaces:**
- Produces: `KNOWN_STATUS_EFFECTS: dict[str, dict[str, str]]` and `describe_status_effect(effect: dict) -> dict` now live in `app.services.status_effects`, importable as `from app.services.status_effects import KNOWN_STATUS_EFFECTS, describe_status_effect`.
- Consumes (by later tasks): Task 2 imports `describe_status_effect` into `combat_service.py` the same way.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_status_effects_decay.py` (append near the other top-level tests, after the existing `replace_effect` import line — extend that same import statement):

Change the existing import line:
```python
from app.services.status_effects import apply_start_of_turn, apply_tick_decay, replace_effect
```
to:
```python
from app.services.status_effects import (
    KNOWN_STATUS_EFFECTS,
    apply_start_of_turn,
    apply_tick_decay,
    describe_status_effect,
    replace_effect,
)
```

Add the test:
```python
def test_describe_status_effect_known_effect_uses_lookup_table():
    result = describe_status_effect({"name": "poison", "remaining": 3, "data": {"damage": 5}})
    assert result == {"icon": "☠", "label": "Poison", "css_class": "effect-debuff", "remaining": 3}


def test_describe_status_effect_unknown_effect_falls_back_to_generic():
    result = describe_status_effect({"name": "future_effect_xyz", "remaining": 2, "data": {}})
    assert result == {"icon": "◆", "label": "future_effect_xyz", "css_class": "effect-neutral", "remaining": 2}


def test_known_status_effects_table_has_poison_and_regen_buff():
    assert KNOWN_STATUS_EFFECTS["poison"]["css_class"] == "effect-debuff"
    assert KNOWN_STATUS_EFFECTS["regen_buff"]["css_class"] == "effect-buff"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_status_effects_decay.py -k "describe_status_effect or known_status_effects" -v
```

Expected: FAIL — `ImportError: cannot import name 'KNOWN_STATUS_EFFECTS'` (it doesn't exist in `status_effects.py` yet).

- [ ] **Step 3: Move the constant and function into `status_effects.py`**

In `app/services/status_effects.py`, add near the top of the file, right after the existing `DEFAULT_REGEN_RATES` constant (so it's grouped with the other module-level effect metadata):

```python
KNOWN_STATUS_EFFECTS: Dict[str, Dict[str, str]] = {
    "poison": {"icon": "☠", "label": "Poison", "css_class": "effect-debuff"},
    "regen_buff": {"icon": "✨", "label": "Well-Rested", "css_class": "effect-buff"},
}


def describe_status_effect(effect: Dict[str, Any]) -> Dict[str, Any]:
    """Return display metadata for one CharacterStatusEffect dict, with a
    generic fallback for names not in KNOWN_STATUS_EFFECTS so a future
    effect type shows up automatically without a template change."""
    meta = KNOWN_STATUS_EFFECTS.get(
        effect["name"], {"icon": "◆", "label": effect["name"], "css_class": "effect-neutral"}
    )
    return {**meta, "remaining": effect["remaining"]}
```

Add `"KNOWN_STATUS_EFFECTS"` and `"describe_status_effect"` to the `__all__` list at the bottom of the file.

In `app/routes/dashboard_helpers.py`, delete the now-duplicate definitions (lines 23-36, the `KNOWN_STATUS_EFFECTS` dict and the `describe_status_effect` function), and add this import near the top of the file, alongside the existing `from app.services.progression import progression_config` line:

```python
from app.services.status_effects import describe_status_effect
```

The one call site inside `serialize_character_list` (the `describe_status_effect(...)` call inside the `effects_display` list comprehension) needs no change — it calls the same function, now imported instead of locally defined.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_status_effects_decay.py tests/test_gear_party_payload.py -v
```

Expected: PASS (all tests in both files — confirms the move didn't break Phase C's dashboard tests, which exercise `describe_status_effect` indirectly through `serialize_character_list`).

- [ ] **Step 5: Commit**

```bash
git add app/services/status_effects.py app/routes/dashboard_helpers.py tests/test_status_effects_decay.py
git commit -m "refactor(status-effects): move KNOWN_STATUS_EFFECTS/describe_status_effect to status_effects.py"
```

---

### Task 2: Add `effects_display` to combat's per-character snapshot

**Files:**
- Modify: `app/services/combat_service.py`
- Test: `tests/test_gear_combat_integration.py` (existing file that already calls `_derive_stats` directly)

**Interfaces:**
- Consumes: `describe_status_effect` from `app.services.status_effects` (Task 1).
- Produces: `_derive_stats(char)`'s returned dict gains one new key: `"effects_display": list[dict]`, each dict shaped `{"icon": str, "label": str, "css_class": str, "remaining": int}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gear_combat_integration.py` (it already imports `_derive_stats` and has a `create_character`/`create_user`-style helper pattern — check the file's existing imports/helpers and match them; the test below assumes `db`, `CharacterStatusEffect`, and a way to create a `Character` are available the same way the file's existing test does):

```python
def test_derive_stats_includes_effects_display_for_known_effect(test_app):
    with test_app.app_context():
        from app.models import CharacterStatusEffect
        from app.models.models import Character, User

        user = User(username="combat-effects-display-checker", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="EffectsDisplayChecker",
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=3, data='{"damage": 5}'))
        db.session.commit()

        derived = _derive_stats(char)

        assert len(derived["effects_display"]) == 1
        eff = derived["effects_display"][0]
        assert eff["icon"] == "☠"
        assert eff["label"] == "Poison"
        assert eff["css_class"] == "effect-debuff"
        assert eff["remaining"] == 3


def test_derive_stats_effects_display_empty_when_no_effects(test_app):
    with test_app.app_context():
        from app.models.models import Character, User

        user = User(username="combat-no-effects-checker", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="NoEffectsChecker",
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()

        derived = _derive_stats(char)

        assert derived["effects_display"] == []
```

Check the top of `tests/test_gear_combat_integration.py` for whether `json` and `db` are already imported — add `import json` and `from app import db` if either is missing, matching the file's existing style.

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_gear_combat_integration.py -k "effects_display" -v
```

Expected: FAIL — `KeyError: 'effects_display'` (the key doesn't exist on `_derive_stats`'s return dict yet).

- [ ] **Step 3: Implement in `app/services/combat_service.py`**

Find the existing effects-loading block inside `_derive_stats` (around line 168-181):

```python
    from app.models import CharacterStatusEffect

    PERSISTED_EFFECT_NAMES = ("poison", "regen_buff")

    try:
        effects = [
            {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
            for row in CharacterStatusEffect.query.filter(
                CharacterStatusEffect.character_id == char.id,
                CharacterStatusEffect.name.in_(PERSISTED_EFFECT_NAMES),
            ).all()
        ]
    except Exception:
        effects = []
```

Add immediately after this block (still before the `return {...}` statement):

```python
    from app.services.status_effects import describe_status_effect

    effects_display = [describe_status_effect(e) for e in effects]
```

Then in the `return {...}` dict (around line 183-203), add the new key right after the existing `"effects": effects,` line:

```python
        "effects": effects,
        "effects_display": effects_display,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_gear_combat_integration.py -v
```

Expected: PASS (all tests in the file, including pre-existing ones — confirms no regression)

Also re-run the broader combat suite to confirm `_derive_stats`'s new key doesn't break anything that consumes its output elsewhere:

```bash
.venv/bin/python -m pytest tests/ -k "combat" -q
```

Expected: PASS, no new failures.

- [ ] **Step 5: Commit**

```bash
git add app/services/combat_service.py tests/test_gear_combat_integration.py
git commit -m "feat(combat): add effects_display to per-character combat snapshot"
```

---

### Task 3: Retire the legacy spell panel UI

**Files:**
- Modify: `app/templates/combat.html`
- Modify: `app/static/js/combat.js`

**Interfaces:** none new — this task only deletes existing UI surface. No other task depends on anything from this task.

- [ ] **Step 1: Remove the legacy spell buttons from `combat.html`**

In `app/templates/combat.html`, the action panel currently contains (lines 23-42):

```html
                        <div class="btn-group-combat">
                            <button type="button" class="btn-combat btn-combat-attack" data-action="attack">
                                <i class="bi bi-sword"></i> Attack
                            </button>
                            <button type="button" class="btn-combat btn-combat-defend" data-action="defend">
                                <i class="bi bi-shield-fill"></i> Defend
                            </button>
                        </div>
                        <div class="btn-group-combat">
                            <button type="button" class="btn-combat btn-combat-spell" data-action="cast_firebolt"
                                data-mana-cost="5">
                                <i class="bi bi-fire"></i> Firebolt
                            </button>
                            <button type="button" class="btn-combat btn-combat-spell" data-action="cast_ice_shard"
                                data-mana-cost="6">
                                <i class="bi bi-snow"></i> Ice Shard
                            </button>
                        </div>
                        <div class="btn-group-combat">
                            <button type="button" class="btn-combat btn-combat-spell" data-action="cast_lightning"
                                data-mana-cost="8">
                                <i class="bi bi-lightning-charge-fill"></i> Lightning
                            </button>
                            <button type="button" class="btn-combat btn-combat-heal" data-action="use_potion"
                                data-needs-potion="true">
                                <i class="bi bi-heart-pulse-fill"></i> Potion
                            </button>
                        </div>
                        <button type="button" class="btn-combat btn-combat-flee" data-action="flee">
                            <i class="bi bi-door-open"></i> Flee
                        </button>
```

Replace with (removes the entire middle `cast_firebolt`/`cast_ice_shard`/`cast_lightning` group, keeps Attack/Defend, moves Potion into its own row, keeps Flee):

```html
                        <div class="btn-group-combat">
                            <button type="button" class="btn-combat btn-combat-attack" data-action="attack">
                                <i class="bi bi-sword"></i> Attack
                            </button>
                            <button type="button" class="btn-combat btn-combat-defend" data-action="defend">
                                <i class="bi bi-shield-fill"></i> Defend
                            </button>
                        </div>
                        <div class="btn-group-combat">
                            <button type="button" class="btn-combat btn-combat-heal" data-action="use_potion"
                                data-needs-potion="true">
                                <i class="bi bi-heart-pulse-fill"></i> Potion
                            </button>
                        </div>
                        <button type="button" class="btn-combat btn-combat-flee" data-action="flee">
                            <i class="bi bi-door-open"></i> Flee
                        </button>
```

- [ ] **Step 2: Remove the class-heuristic gating from `combat.js`**

In `app/static/js/combat.js`, inside `render()`, find this block (around lines 378-405):

```js
            const charClass = (activeMember.char_class || 'fighter').toLowerCase();
            const intStat = activeMember.int_stat || 10;
            const strStat = activeMember.str_stat || 10;
            const dexStat = activeMember.dex_stat || 10;

            // Define which classes can use spells
            const spellcastingClasses = ['mage', 'cleric', 'druid', 'sorcerer', 'warlock', 'bard', 'paladin', 'ranger'];
            const canCastSpells = spellcastingClasses.includes(charClass) || intStat >= 12;

            // Define melee-focused classes
            const meleeFocused = ['fighter', 'barbarian', 'paladin', 'monk', 'ranger'];
            const isPhysical = meleeFocused.includes(charClass) || strStat >= 14;

            // Update action buttons
            actionPanel.querySelectorAll('button[data-action]').forEach(btn => {
                const action = btn.dataset.action;
                let shouldHide = false;

                // Hide spell buttons for non-casters
                if (action.startsWith('cast_') && !canCastSpells) {
                    shouldHide = true;
                }

                if (shouldHide) {
                    btn.style.display = 'none';
                    return;
                }
                btn.style.display = '';
```

Replace with (drops the now-unused `spellcastingClasses`/`canCastSpells`/`meleeFocused`/`isPhysical` variables and the `cast_`-prefix hiding branch, since no button has `data-action="cast_*"` anymore after Step 1 — `charClass` itself is kept since `MANALESS_CLASSES.has(charClass)` elsewhere in `render()` still needs it):

```js
            const charClass = (activeMember.char_class || 'fighter').toLowerCase();

            // Update action buttons
            actionPanel.querySelectorAll('button[data-action]').forEach(btn => {
                btn.style.display = '';
```

Leave everything below this point (the `if (!canAct) { ... }`, potion-availability, mana-gating, and listener-rebinding logic) exactly as-is — those blocks don't reference `canCastSpells`/`isPhysical`/`intStat`/`strStat`/`dexStat` and apply equally to the remaining buttons (Attack/Defend/Potion/Flee).

- [ ] **Step 3: Verify JS syntax**

```bash
node --check app/static/js/combat.js
```

Expected: no output, exit code 0.

- [ ] **Step 4: Run the existing combat test suite to confirm the backend is unaffected**

```bash
.venv/bin/python -m pytest tests/test_combat_spell_outcomes.py tests/test_combat_actions.py tests/test_unconscious_actions.py -v
```

Expected: PASS — this task only touched `combat.html`/`combat.js`; the backend service and route these tests exercise (`player_cast_spell`, `/api/combat/<id>/cast_spell`) are untouched.

- [ ] **Step 5: Commit**

```bash
git add app/templates/combat.html app/static/js/combat.js
git commit -m "feat(combat): retire legacy static spell panel UI, keep real skill system as the only caster path"
```

---

### Task 4: Render buff/debuff chips on every card, stat breakdown on the active card only

**Files:**
- Modify: `app/templates/combat.html`
- Modify: `app/static/js/combat.js`
- Modify: `app/static/css/combat.css`

**Interfaces:**
- Consumes: `mem.effects_display` (Task 2's new key on each party member, each entry shaped `{"icon", "label", "css_class", "remaining"}`), `mem.attack`/`mem.defense`/`mem.speed` (already existed on every member dict before this plan), and the `isActive` boolean `render()` already computes per member.

- [ ] **Step 1: Add the new template fields to `party-member-template`**

In `app/templates/combat.html`, the `party-member-template`'s `.party-member` currently ends with the `stats-bars` div closing (around line 125, right before the `</div>` that closes `.panel-header`):

```html
                    <div class="stat-bar-group" data-field="mana-group">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="stat-label"><i class="bi bi-droplet-fill mp-icon"></i></span>
                            <span class="stat-value" data-field="mana-text">0/0</span>
                        </div>
                        <div class="progress-glass-sm">
                            <div class="progress-bar-primary" data-field="mana-bar"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
```

Replace with (adds the chip row and the hidden-by-default stat breakdown right after `.stats-bars` closes, still inside `.panel-header`):

```html
                    <div class="stat-bar-group" data-field="mana-group">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="stat-label"><i class="bi bi-droplet-fill mp-icon"></i></span>
                            <span class="stat-value" data-field="mana-text">0/0</span>
                        </div>
                        <div class="progress-glass-sm">
                            <div class="progress-bar-primary" data-field="mana-bar"></div>
                        </div>
                    </div>
                </div>
                <div class="effect-chips" data-field="effect-chips"></div>
                <div class="stat-breakdown" data-field="stat-breakdown" hidden>
                    <span data-field="atk">ATK 0</span>
                    <span data-field="def">DEF 0</span>
                    <span data-field="spd">SPD 0</span>
                </div>
            </div>
        </div>
    </div>
</template>
```

- [ ] **Step 2: Add the `.stat-breakdown` CSS rule**

In `app/static/css/combat.css`, add this rule right after the existing `.stat-value { ... }` rule (in the "Stats bars in party cards" section):

```css
.stat-breakdown {
    display: flex;
    gap: 10px;
    margin-top: 8px;
    font-size: 0.75rem;
    color: var(--ui-text-dim);
    font-family: 'Courier New', monospace;
}
```

No new rule is needed for `.effect-chips`/`.effect-chip`/`.effect-buff`/`.effect-debuff`/`.effect-neutral` — these are already defined in `app/static/css/theme.css`, which `combat.html` already loads via `{{ url_for('theme.get_active_theme_css') }}` (see the `{% block head %}` section of `combat.html`).

- [ ] **Step 3: Populate the new fields in `combat.js`'s `render()`**

Find the existing mana-update block inside the `party.forEach(mem => { ... })` loop (around lines 351-363):

```js
            // Update Mana (hidden entirely for manaless classes, e.g. barbarian)
            const manaGroup = clone.querySelector('[data-field="mana-group"]');
            if (MANALESS_CLASSES.has(charClass)) {
                if (manaGroup) manaGroup.style.display = 'none';
            } else {
                const manaText = clone.querySelector('[data-field="mana-text"]');
                const manaBar = clone.querySelector('[data-field="mana-bar"]');
                if (manaText) manaText.textContent = `${mem.mana}/${mem.mana_max}`;
                if (manaBar) {
                    const manaPct = mem.mana_max > 0 ? (mem.mana / mem.mana_max * 100) : 0;
                    manaBar.style.width = manaPct + '%';
                }
            }

            partyContainer.appendChild(clone);
```

Replace with (adds the chip population and stat-breakdown reveal right before the existing `partyContainer.appendChild(clone)` call):

```js
            // Update Mana (hidden entirely for manaless classes, e.g. barbarian)
            const manaGroup = clone.querySelector('[data-field="mana-group"]');
            if (MANALESS_CLASSES.has(charClass)) {
                if (manaGroup) manaGroup.style.display = 'none';
            } else {
                const manaText = clone.querySelector('[data-field="mana-text"]');
                const manaBar = clone.querySelector('[data-field="mana-bar"]');
                if (manaText) manaText.textContent = `${mem.mana}/${mem.mana_max}`;
                if (manaBar) {
                    const manaPct = mem.mana_max > 0 ? (mem.mana / mem.mana_max * 100) : 0;
                    manaBar.style.width = manaPct + '%';
                }
            }

            // Buff/debuff chips -- always shown, every card, regardless of turn.
            const chipsEl = clone.querySelector('[data-field="effect-chips"]');
            if (chipsEl) {
                chipsEl.innerHTML = '';
                (mem.effects_display || []).forEach(eff => {
                    const chip = document.createElement('span');
                    chip.className = `effect-chip ${eff.css_class}`;
                    chip.title = `${eff.label} — ${eff.remaining} remaining`;
                    chip.textContent = `${eff.icon} ${eff.label} ×${eff.remaining}`;
                    chipsEl.appendChild(chip);
                });
            }

            // Stat breakdown -- only the active character's card reveals it.
            const statBlock = clone.querySelector('[data-field="stat-breakdown"]');
            if (statBlock) {
                if (isActive) {
                    statBlock.hidden = false;
                    statBlock.querySelector('[data-field="atk"]').textContent = 'ATK ' + (mem.attack ?? 0);
                    statBlock.querySelector('[data-field="def"]').textContent = 'DEF ' + (mem.defense ?? 0);
                    statBlock.querySelector('[data-field="spd"]').textContent = 'SPD ' + (mem.speed ?? 0);
                } else {
                    statBlock.hidden = true;
                }
            }

            partyContainer.appendChild(clone);
```

`isActive` is already declared earlier in the same `forEach` iteration (the line `const isActive = active && active.type === 'player' && active.id === mem.char_id;`, used for the `border-warning`/`active-turn` class toggle) — this reuses that exact variable, no recomputation.

- [ ] **Step 4: Verify JS syntax**

```bash
node --check app/static/js/combat.js
```

Expected: no output, exit code 0.

- [ ] **Step 5: Verify CSS brace balance**

```bash
.venv/bin/python -c "
with open('app/static/css/combat.css') as f:
    css = f.read()
assert css.count('{') == css.count('}'), 'mismatched braces'
print('brace count OK:', css.count('{'))
"
```

Expected: prints `brace count OK: <some number>` with no `AssertionError`.

- [ ] **Step 6: Commit**

```bash
git add app/templates/combat.html app/static/js/combat.js app/static/css/combat.css
git commit -m "feat(combat): render buff/debuff chips on every party card, auto-reveal stat breakdown on the active card"
```

---

### Task 5: Live-browser verification

**Files:** none (verification only — if a real bug is found, fix it in whichever Task 1-4 file is responsible and document it in the report, following the same pattern as Phase B/C)

**Interfaces:** none — consumes the finished feature from Tasks 1-4 end to end.

- [ ] **Step 1: Start the dev server**

```bash
cd /home/winter/work/Adventure
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
nohup .venv/bin/python run.py > /tmp/run_server.log 2>&1 &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/login
```

Expected: `200`.

- [ ] **Step 2: Ensure a logged-in user with a poisoned character and an active combat session exists**

The combat page route is `GET /combat/<int:combat_id>` (`app/routes/combat_api.py`'s `combat_page`), requiring a real, non-archived `CombatSession` row owned by the logged-in user — there is no bare `/combat` route. The most direct way to get a real `combat_id` for this verification is to call `combat_service.start_session(user_id, monster_dict)` directly via a one-off Python script run in the app context (the same pattern `tests/test_regen_potion_combat.py` and similar combat tests already use to construct a session), then navigate Playwright straight to `/combat/<that_id>`.

If the `tester` user (username `tester`, password `pass`) doesn't already exist in the dev/test DB from a prior phase's verification, register it via the app's normal `/register` flow (a one-off script, not committed) and give it at least 2 characters via the existing `POST /autofill_characters` route. Then, still inside that one-off setup script's app context:
1. Optionally seed a `CharacterStatusEffect(name="poison", remaining=5, data='{"damage": 5}')` row for one of `tester`'s characters, so the verification script has a real effect to check for a chip on.
2. Call `combat_service.start_session(user.id, <a simple monster dict like the one in tests/test_regen_potion_combat.py's `_simple_monster()`>)` to create a real `CombatSession`, and print its `.id`.
3. Pass that printed `combat_id` into the Playwright script below (e.g. as a CLI arg or hardcoded constant after reading the printed value).

- [ ] **Step 3: Write a one-off Playwright verification script**

Create `scripts/verify_phase_d_combat_cards.py` (temporary, matching the project's established one-off-Playwright-script pattern):

```python
"""One-off Playwright verification for Character Cards Phase D (combat party
card buff/debuff chips + auto-revealed stat breakdown + legacy spell panel
removal). Not part of the automated test suite -- run manually against a
live dev server."""

import sys

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"
COMBAT_ID = int(sys.argv[1]) if len(sys.argv) > 1 else None


def main():
    if COMBAT_ID is None:
        print("Usage: verify_phase_d_combat_cards.py <combat_id>")
        return 1
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(f"{BASE_URL}/login")
        page.fill("input[name=username]", "tester")
        page.fill("input[name=password]", "pass")
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE_URL}/dashboard*", timeout=5000)

        page.goto(f"{BASE_URL}/combat/{COMBAT_ID}")
        page.wait_for_selector(".party-member", timeout=5000)

        cards = page.query_selector_all(".party-member")
        assert len(cards) >= 1, "expected at least one party card"

        # Legacy spell buttons must be gone.
        legacy_buttons = page.query_selector_all(
            '[data-action="cast_firebolt"], [data-action="cast_ice_shard"], [data-action="cast_lightning"]'
        )
        assert len(legacy_buttons) == 0, "legacy spell buttons should have been removed"

        # Exactly one card should show the stat breakdown (the active character's).
        visible_breakdowns = [
            el for el in page.query_selector_all(".stat-breakdown") if el.is_visible()
        ]
        assert len(visible_breakdowns) == 1, f"expected exactly 1 visible stat-breakdown, got {len(visible_breakdowns)}"

        # Every card's effect-chips container should exist (even if empty for
        # characters with no active effects).
        chip_containers = page.query_selector_all(".effect-chips")
        assert len(chip_containers) == len(cards), "every party card should have an effect-chips container"

        assert not console_errors, f"console errors: {console_errors}"

        print("All Phase D combat-card checks passed.")
        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the verification script**

```bash
.venv/bin/python scripts/verify_phase_d_combat_cards.py <combat_id_printed_in_step_2>
```

Expected: `All Phase D combat-card checks passed.` If any assertion fails, investigate and fix the real bug it surfaces in whichever Task 1-4 file is responsible — do not weaken the assertions to force a pass.

- [ ] **Step 5: Stop the dev server and remove the one-off script**

```bash
pkill -f "run.py" || true
rm -f scripts/verify_phase_d_combat_cards.py
```

- [ ] **Step 6: Run the full backend test suite**

```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py -p no:randomly
```

Expected: all tests pass, no regressions vs. the pre-Phase-D baseline (441 passed as of the end of Phase C).

- [ ] **Step 7: Update the handoff TODO**

Add an entry to `docs/superpowers/TODO.md` under the Character Cards series (near the Phase A/B/C entries) summarizing what shipped: legacy spell panel UI retired, buff/debuff chips on every combat card, auto-revealed stat breakdown on the active card, shared `describe_status_effect` helper now lives in `status_effects.py`. Note that this closes out the full Character Cards series (Phases A-D).

- [ ] **Step 8: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark Character Cards Phase D (combat party card redesign) done -- series complete"
```
