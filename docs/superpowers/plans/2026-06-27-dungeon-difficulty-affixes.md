# Dungeon Difficulty & Affix System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Normal/Heroic/Mythic difficulty selector and stackable opt-in affixes to the dungeon screen, with a named Threat Rating (Calm → Doomed), checklist rows, and achievement hooks on extract.

**Architecture:** `DungeonTier` and `DungeonAffix` tables already exist; add three new columns to `DungeonAffix` (migration), seed tier and affix rows, extend the `start_adventure` POST handler to read `difficulty_tier` and `affix_ids` form fields, add `GET /api/dungeon/affixes`, wire the dungeon tab UI, and hook achievement checks into `extraction_service.py`.

**Tech Stack:** Flask, SQLAlchemy, Alembic, Bootstrap 5, existing `DungeonInstance`, `DungeonTier`, `DungeonAffix`, `achievement` system.

## Global Constraints

- Inline styles prohibited by pre-commit hook
- Difficulty tiers: Normal=1, Heroic=2, Mythic=3 (maps to `DungeonInstance.tier`)
- Threat score = `sum(affix.threat_weight)` + `(tier - 1) * 2`
- Threat names: Calm(0), Troubled(1–2), Dire(3–5), Harrowing(6–9), Catastrophic(10–14), Doomed(15+)
- Config resets on page load — no persistence between sessions
- Affix ids validated server-side; unknown ids silently dropped
- Migration chains after `a1b2c3d4e5f6` (daily quest migration)

---

### Task 1: Migrate `DungeonAffix` — add three columns

**Files:**
- Create: `migrations/versions/b2c3d4e5f6a7_dungeon_affix_columns.py`

**Interfaces:**
- Produces: `dungeon_affix` table gains `monster_count_multiplier FLOAT`, `xp_multiplier FLOAT`, `threat_weight INT`

- [ ] **Step 1: Create migration**

```python
# migrations/versions/b2c3d4e5f6a7_dungeon_affix_columns.py
"""add monster_count_multiplier, xp_multiplier, threat_weight to dungeon_affix

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-27

"""

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dungeon_affix", sa.Column("monster_count_multiplier", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("dungeon_affix", sa.Column("xp_multiplier", sa.Float(), nullable=False, server_default="1.0"))
    op.add_column("dungeon_affix", sa.Column("threat_weight", sa.Integer(), nullable=False, server_default="1"))


def downgrade():
    op.drop_column("dungeon_affix", "threat_weight")
    op.drop_column("dungeon_affix", "xp_multiplier")
    op.drop_column("dungeon_affix", "monster_count_multiplier")
```

- [ ] **Step 2: Apply migration**

```bash
alembic upgrade head
```
Expected: `Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a7`

- [ ] **Step 3: Update `DungeonAffix` model to reflect new columns**

In `app/models/dungeon_tier.py`, add after `special_effect`:

```python
monster_count_multiplier = db.Column(db.Float, nullable=False, default=1.0)
xp_multiplier = db.Column(db.Float, nullable=False, default=1.0)
threat_weight = db.Column(db.Integer, nullable=False, default=1)
```

- [ ] **Step 4: Verify no model errors**

```bash
python3 -c "from app.models.dungeon_tier import DungeonAffix; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/b2c3d4e5f6a7_dungeon_affix_columns.py app/models/dungeon_tier.py
git commit -m "feat(dungeon): add monster_count_multiplier, xp_multiplier, threat_weight to DungeonAffix"
```

---

### Task 2: Seed dungeon tiers and starter affixes

**Files:**
- Create: `app/seed_dungeon_difficulty.py`
- Modify: `run.py` (add `seed-dungeon-difficulty` command)

**Interfaces:**
- Produces: `python run.py seed-dungeon-difficulty` — idempotent, upserts tier rows T1-T3 and 8 affix rows

- [ ] **Step 1: Write a test that verifies idempotency**

```python
# tests/test_seed_dungeon_difficulty.py

def test_seed_is_idempotent(app_context):
    from app.seed_dungeon_difficulty import seed_dungeon_difficulty
    seed_dungeon_difficulty()
    seed_dungeon_difficulty()  # should not raise or duplicate
    from app.models.dungeon_tier import DungeonTier, DungeonAffix
    assert DungeonTier.query.count() >= 3
    assert DungeonAffix.query.count() >= 8
    # No duplicate tier numbers
    tiers = [t.tier for t in DungeonTier.query.all()]
    assert len(tiers) == len(set(tiers))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_seed_dungeon_difficulty.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Create `app/seed_dungeon_difficulty.py`**

```python
"""Idempotent seeding for dungeon difficulty tiers and starter affixes."""

from __future__ import annotations

from app import app as flask_app, db
from app.models.dungeon_tier import DungeonAffix, DungeonTier

TIERS = [
    {"tier": 1, "name": "Normal", "min_level": 1, "max_level": 99,
     "monster_level_modifier": 0, "loot_quality_bonus": 0.0, "xp_multiplier": 1.0,
     "description": "Standard difficulty. No modifiers."},
    {"tier": 2, "name": "Heroic", "min_level": 1, "max_level": 99,
     "monster_level_modifier": 1, "loot_quality_bonus": 0.15, "xp_multiplier": 1.5,
     "description": "Monsters are one level higher. +15% loot quality, ×1.5 XP."},
    {"tier": 3, "name": "Mythic", "min_level": 1, "max_level": 99,
     "monster_level_modifier": 2, "loot_quality_bonus": 0.30, "xp_multiplier": 2.0,
     "description": "Monsters are two levels higher. +30% loot quality, ×2.0 XP."},
]

AFFIXES = [
    {"affix_id": "swarming",    "name": "Swarming",      "threat_weight": 2,
     "monster_count_multiplier": 1.2, "xp_multiplier": 1.1, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.0, "color": "#e74c3c",
     "description": "+20% more monsters, +10% XP."},
    {"affix_id": "bulwark",     "name": "Bulwark",       "threat_weight": 2,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.3,
     "monster_damage_multiplier": 1.0, "color": "#3498db",
     "description": "Monsters have +30% HP."},
    {"affix_id": "savage",      "name": "Savage",        "threat_weight": 2,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.2, "color": "#e67e22",
     "description": "Monsters deal +20% damage."},
    {"affix_id": "thinned",     "name": "Thinned Ranks", "threat_weight": 1,
     "monster_count_multiplier": 0.9, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.1,
     "monster_damage_multiplier": 1.1, "color": "#95a5a6",
     "description": "-10% monsters, but each is +10% stronger."},
    {"affix_id": "bloodthirsty","name": "Bloodthirsty",  "threat_weight": 3,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.0, "color": "#c0392b",
     "description": "Monsters regenerate 2% HP per round.",
     "special_effect": '{"regen_pct": 0.02}'},
    {"affix_id": "cursed",      "name": "Cursed",        "threat_weight": 3,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.0, "color": "#8e44ad",
     "description": "Players take +15% damage.",
     "special_effect": '{"player_damage_taken_multiplier": 1.15}'},
    {"affix_id": "gilded",      "name": "Gilded",        "threat_weight": 1,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.15, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.0, "color": "#f1c40f",
     "description": "+15% XP, -10% loot quality.",
     "special_effect": '{"loot_quality_bonus": -0.10}'},
    {"affix_id": "fortified",   "name": "Fortified",     "threat_weight": 2,
     "monster_count_multiplier": 1.0, "xp_multiplier": 1.0, "monster_hp_multiplier": 1.0,
     "monster_damage_multiplier": 1.0, "color": "#1abc9c",
     "description": "Bosses have +50% HP.",
     "special_effect": '{"boss_hp_multiplier": 1.5}'},
]


def seed_dungeon_difficulty(verbose: bool = False) -> None:
    with flask_app.app_context():
        for spec in TIERS:
            existing = DungeonTier.query.filter_by(tier=spec["tier"]).first()
            if existing:
                for k, v in spec.items():
                    setattr(existing, k, v)
            else:
                db.session.add(DungeonTier(**spec))
            if verbose:
                print(f"  tier {spec['tier']}: {spec['name']}")

        for spec in AFFIXES:
            existing = DungeonAffix.query.filter_by(affix_id=spec["affix_id"]).first()
            if existing:
                for k, v in spec.items():
                    setattr(existing, k, v)
            else:
                db.session.add(DungeonAffix(**spec))
            if verbose:
                print(f"  affix {spec['affix_id']}: {spec['name']}")

        db.session.commit()
        if verbose:
            print("Done.")


if __name__ == "__main__":
    seed_dungeon_difficulty(verbose=True)
```

- [ ] **Step 4: Add `seed-dungeon-difficulty` command to `run.py`**

After the `seed-themes` parser block, add:

```python
# seed-dungeon-difficulty subcommand
seed_dungeon_parser = subparsers.add_parser(
    "seed-dungeon-difficulty",
    help="Seed Normal/Heroic/Mythic tiers and starter affixes (idempotent).",
    description="Upsert DungeonTier rows T1-T3 and 8 starter DungeonAffix rows.",
)
seed_dungeon_parser.set_defaults(command="seed-dungeon-difficulty")
```

In the `elif mode == ...` dispatch section, add:

```python
elif mode == "seed-dungeon-difficulty":
    from app.seed_dungeon_difficulty import seed_dungeon_difficulty
    seed_dungeon_difficulty(verbose=True)
    return 0
```

- [ ] **Step 5: Run seed and test**

```bash
python run.py seed-dungeon-difficulty
pytest tests/test_seed_dungeon_difficulty.py -v
```
Expected: seed prints tier/affix names, test PASS

- [ ] **Step 6: Commit**

```bash
git add app/seed_dungeon_difficulty.py run.py tests/test_seed_dungeon_difficulty.py
git commit -m "feat(dungeon): seed Normal/Heroic/Mythic tiers and 8 starter affixes"
```

---

### Task 3: `GET /api/dungeon/affixes` endpoint

**Files:**
- Modify: `app/routes/dungeon_api.py`

**Interfaces:**
- Produces: `GET /api/dungeon/affixes` → `[{affix_id, name, description, threat_weight, color, monster_hp_multiplier, monster_damage_multiplier, monster_count_multiplier, xp_multiplier}]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dungeon_affixes_api.py

def test_get_affixes_returns_list(client, logged_in_user, seeded_affixes):
    resp = client.get('/api/dungeon/affixes')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) >= 8
    assert all('affix_id' in a and 'threat_weight' in a for a in data)

def test_get_affixes_unauthenticated(client):
    resp = client.get('/api/dungeon/affixes')
    assert resp.status_code in (401, 302)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_dungeon_affixes_api.py -v
```
Expected: FAIL — 404 or no route

- [ ] **Step 3: Add route to `app/routes/dungeon_api.py`**

```python
@bp_dungeon.route("/api/dungeon/affixes")
@login_required
def get_affixes():
    from app.models.dungeon_tier import DungeonAffix
    affixes = DungeonAffix.query.all()
    return jsonify([{
        "affix_id": a.affix_id,
        "name": a.name,
        "description": a.description,
        "threat_weight": a.threat_weight,
        "color": a.color or "#888",
        "monster_hp_multiplier": a.monster_hp_multiplier,
        "monster_damage_multiplier": a.monster_damage_multiplier,
        "monster_count_multiplier": a.monster_count_multiplier,
        "xp_multiplier": a.xp_multiplier,
    } for a in affixes])
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_dungeon_affixes_api.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/dungeon_api.py tests/test_dungeon_affixes_api.py
git commit -m "feat(dungeon): add GET /api/dungeon/affixes endpoint"
```

---

### Task 4: Extend `start_adventure` to accept difficulty and affixes

**Files:**
- Modify: `app/routes/dashboard.py` (`start_adventure` form handler, ~line 112)

**Interfaces:**
- Consumes: form fields `difficulty_tier` (int, default 1) and `affix_ids` (JSON string, default `"[]"`)
- Produces: `DungeonInstance.tier` and `DungeonInstance.affix_ids` set on new instance

- [ ] **Step 1: Write the failing test**

```python
# tests/test_start_adventure_difficulty.py

def test_start_adventure_sets_tier(client, logged_in_user, party_ready):
    char_ids = party_ready
    resp = client.post('/', data={
        'form': 'start_adventure',
        'party_ids': char_ids,
        'difficulty_tier': '2',
        'affix_ids': '["swarming"]',
    }, follow_redirects=False)
    assert resp.status_code in (302, 200)

    from flask import session
    with client.session_transaction() as sess:
        instance_id = sess.get('dungeon_instance_id')
    assert instance_id is not None

    from app.models.dungeon_instance import DungeonInstance
    from app import db
    with client.application.app_context():
        instance = db.session.get(DungeonInstance, instance_id)
        assert instance.tier == 2
        assert 'swarming' in instance.get_affixes()

def test_start_adventure_invalid_affix_dropped(client, logged_in_user, party_ready):
    char_ids = party_ready
    client.post('/', data={
        'form': 'start_adventure',
        'party_ids': char_ids,
        'difficulty_tier': '1',
        'affix_ids': '["nonexistent-affix"]',
    }, follow_redirects=False)
    with client.session_transaction() as sess:
        instance_id = sess.get('dungeon_instance_id')
    from app.models.dungeon_instance import DungeonInstance
    from app import db
    with client.application.app_context():
        instance = db.session.get(DungeonInstance, instance_id)
        assert instance.get_affixes() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_start_adventure_difficulty.py -v
```
Expected: FAIL — tier defaults to 1 and affixes not read

- [ ] **Step 3: Update `start_adventure` handler in `dashboard.py`**

Find the block that creates `DungeonInstance` (around line 189–205). Before `db.session.add(instance)`:

```python
# Read difficulty and affix config from form
try:
    difficulty_tier = max(1, min(3, int(request.form.get("difficulty_tier", 1))))
except (ValueError, TypeError):
    difficulty_tier = 1

raw_affix_ids = request.form.get("affix_ids", "[]")
try:
    submitted_affixes = json.loads(raw_affix_ids)
    if not isinstance(submitted_affixes, list):
        submitted_affixes = []
except Exception:
    submitted_affixes = []

# Validate against known affixes
from app.models.dungeon_tier import DungeonAffix
valid_affix_ids = {a.affix_id for a in DungeonAffix.query.all()}
affix_ids = [a for a in submitted_affixes if a in valid_affix_ids]
```

Then on the `DungeonInstance(...)` constructor call, add:

```python
instance = DungeonInstance(
    user_id=current_user_id,
    seed=seed,
    pos_x=0, pos_y=0, pos_z=0,
    monster_family=pick_monster_family(seed),
    tier=difficulty_tier,  # ← add this
)
instance.set_affixes(affix_ids)  # ← add after construction
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_start_adventure_difficulty.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/dashboard.py tests/test_start_adventure_difficulty.py
git commit -m "feat(dungeon): read difficulty_tier and affix_ids from start_adventure form"
```

---

### Task 5: Dungeon screen UI — difficulty selector, affix picker, checklist rows

**Files:**
- Modify: `app/templates/dashboard.html` (dungeon tab pane)
- Create: `app/static/css/dungeon-config.css`
- Create: `app/static/js/dungeon-config.js`
- Modify: `app/static/css/app.css` (add import)

**Interfaces:**
- Consumes: `GET /api/dungeon/affixes`
- Produces: hidden form fields `difficulty_tier`, `affix_ids` injected into the `start_adventure` form on submit; checklist rows; Threat Rating display

- [ ] **Step 1: Create `app/static/css/dungeon-config.css`**

```css
/* dungeon-config.css — Difficulty selector and affix picker */

.difficulty-btn-group .btn {
    min-width: 90px;
}

.affix-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px;
    margin-top: 8px;
}

.affix-card {
    border: 2px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 8px 10px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    user-select: none;
}

.affix-card:hover {
    border-color: rgba(255,255,255,0.3);
}

.affix-card.selected {
    border-color: var(--affix-color, #7c3aed);
    background: rgba(124,58,237,0.08);
}

.affix-card-name {
    font-weight: 600;
    font-size: 0.9rem;
}

.affix-card-desc {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.6);
    margin-top: 2px;
}

.affix-threat-badge {
    font-size: 0.7rem;
    margin-left: 4px;
    vertical-align: middle;
}

.threat-rating-display {
    font-size: 0.85rem;
    font-weight: 600;
}

.threat-calm        { color: #6c757d; }
.threat-troubled    { color: #0dcaf0; }
.threat-dire        { color: #ffc107; }
.threat-harrowing   { color: #fd7e14; }
.threat-catastrophic{ color: #dc3545; }
.threat-doomed      { color: #6f42c1; }
```

- [ ] **Step 2: Add import to `app/static/css/app.css`**

```css
@import url("dungeon-config.css");
```

- [ ] **Step 3: Create `app/static/js/dungeon-config.js`**

```javascript
// dungeon-config.js — difficulty/affix selector for dungeon screen
(function () {
  const THREAT_NAMES = [
    [0,  0,  'Calm',         'threat-calm'],
    [1,  2,  'Troubled',     'threat-troubled'],
    [3,  5,  'Dire',         'threat-dire'],
    [6,  9,  'Harrowing',    'threat-harrowing'],
    [10, 14, 'Catastrophic', 'threat-catastrophic'],
    [15, Infinity, 'Doomed', 'threat-doomed'],
  ];

  let tier = 1;
  let selectedAffixes = new Set();
  let affixData = [];

  function threatInfo(score) {
    for (const [lo, hi, name, cls] of THREAT_NAMES) {
      if (score >= lo && score <= hi) return { name, cls };
    }
    return { name: 'Doomed', cls: 'threat-doomed' };
  }

  function threatScore() {
    const affixWeight = affixData
      .filter(a => selectedAffixes.has(a.affix_id))
      .reduce((s, a) => s + (a.threat_weight || 1), 0);
    return affixWeight + (tier - 1) * 2;
  }

  function updateChecklist() {
    const tierNames = { 1: 'Normal', 2: 'Heroic', 3: 'Mythic' };
    const diffRow = document.getElementById('dungeon-check-difficulty');
    if (diffRow) diffRow.textContent = `Difficulty: ${tierNames[tier] || 'Normal'}`;

    const score = threatScore();
    const info = threatInfo(score);
    const affixRow = document.getElementById('dungeon-check-affixes');
    if (affixRow) {
      if (selectedAffixes.size === 0) {
        affixRow.innerHTML = '<span class="text-muted">No affixes selected</span>';
      } else {
        const names = affixData
          .filter(a => selectedAffixes.has(a.affix_id))
          .map(a => a.name)
          .join(', ');
        affixRow.innerHTML = `${names} <span class="threat-rating-display ${info.cls}">[${info.name}]</span>`;
      }
    }

    // Sync hidden form fields
    const tierField = document.getElementById('hidden-difficulty-tier');
    if (tierField) tierField.value = tier;
    const affixField = document.getElementById('hidden-affix-ids');
    if (affixField) affixField.value = JSON.stringify([...selectedAffixes]);
  }

  function renderAffixGrid() {
    const grid = document.getElementById('affix-grid');
    if (!grid) return;
    grid.innerHTML = affixData.map(a => {
      const sel = selectedAffixes.has(a.affix_id) ? 'selected' : '';
      const color = a.color || '#888';
      return `<div class="affix-card ${sel}" data-affix-id="${a.affix_id}"
        style="--affix-color:${color}">
        <div class="affix-card-name" style="color:${color}">${a.name}
          <span class="badge bg-secondary affix-threat-badge">⚠${a.threat_weight}</span>
        </div>
        <div class="affix-card-desc">${a.description || ''}</div>
      </div>`;
    }).join('');

    grid.querySelectorAll('.affix-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = card.dataset.affixId;
        if (selectedAffixes.has(id)) selectedAffixes.delete(id);
        else selectedAffixes.add(id);
        card.classList.toggle('selected');
        updateChecklist();
      });
    });
  }

  async function init() {
    // Difficulty buttons
    document.querySelectorAll('.difficulty-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.remove('active', 'btn-primary'));
        document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.add('btn-outline-secondary'));
        btn.classList.remove('btn-outline-secondary');
        btn.classList.add('active', 'btn-primary');
        tier = parseInt(btn.dataset.tier, 10);
        updateChecklist();
      });
    });

    // Fetch affixes
    try {
      const resp = await fetch('/api/dungeon/affixes');
      if (resp.ok) {
        affixData = await resp.json();
        renderAffixGrid();
      }
    } catch (e) {
      console.warn('[dungeon-config] failed to load affixes', e);
    }

    updateChecklist();
  }

  // Init when dungeon tab becomes active
  document.addEventListener('DOMContentLoaded', () => {
    const dungeonTab = document.querySelector('[data-bs-target="#lobby-dungeon"]');
    if (dungeonTab) {
      dungeonTab.addEventListener('shown.bs.tab', init);
    } else {
      // Already on dungeon tab (direct load)
      init();
    }
  });
})();
```

- [ ] **Step 4: Add difficulty selector, affix picker, and checklist rows to dungeon tab in `dashboard.html`**

Find the `#lobby-dungeon` tab pane. Add before the seed widget section:

```html
<!-- Difficulty selector -->
<div class="mb-3">
  <div class="small text-muted mb-1">DIFFICULTY</div>
  <div class="btn-group difficulty-btn-group" role="group">
    <button type="button" class="btn btn-primary difficulty-btn active" data-tier="1">NORMAL</button>
    <button type="button" class="btn btn-outline-secondary difficulty-btn" data-tier="2">
      HEROIC <small class="d-block" style="font-size:0.65rem">+1 lvl · ×1.5 XP</small>
    </button>
    <button type="button" class="btn btn-outline-secondary difficulty-btn" data-tier="3">
      MYTHIC <small class="d-block" style="font-size:0.65rem">+2 lvl · ×2.0 XP</small>
    </button>
  </div>
</div>

<!-- Affix picker -->
<div class="mb-3">
  <div class="small text-muted mb-1">AFFIXES <span class="text-muted">(optional — stack for more challenge)</span></div>
  <div class="affix-grid" id="affix-grid">
    <div class="text-muted small">Loading affixes…</div>
  </div>
</div>
```

Find the dungeon checklist `<ul>` (the list showing party alive/ready checks). Add two new `<li>` items:

```html
<li class="list-group-item d-flex align-items-center gap-2">
  <i class="bi bi-shield-fill text-info"></i>
  <span id="dungeon-check-difficulty">Difficulty: Normal</span>
</li>
<li class="list-group-item d-flex align-items-center gap-2">
  <i class="bi bi-lightning-fill text-warning"></i>
  <span id="dungeon-check-affixes"><span class="text-muted">No affixes selected</span></span>
</li>
```

Add hidden form fields inside the `start_adventure` form:

```html
<input type="hidden" id="hidden-difficulty-tier" name="difficulty_tier" value="1">
<input type="hidden" id="hidden-affix-ids" name="affix_ids" value="[]">
```

Add script tag at end of dungeon tab section (or in the scripts block):

```html
<script src="{{ url_for('static', filename='js/dungeon-config.js') }}?v={{ version }}"></script>
```

- [ ] **Step 5: Restart and smoke test**

```bash
./manage.sh restart
```

Open dashboard → Dungeon tab. Verify:
- NORMAL / HEROIC / MYTHIC buttons render, clicking toggles active state
- Affix cards load and toggle selected state on click
- Checklist shows "Difficulty: Normal" and "No affixes selected" by default
- Selecting Heroic + Swarming shows `[Dire]` threat rating in checklist
- Entering dungeon with tier=2 sets `DungeonInstance.tier = 2`

- [ ] **Step 6: Commit**

```bash
git add app/static/css/dungeon-config.css app/static/css/app.css \
        app/static/js/dungeon-config.js app/templates/dashboard.html
git commit -m "feat(dungeon): add difficulty selector, affix picker, threat rating to dungeon screen"
```

---

### Task 6: Achievement hooks on extraction

**Files:**
- Modify: `app/services/extraction_service.py`
- Modify: `app/routes/achievement_api.py` (or wherever achievements are seeded/checked)

**Interfaces:**
- Consumes: `DungeonInstance.tier`, `DungeonInstance.get_affixes()`, threat score calculation
- Produces: achievement checks fire on successful extraction; new achievement slugs seeded

- [ ] **Step 1: Verify achievement system API**

```bash
grep -n "def.*achieve\|unlock\|grant" /home/winter/work/Adventure/app/routes/achievement_api.py | head -10
grep -n "def.*achieve\|unlock\|grant" /home/winter/work/Adventure/app/services/*.py 2>/dev/null | head -10
```

Note the exact function name for granting achievements — it will be used in Step 3.

- [ ] **Step 2: Seed new achievement rows**

Find the existing achievement seed file (check `app/seed_achievements.py` or similar). Add the following achievement specs (idempotent upsert by slug):

```python
DUNGEON_DIFFICULTY_ACHIEVEMENTS = [
    {"slug": "first-heroic-run",    "title": "Proving Ground",   "description": "Complete your first Heroic run."},
    {"slug": "first-mythic-run",    "title": "Into the Abyss",   "description": "Complete your first Mythic run."},
    {"slug": "first-affix-run",     "title": "Glutton for Punishment", "description": "Complete a run with at least one affix active."},
    {"slug": "three-affix-run",     "title": "Chaos Incarnate",  "description": "Complete a run with 3 or more affixes simultaneously."},
    {"slug": "threat-harrowing",    "title": "This Is Fine",     "description": "Reach Threat Rating: Harrowing."},
    {"slug": "threat-doomed",       "title": "Absolute Madness", "description": "Reach Threat Rating: Doomed."},
    {"slug": "mythic-two-affixes",  "title": "No Survivors",     "description": "Complete a Mythic run with 2 or more affixes."},
    {"slug": "death-wish",          "title": "Death Wish",       "description": "Complete a run with both Cursed and Savage active."},
    {"slug": "gold-rush",           "title": "Gold Rush",        "description": "Complete a run with both Gilded and Swarming active."},
]
```

Run the seed: `python run.py seed-achievements` (use existing command; just add these rows to the existing seed data file).

- [ ] **Step 3: Add achievement check to `extract_party()`**

In `app/services/extraction_service.py`, at the end of `extract_party()` just before the final `return True, message, result`:

```python
# Achievement checks for difficulty/affix milestones
try:
    from app.models.dungeon_tier import DungeonAffix as _Affix
    affix_ids = instance.get_affixes()
    tier = instance.tier or 1

    # Compute threat score
    weights = {a.affix_id: a.threat_weight for a in _Affix.query.all()}
    threat_score = sum(weights.get(a, 1) for a in affix_ids) + (tier - 1) * 2

    from app.services import achievement_service  # adjust import to match your module

    def _check(slug, condition):
        if condition:
            achievement_service.unlock(user_id, slug)

    _check("first-heroic-run",   tier >= 2)
    _check("first-mythic-run",   tier >= 3)
    _check("first-affix-run",    len(affix_ids) >= 1)
    _check("three-affix-run",    len(affix_ids) >= 3)
    _check("threat-harrowing",   threat_score >= 6)
    _check("threat-doomed",      threat_score >= 15)
    _check("mythic-two-affixes", tier >= 3 and len(affix_ids) >= 2)
    _check("death-wish",         "cursed" in affix_ids and "savage" in affix_ids)
    _check("gold-rush",          "gilded" in affix_ids and "swarming" in affix_ids)
except Exception as e:
    import logging
    logging.getLogger(__name__).warning("achievement_check_failed", extra={"error": str(e)})
```

> **Note:** The import path `app.services.achievement_service` and function name `achievement_service.unlock(user_id, slug)` must match what actually exists. Run `grep -rn "def unlock\|def grant_achievement" app/` before wiring to confirm the correct call signature.

- [ ] **Step 4: Run existing achievement tests to confirm no regressions**

```bash
pytest tests/ -k "achievement" -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/extraction_service.py
git commit -m "feat(dungeon): hook difficulty/affix achievements into extraction"
```

---

### Task 7: Manual end-to-end smoke test

- [ ] **Step 1: Restart and seed**

```bash
./manage.sh restart
python run.py seed-dungeon-difficulty
```

- [ ] **Step 2: Dungeon tab UI check**

- NORMAL / HEROIC / MYTHIC buttons present and toggle correctly
- Affix cards load (8 cards visible)
- Selecting Heroic (score=2) + Swarming (weight=2) shows `[Dire]` threat (score=4)
- Selecting Heroic + Swarming + Savage (weight=2) shows `[Harrowing]` (score=6)
- Checklist shows correct difficulty name and affix list

- [ ] **Step 3: Run a Heroic dungeon**

- Select Heroic, enter dungeon, confirm `DungeonInstance.tier = 2` in DB:

```bash
python3 -c "
from app import app, db
from app.models.dungeon_instance import DungeonInstance
with app.app_context():
    inst = DungeonInstance.query.order_by(DungeonInstance.id.desc()).first()
    print('tier:', inst.tier, 'affixes:', inst.get_affixes())
"
```

- [ ] **Step 4: Commit any fixes**

```bash
git add -p
git commit -m "fix(dungeon): smoke test fixes for difficulty/affix system"
```
