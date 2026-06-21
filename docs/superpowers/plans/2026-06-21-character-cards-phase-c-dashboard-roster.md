# Character Cards Phase C: Dashboard Roster Card Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the dashboard's always-fully-expanded roster cards into a collapsed-by-default summary (header + HP/MP bars + buff/debuff chips) that expands in place on click to show everything the card shows today, plus a new effects detail block.

**Architecture:** Server-side, extend `serialize_character_list` to compute `hp_max`/`mana_max` (via the existing `compute_hp_mana_max` helper) and a generically-rendered `effects_display` list per character. Client-side, split each `.operative-card` into an always-visible `.operative-summary` and a `hidden`-by-default `.operative-detail`, toggled independently per card by a click handler.

**Tech Stack:** Flask, Jinja2 templates, vanilla JS, existing Cold Steel CSS theme (`color-mix()` on `--ui-*`/`--dungeon-*` tokens), pytest, Playwright (already installed in `.venv`) for live-browser verification.

## Global Constraints

- Any number of cards can be expanded simultaneously — no accordion/single-expand behavior.
- The entire collapsed card is the click target to expand/collapse (not a dedicated button) — bigger touch target for low-dexterity/mobile use.
- No new quick-action buttons — EQUIP/BAG/SKILLS/DISMISS/SELECT move into the expanded state unchanged.
- No live polling/websockets — buff/debuff and HP/MP data is computed once per page load, same as everything else on this page today.
- No expand/collapse persistence across reload — every page load starts fully collapsed.
- Buff/debuff rendering must be generic: an unrecognized `CharacterStatusEffect` name falls back to a generic icon/label instead of being skipped or raising.
- No inline `style="..."` attributes in templates (project's pre-commit hook blocks this) — use `data-*` attributes consumed by JS, following the existing `data-xp-pct` pattern in `app/static/js/dashboard.js:154`.

---

### Task 1: Backend — expose `hp_max`/`mana_max`/`effects_display` from `serialize_character_list`

**Files:**
- Modify: `app/routes/dashboard_helpers.py`
- Test: `tests/test_gear_party_payload.py`

**Interfaces:**
- Produces: `KNOWN_STATUS_EFFECTS: dict[str, dict[str, str]]` (module-level constant in `dashboard_helpers.py`, keys are effect names, values have `icon`/`label`/`css_class` string keys).
- Produces: `describe_status_effect(effect: dict) -> dict` — takes one effect dict shaped `{"name": str, "remaining": int, "data": dict}` (the same shape `CharacterStatusEffect` rows are already converted to elsewhere in the codebase, e.g. `combat_service.py`'s effects-loading query), returns `{"icon": str, "label": str, "css_class": str, "remaining": int}`.
- Produces: each dict in `serialize_character_list`'s return list gains three new keys: `"hp_max": int`, `"mana_max": int`, `"effects_display": list[dict]` (each dict shaped per `describe_status_effect`'s return).
- Consumes: `compute_hp_mana_max(character) -> tuple[int, int]` from `app.services.character_stats` (already exists, already used elsewhere in this same function for backfilling `hp`/`mana`).
- Consumes: `CharacterStatusEffect` model from `app.models` (already exists from Phase A: `id`, `character_id`, `name`, `remaining`, `data` (JSON-string-or-None) columns).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_gear_party_payload.py` (append after the existing tests, keep the existing `import json` / other imports at top untouched):

```python
def test_serialize_character_list_exposes_hp_max_and_mana_max(test_app):
    with test_app.app_context():
        u = User(username="hpmax-dash-checker", email="hmdc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character
        from app.services.character_stats import compute_hp_mana_max

        char = Character(
            user_id=u.id,
            name="HpMaxChecker",
            level=2,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 12, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        hp_max, mana_max = compute_hp_mana_max(char)

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["hp_max"] == hp_max
        assert match["mana_max"] == mana_max


def test_serialize_character_list_exposes_known_effect_display(test_app):
    with test_app.app_context():
        u = User(username="effect-dash-checker", email="edc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models import CharacterStatusEffect
        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="EffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=3, data='{"damage": 5}'))
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert len(match["effects_display"]) == 1
        eff = match["effects_display"][0]
        assert eff["icon"] == "☠"
        assert eff["label"] == "Poison"
        assert eff["css_class"] == "effect-debuff"
        assert eff["remaining"] == 3


def test_serialize_character_list_unknown_effect_falls_back_to_generic_display(test_app):
    with test_app.app_context():
        u = User(username="unknown-effect-dash-checker", email="uedc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models import CharacterStatusEffect
        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="UnknownEffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(
            CharacterStatusEffect(character_id=char.id, name="future_effect_xyz", remaining=2, data="{}")
        )
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert len(match["effects_display"]) == 1
        eff = match["effects_display"][0]
        assert eff["label"] == "future_effect_xyz"
        assert eff["css_class"] == "effect-neutral"
        assert eff["remaining"] == 2


def test_serialize_character_list_no_effects_gives_empty_list(test_app):
    with test_app.app_context():
        u = User(username="noeffect-dash-checker", email="nedc@test.local")
        u.set_password("pw")
        db.session.add(u)
        db.session.commit()

        from app.models.models import Character

        char = Character(
            user_id=u.id,
            name="NoEffectChecker",
            level=1,
            stats=json.dumps({"str": 10, "dex": 10, "int": 10, "con": 10, "wis": 10, "cha": 10}),
        )
        db.session.add(char)
        db.session.commit()

        out = serialize_character_list(u.id)
        match = next(c for c in out if c["id"] == char.id)
        assert match["effects_display"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/test_gear_party_payload.py -k "hp_max or effect" -v
```

Expected: FAIL — `KeyError: 'hp_max'` / `KeyError: 'effects_display'` (neither key exists in `serialize_character_list`'s output yet).

- [ ] **Step 3: Implement in `app/routes/dashboard_helpers.py`**

Add the module-level constant and helper function near the top of the file, after the existing imports (around line 22, right after `from app.services.progression import progression_config`):

```python
KNOWN_STATUS_EFFECTS: dict[str, dict[str, str]] = {
    "poison": {"icon": "☠", "label": "Poison", "css_class": "effect-debuff"},
    "regen_buff": {"icon": "✨", "label": "Well-Rested", "css_class": "effect-buff"},
}


def describe_status_effect(effect: dict[str, Any]) -> dict[str, Any]:
    """Return display metadata for one CharacterStatusEffect dict, with a
    generic fallback for names not in KNOWN_STATUS_EFFECTS so a future
    effect type shows up automatically without a template change."""
    meta = KNOWN_STATUS_EFFECTS.get(
        effect["name"], {"icon": "◆", "label": effect["name"], "css_class": "effect-neutral"}
    )
    return {**meta, "remaining": effect["remaining"]}
```

Inside `serialize_character_list`'s per-character loop, find where `hp`/`mana` backfill already happens (around line 80-85):

```python
        if "hp" not in stats or "mana" not in stats:
            from app.services.character_stats import compute_hp_mana_max

            hp_max, mana_max = compute_hp_mana_max(c)
            stats.setdefault("hp", hp_max)
            stats.setdefault("mana", mana_max)
```

Add immediately after this block (still inside the per-character loop, before `stats_class = stats.get("class", None)`):

```python
        from app.services.character_stats import compute_hp_mana_max

        hp_max, mana_max = compute_hp_mana_max(c)

        try:
            from app.models import CharacterStatusEffect

            effects_display = [
                describe_status_effect(
                    {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
                )
                for row in CharacterStatusEffect.query.filter_by(character_id=c.id).all()
            ]
        except Exception:
            effects_display = []
```

Then in the `out.append({...})` dict (around line 161-175), add the two new keys:

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
                "level": level,
                "xp_current": xp_for_level(level, mod),
                "xp_next": xp_for_level(level + 1, mod),
                "stat_points": getattr(c, "stat_points", 0) or 0,
                "hp_max": hp_max,
                "mana_max": mana_max,
                "effects_display": effects_display,
            }
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_gear_party_payload.py -v
```

Expected: PASS (all tests in the file, including the 3 pre-existing ones — confirms no regression)

- [ ] **Step 5: Commit**

```bash
git add app/routes/dashboard_helpers.py tests/test_gear_party_payload.py
git commit -m "feat(dashboard): expose hp_max/mana_max/effects_display from serialize_character_list"
```

---

### Task 2: Template — split each card into collapsed summary + expanded detail

**Files:**
- Modify: `app/templates/dashboard.html:230-384` (the `.operative-card` block)

**Interfaces:**
- Consumes: `c.hp_max`, `c.mana_max`, `c.effects_display` (Task 1's new keys), plus all pre-existing `c.*` keys this block already uses.
- Produces: new DOM structure with `.operative-summary` (always visible) and `.operative-detail` (HTML `hidden` attribute by default) as the two direct children of `.operative-card` that wrap, respectively, the new collapsed content and all of today's existing content. Task 3 (CSS) and Task 4 (JS) depend on these exact class names and the `hidden` attribute being present.

- [ ] **Step 1: Write the new template structure**

Replace the current `.operative-card` block (`app/templates/dashboard.html` lines 234-382, i.e. from `<div class="operative-card ...">` through its matching closing `</div>`) with:

```html
            <div class="operative-card {% if session.get('party') %}{% for p in session.get('party') %}{% if p.id == c.id %}selected{% endif %}{% endfor %}{% endif %}"
                data-id="{{ c.id }}">

                <!-- Always-visible collapsed summary -- the click target for expand/collapse -->
                <div class="operative-summary">
                    <div class="operative-header">
                        <div class="operative-name">
                            <span class="icon-28">
                                {% set class_lower = c.class_name.lower() %}
                                {% if class_lower == 'fighter' %}
                                {{ svg_icon('swords-power', 24) }}
                                {% elif class_lower == 'mage' %}
                                {{ svg_icon('fire-silhouette', 24) }}
                                {% elif class_lower == 'rogue' %}
                                {{ svg_icon('rogue', 24) }}
                                {% elif class_lower == 'druid' %}
                                {{ svg_icon('heavy-thorny-triskelion', 24) }}
                                {% elif class_lower == 'cleric' %}
                                {{ svg_icon('aura', 24) }}
                                {% elif class_lower == 'ranger' %}
                                {{ svg_icon('bowman', 24) }}
                                {% else %}
                                <i class="bi bi-person-fill"></i>
                                {% endif %}
                            </span>
                            <span>{{ c.name }}</span>
                        </div>
                        <div class="operative-meta">
                            <span class="class-badge {{ c.class_name|lower }}-badge">{{ c.class_name }}</span>
                            <span class="badge">LV{{ c.level }}</span>
                        </div>
                    </div>

                    {% set hp_pct = (c.stats.hp / c.hp_max * 100) if c.hp_max > 0 else 0 %}
                    {% set hp_pct = 100 if hp_pct > 100 else (0 if hp_pct < 0 else hp_pct) %}
                    {% set mp_pct = (c.stats.mana / c.mana_max * 100) if c.mana_max > 0 else 0 %}
                    {% set mp_pct = 100 if mp_pct > 100 else (0 if mp_pct < 0 else mp_pct) %}
                    <div class="hp-mp-bars">
                        <div class="resource-bar-track">
                            <span class="bar-label">HP {{ c.stats.hp }}/{{ c.hp_max }}</span>
                            <div class="bar-track"><div class="bar-fill hp-fill" data-bar-pct="{{ hp_pct }}"></div></div>
                        </div>
                        <div class="resource-bar-track">
                            <span class="bar-label">MP {{ c.stats.mana }}/{{ c.mana_max }}</span>
                            <div class="bar-track"><div class="bar-fill mp-fill" data-bar-pct="{{ mp_pct }}"></div></div>
                        </div>
                    </div>

                    {% if c.effects_display %}
                    <div class="effect-chips">
                        {% for eff in c.effects_display %}
                        <span class="effect-chip {{ eff.css_class }}" title="{{ eff.label }} — {{ eff.remaining }} remaining">
                            {{ eff.icon }} {{ eff.label }} ×{{ eff.remaining }}
                        </span>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>

                <!-- Expanded detail -- hidden by default, toggled by dashboard-operative-cards.js -->
                <div class="operative-detail" hidden>

                    <div class="operative-body">

                        <!-- XP Progress -->
                        {% set xp_span = c.xp_next - c.xp_current %}
                        {% set xp_pct = ((c.xp - c.xp_current) / xp_span * 100) if xp_span > 0 else 100 %}
                        {% set xp_pct = xp_pct if xp_pct <= 100 else 100 %}
                        {% set xp_pct = xp_pct if xp_pct >= 0 else 0 %}
                        <div class="xp-bar-anchor" data-char-id="{{ c.id }}">
                            <div class="d-flex justify-content-between">
                                <span class="xp-label-dim">EXPERIENCE:</span>
                                <span><span class="xp-label-accent">{{ c.xp }}</span> /
                                    <span class="xp-label-dim">{{ c.xp_next }}</span></span>
                            </div>
                            <div class="progress mt-1 xp-progress-track">
                                <div class="progress-bar xp-fill" data-xp-pct="{{ xp_pct }}"></div>
                            </div>
                            <span class="opacity-70">(Next: LV{{ c.level + 1 }})</span>
                            {% if c.stat_points and c.stat_points > 0 %}
                            <button type="button" class="tactical-btn-secondary btn-allocate-stats mt-2 btn-full-width"
                                data-char-id="{{ c.id }}">
                                <i class="bi bi-star-fill me-1"></i> Allocate {{ c.stat_points }} Stat Point{{ 's' if c.stat_points != 1 else '' }}
                            </button>
                            {% endif %}
                        </div>

                        {% if c.effects_display %}
                        <div class="stat-block">
                            <h6>{{ svg_icon('aura', 16, 'me-1') }}ACTIVE EFFECTS</h6>
                            <ul class="effect-detail-list">
                                {% for eff in c.effects_display %}
                                <li class="{{ eff.css_class }}">{{ eff.icon }} <strong>{{ eff.label }}</strong> — {{ eff.remaining }} remaining</li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}

                        <!-- Stats Block -->
                        <div class="stat-block">
                            <h6>{{ svg_icon('bar-chart', 16, 'me-1') }}ATTRIBUTES</h6>
                            <div class="stat-grid">
                                <div><span class="fw-bold">STR</span>{{ c.stats.str }}</div>
                                <div><span class="fw-bold">DEX</span>{{ c.stats.dex }}</div>
                                <div><span class="fw-bold">INT</span>{{ c.stats.int }}</div>
                                <div><span class="fw-bold">WIS</span>{{ c.stats.wis }}</div>
                                <div><span class="fw-bold">CHA</span>{{ c.stats.cha }}</div>
                                <div><span class="fw-bold">CON</span>{{ c.stats.con }}</div>
                                <div><span class="fw-bold">HP</span>{{ c.stats.hp }}</div>
                                <div><span class="fw-bold">MP</span>{{ c.stats.mana }}</div>
                            </div>
                        </div>

                        <!-- Resources -->
                        <div class="resource-bar">
                            <span class="coin-gold">{{ svg_icon('cash', 18, 'me-1') }}{{ c.coins.gold }}g</span>
                            <span class="coin-silver">{{ svg_icon('two-coins', 18, 'me-1') }}{{ c.coins.silver }}s</span>
                            <span class="coin-copper">{{ svg_icon('token', 18, 'me-1') }}{{ c.coins.copper }}c</span>
                        </div>

                        <!-- Inventory -->
                        <div class="stat-block flex-grow-1-block">
                            <h6>{{ svg_icon('knapsack', 16, 'me-1') }}EQUIPMENT</h6>
                            {% if c.inventory and c.inventory|length > 0 %}
                            <div class="inventory-list">
                                <ul>
                                    {% for it in c.inventory %}
                                    <li>
                                        {% if it.type == 'weapon' %}
                                        {{ svg_icon('bloody-sword', 16) }}
                                        {% elif it.type == 'armor' %}
                                        {{ svg_icon('shield', 16) }}
                                        {% elif it.type == 'potion' %}
                                        {{ svg_icon('potion-ball', 16) }}
                                        {% elif it.type == 'tool' %}
                                        {{ svg_icon('anvil', 16) }}
                                        {% elif it.type == 'ring' %}
                                        {{ svg_icon('ring', 16) }}
                                        {% elif it.type == 'scroll' %}
                                        {{ svg_icon('scroll-unfurled', 16) }}
                                        {% else %}
                                        {{ svg_icon('chest', 16) }}
                                        {% endif %}
                                        <span>{{ it.name }}</span>
                                        <span class="item-type-tag">[{{ it.type }}]</span>
                                    </li>
                                    {% endfor %}
                                </ul>
                            </div>
                            {% else %}
                            <div class="unarmed-placeholder">
                                [ UNARMED ]
                            </div>
                            {% endif %}
                        </div>
                    </div>

                    <!-- Operative Footer -->
                    <div class="operative-footer">
                        <form action="{{ url_for('dashboard.delete_character', char_id=c.id) }}" method="post"
                            onsubmit="return confirm('⚠️ DISMISS {{ c.name }}?\n\nThis action is permanent and cannot be undone.');">
                            <button class="tactical-btn-danger">
                                {{ svg_icon('trash-can', 16, 'me-1') }} DISMISS
                            </button>
                        </form>
                        <div class="btn-group">
                            <button class="tactical-btn-secondary btn-equip-panel btn-icon-compact"
                                data-char-id="{{ c.id }}" title="Equipment Panel">
                                {{ svg_icon('anvil', 18) }}
                            </button>
                            <button class="tactical-btn-secondary btn-bag-panel btn-icon-compact" data-char-id="{{ c.id }}"
                                title="Inventory">
                                {{ svg_icon('knapsack', 18) }}
                            </button>
                            <button class="tactical-btn-secondary btn-skill-panel btn-icon-compact"
                                data-char-id="{{ c.id }}" title="Skill Tree">
                                {{ svg_icon('star-fill', 18) }}
                            </button>
                        </div>
                        <input type="checkbox" class="party-select d-none" id="char-select-{{ c.id }}" data-id="{{ c.id }}"
                            data-name="{{ c.name }}" data-class="{{ c.class_name }}" {% if session.get('party') %}{% for p
                            in session.get('party') %}{% if p.id==c.id %}checked{% endif %}{% endfor %}{% endif %}>
                        <label for="char-select-{{ c.id }}" class="select-operative select-operative-label">
                            <span class="select-text">{% if session.get('party') %}{% for p in session.get('party') %}{% if
                                p.id == c.id %}SELECTED{% else %}SELECT{% endif %}{% endfor %}{% else %}SELECT{% endif
                                %}</span>
                        </label>
                    </div>
                </div>
            </div>
```

This is a structural reorganization, not new logic: every existing Jinja expression (`{{ c.name }}`, `{{ c.stats.str }}`, the footer forms/buttons, the SELECT checkbox, etc.) is unchanged and simply re-nested under the two new wrapper divs. Only genuinely new lines are the `hp-mp-bars`/`effect-chips` block inside `.operative-summary` and the "ACTIVE EFFECTS" `stat-block` inside `.operative-detail`.

- [ ] **Step 2: Verify the page still renders without a server error**

No automated test exists for template rendering of this page (per established project convention — confirmed via `grep -rl "dashboard.html" tests/` returning no direct render-assertion tests beyond auth flow checks). Verify structurally instead:

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/ -k "dashboard" -v
```

Expected: PASS (existing dashboard-route tests, e.g. auth/redirect checks, continue to pass — confirms the template change didn't break Jinja syntax or break the route's 200 response).

- [ ] **Step 3: Commit**

```bash
git add app/templates/dashboard.html
git commit -m "feat(dashboard): split operative-card into collapsed summary + expandable detail"
```

---

### Task 3: CSS — bars, effect chips, and detail-list styling

**Files:**
- Modify: `app/static/css/theme.css` (add new rules near the existing `.operative-card`/`.stat-block` rules, e.g. after the `.stat-grid div` rule block established in earlier reads of this file)

**Interfaces:**
- Consumes: the exact class names Task 2's template produces: `.operative-summary`, `.operative-detail`, `.hp-mp-bars`, `.resource-bar-track`, `.bar-label`, `.bar-track`, `.bar-fill`, `.hp-fill`, `.mp-fill`, `.effect-chips`, `.effect-chip`, `.effect-buff`, `.effect-debuff`, `.effect-neutral`, `.effect-detail-list`.
- Produces: nothing consumed by later tasks beyond visual rendering (Task 4's JS only toggles the `hidden` attribute and sets `data-bar-pct`-driven widths; it does not depend on any specific CSS values).

- [ ] **Step 1: Add the new CSS rules**

Add to `app/static/css/theme.css`, anywhere within the existing "ADVENTURER CARDS" section (after the `.stat-grid div { ... }` rule shown when this file was last read, so the new rules stay grouped with the other card styling):

```css
.operative-summary {
    padding: 14px 18px 10px;
    cursor: pointer;
}

.operative-summary .operative-header {
    padding: 0 0 10px 0;
    border-bottom: none;
    background: none;
}

.hp-mp-bars {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.resource-bar-track {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.bar-label {
    font-size: 0.7rem;
    color: var(--dungeon-text-dim);
    font-family: var(--ui-font);
}

.bar-track {
    height: 6px;
    background: color-mix(in srgb, var(--dungeon-bg) 70%, transparent);
    border: 1px solid color-mix(in srgb, var(--dungeon-border) 40%, transparent);
    overflow: hidden;
}

.bar-fill {
    height: 100%;
}

.bar-fill.hp-fill {
    background: var(--dungeon-danger);
}

.bar-fill.mp-fill {
    background: var(--dungeon-accent);
}

.effect-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

.effect-chip {
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 10px;
    font-family: var(--ui-font);
    border: 1px solid transparent;
}

.effect-chip.effect-buff {
    background: color-mix(in srgb, var(--dungeon-success) 18%, transparent);
    color: var(--dungeon-success);
    border-color: color-mix(in srgb, var(--dungeon-success) 40%, transparent);
}

.effect-chip.effect-debuff {
    background: color-mix(in srgb, var(--dungeon-danger) 18%, transparent);
    color: var(--dungeon-danger);
    border-color: color-mix(in srgb, var(--dungeon-danger) 40%, transparent);
}

.effect-chip.effect-neutral {
    background: color-mix(in srgb, var(--dungeon-text-dim) 18%, transparent);
    color: var(--dungeon-text-dim);
    border-color: color-mix(in srgb, var(--dungeon-text-dim) 40%, transparent);
}

.effect-detail-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 0.85rem;
    font-family: var(--ui-font);
}

.effect-detail-list li {
    padding: 4px 0;
}

.effect-detail-list li.effect-buff {
    color: var(--dungeon-success);
}

.effect-detail-list li.effect-debuff {
    color: var(--dungeon-danger);
}

.effect-detail-list li.effect-neutral {
    color: var(--dungeon-text-dim);
}
```

No rule is needed for `.operative-detail[hidden]` itself — the native HTML `hidden` attribute already applies `display: none` by default in all browsers, and no existing rule in this file sets `display` on `.operative-detail` (a new class name, no prior rule can conflict).

- [ ] **Step 2: Verify no syntax errors**

```bash
.venv/bin/python -c "
import re
with open('app/static/css/theme.css') as f:
    css = f.read()
assert css.count('{') == css.count('}'), 'mismatched braces'
print('brace count OK:', css.count('{'))
"
```

Expected: prints `brace count OK: <some number>` with no `AssertionError`.

- [ ] **Step 3: Commit**

```bash
git add app/static/css/theme.css
git commit -m "feat(dashboard): style HP/MP bars, effect chips, and active-effects detail list"
```

---

### Task 4: JS — click-to-expand toggle + bar fill application

**Files:**
- Modify: `app/static/js/dashboard-operative-cards.js`
- Modify: `app/static/js/dashboard.js`

**Interfaces:**
- Consumes: `.operative-summary`, `.operative-detail`, `.operative-card`, `.select-operative-label`, `.operative-footer` (from Task 2's template), `[data-bar-pct]` elements with class `.bar-fill` (from Task 2's template).
- Produces: clicking anywhere on `.operative-summary` toggles its sibling `.operative-detail`'s `hidden` attribute, independently per card. `.bar-fill[data-bar-pct]` elements get their `width` set from `data-bar-pct` on page load, mirroring the existing `.xp-fill[data-xp-pct]` pattern in `dashboard.js`.

- [ ] **Step 1: Add the bar-fill width application to `dashboard.js`**

In `app/static/js/dashboard.js`, find the existing XP-bar fill block (near the end of the file, shown when this file was last read):

```js
    // Apply server-rendered XP bar fill percentages (kept out of inline
    // style attrs so templates stay free of style=).
    document.querySelectorAll('.xp-fill[data-xp-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.xpPct + '%';
    });
})();
```

Add a second block right before the closing `})();` (i.e. directly after the `.xp-fill` block, still inside the same IIFE):

```js
    // Apply server-rendered HP/MP bar fill percentages (same pattern as the
    // XP bar above -- kept out of inline style attrs).
    document.querySelectorAll('.bar-fill[data-bar-pct]').forEach((bar) => {
        bar.style.width = bar.dataset.barPct + '%';
    });
})();
```

- [ ] **Step 2: Add the click-to-expand toggle to `dashboard-operative-cards.js`**

In `app/static/js/dashboard-operative-cards.js`, the file currently ends with:

```js
            })
                .catch(() => { });
        });
    }
});
```

Add a new top-level block after the existing `document.addEventListener('DOMContentLoaded', function () { ... });` block closes (i.e. as a sibling statement in the file, not nested inside the existing listener — keeps this new behavior independently readable):

```js
// Click-to-expand: each .operative-summary toggles its own sibling
// .operative-detail independently (no accordion -- any number of cards
// can be expanded at once, so two characters can be compared side by side).
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.operative-summary').forEach((summary) => {
        summary.addEventListener('click', (e) => {
            // Defensive guard: don't toggle if the click originated on a
            // control that has its own handler (SELECT label, footer
            // buttons). Under the current DOM these controls live inside
            // .operative-detail (hidden while collapsed) so this mostly
            // matters if that structure changes later.
            if (e.target.closest('.select-operative-label, .operative-footer, .btn-allocate-stats')) return;
            const card = summary.closest('.operative-card');
            const detail = card.querySelector('.operative-detail');
            if (!detail) return;
            detail.hidden = !detail.hidden;
            card.classList.toggle('expanded', !detail.hidden);
        });
    });
});
```

- [ ] **Step 3: Verify both files are syntactically valid JS**

```bash
node --check app/static/js/dashboard.js
node --check app/static/js/dashboard-operative-cards.js
```

Expected: both commands exit with no output and exit code 0.

- [ ] **Step 4: Commit**

```bash
git add app/static/js/dashboard.js app/static/js/dashboard-operative-cards.js
git commit -m "feat(dashboard): click-to-expand roster cards, apply HP/MP bar widths"
```

---

### Task 5: Live-browser verification

**Files:** none (verification only — no code changes expected; if this step finds a real bug, fix it in the file it lives in and note the fix in the commit message, following this plan's established pattern from Phase B where implementers fixed real bugs found during their own task's verification)

**Interfaces:** none — this task consumes the finished feature from Tasks 1-4 end to end.

- [ ] **Step 1: Start the dev server**

```bash
cd /home/winter/work/Adventure
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python run.py &
sleep 3
```

- [ ] **Step 2: Write a one-off Playwright verification script**

Create `scripts/verify_phase_c_roster_cards.py` (temporary, project already has precedent for one-off Playwright verification scripts per `docs/superpowers/TODO.md`'s mention of `scripts/screenshot_help.py`):

```python
"""One-off Playwright verification for Character Cards Phase C (dashboard
roster card collapse/expand). Not part of the automated test suite -- run
manually against a live dev server, matching this project's established
pattern for template/CSS/JS-only changes with no automated coverage."""

import sys

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        page.goto(f"{BASE_URL}/login")
        page.fill("input[name=username]", "tester")
        page.fill("input[name=password]", "pass")
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE_URL}/dashboard*", timeout=5000)

        cards = page.query_selector_all(".operative-card")
        assert len(cards) >= 1, "expected at least one roster card"

        first_detail = cards[0].query_selector(".operative-detail")
        assert first_detail.is_hidden(), "detail should start hidden (collapsed by default)"

        # Click to expand the first card.
        cards[0].query_selector(".operative-summary").click()
        page.wait_for_timeout(200)
        assert first_detail.is_visible(), "detail should be visible after clicking summary"

        # If a second card exists, expand it too and confirm the first stays expanded
        # (multi-expand, not accordion).
        if len(cards) >= 2:
            second_detail = cards[1].query_selector(".operative-detail")
            cards[1].query_selector(".operative-summary").click()
            page.wait_for_timeout(200)
            assert second_detail.is_visible(), "second card's detail should be visible"
            assert first_detail.is_visible(), "first card should STILL be expanded (multi-expand, not accordion)"

        # Click again to collapse the first card.
        cards[0].query_selector(".operative-summary").click()
        page.wait_for_timeout(200)
        assert first_detail.is_hidden(), "detail should collapse again after a second click"

        # Confirm footer buttons inside the (now-collapsed) first card don't error when
        # the card is re-expanded and a footer button is clicked -- spot-check EQUIP.
        cards[0].query_selector(".operative-summary").click()
        page.wait_for_timeout(200)
        equip_btn = cards[0].query_selector(".btn-equip-panel")
        assert equip_btn is not None, "equip button should exist inside expanded detail"

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        equip_btn.click()
        page.wait_for_timeout(300)
        assert not console_errors, f"console errors after clicking equip: {console_errors}"

        print("All Phase C roster-card checks passed.")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the verification script**

```bash
.venv/bin/python scripts/verify_phase_c_roster_cards.py
```

Expected: `All Phase C roster-card checks passed.` with no assertion errors. If any assertion fails, fix the underlying template/CSS/JS bug it identifies (in whichever Task 1-4 file is responsible) before proceeding — do not weaken the script's assertions to force a pass.

- [ ] **Step 4: Stop the dev server and remove the one-off script**

```bash
kill %1 2>/dev/null || pkill -f "run.py" || true
rm scripts/verify_phase_c_roster_cards.py
```

The script is a verification tool, not a permanent test (no JS/Playwright test infra exists in this repo's CI per established convention) — remove it after use so it doesn't accumulate as dead scaffolding, matching how prior phases' one-off Playwright repro scripts were not committed.

- [ ] **Step 5: Run the full backend test suite**

```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```

Expected: all tests pass, no regressions vs. the pre-Phase-C baseline (437 passed as of the end of Phase B).

- [ ] **Step 6: Update the handoff TODO**

Add an entry to `docs/superpowers/TODO.md` under the Character Cards series (near the Phase A/B entries) summarizing what shipped: collapsed-by-default roster cards, independent multi-expand, HP/MP bars, generic buff/debuff chips, and live-browser-verified interaction. Note Phase D (combat party card redesign) as the next step in the series.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark Character Cards Phase C (dashboard roster redesign) done"
```
