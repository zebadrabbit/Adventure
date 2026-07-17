# Class Skill Trees + Starting Skills + Full-Clear Bonus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every class starts with a class-appropriate active skill and has a real archetype skill tree to grow into; clearing every mob plus the boss grants an extraction bonus and achievement.

**Architecture:** Pure content + thin wiring on existing systems. Skills are seed data through the existing `seed_skills.py` upsert; class gating extends the existing single-string `class_requirement` to a comma-separated list (checked server-side at unlock, filtered client-side for display); starting skills are a cost-free `CharacterSkill` row created at the three character-creation sites; full-clear is a derived check (`bosses_defeated >= bosses_total` AND zero remaining monster entities) applied inside `extract_party`.

**Tech Stack:** Flask/SQLAlchemy, existing skill/achievement/extraction services, vanilla JS.

## Global Constraints

- Skill `effect_json` may ONLY use the existing vocabulary — actives: `damage`, `spell_damage`, `heal` (what `combat_service.player_cast_skill` applies); passives: the six ability stats `str/dex/con/int/wis/cha` (what `skill_effects.passive_bonuses` sums). No new effect keys, no new combat mechanics.
- The character's class is `stats["class"]` (JSON), lowercase; the 12 classes are: fighter, rogue, mage, cleric, ranger, druid, barbarian, bard, monk, paladin, sorcerer, warlock.
- `SkillTree.class_requirement` is `db.String(30)` — every comma-separated value below fits; do NOT widen the column.
- All seeding must stay idempotent (upsert by name / (tree, name)), matching `seed_skills.py`'s existing pattern.
- Tests: `cd /home/winter/work/Adventure && source .venv/bin/activate && TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test pytest -q` (never `-x`). Suite is currently fully green (512 passed, 1 skipped, 1 xpassed) and must stay green.
- Pre-commit hooks may reformat; re-add and retry the commit.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## Canonical content tables (used by Tasks 1 and 3 — values are final)

Archetype trees (`class_requirement` exactly as written; `Combat` tree already exists and stays universal):

| Tree | class_requirement | Description |
|---|---|---|
| Martial | `fighter,barbarian,monk` | Strength of arms. |
| Arcana | `mage,sorcerer` | Arcane study. (existing tree — requirement changes from `mage`) |
| Divine | `cleric,paladin` | Channel holy power. |
| Nature | `druid,ranger` | The wild answers. |
| Shadow | `rogue,bard` | Guile and precision. |
| Occult | `warlock` | Forbidden bargains. |

Skills per tree (T1 active is the class's **starting skill**; existing Arcana skills Focus/Firebolt are kept, so Arcana only adds the three T2/T3 rows):

| Tree | Name | tier | req_lvl | cost | type | cooldown | effect | required_skill |
|---|---|---|---|---|---|---|---|---|
| Martial | Crushing Blow | 1 | 1 | 1 | active | 3 | `{"damage": 6}` | — |
| Martial | Iron Body | 1 | 1 | 1 | passive | — | `{"con": 2}` | — |
| Martial | Cleave | 2 | 3 | 2 | active | 4 | `{"damage": 12}` | — |
| Martial | Bulwark | 2 | 3 | 2 | passive | — | `{"str": 2, "con": 1}` | — |
| Martial | Execute | 3 | 5 | 3 | active | 6 | `{"damage": 20}` | Cleave |
| Arcana | Focus *(exists)* | 1 | 1 | 1 | passive | — | `{"int": 2}` | — |
| Arcana | Firebolt *(exists)* | 1 | 1 | 1 | active | 2 | `{"spell_damage": 8}` | — |
| Arcana | Frost Lance | 2 | 3 | 2 | active | 4 | `{"spell_damage": 14}` | — |
| Arcana | Clarity | 2 | 3 | 2 | passive | — | `{"int": 2, "wis": 1}` | — |
| Arcana | Arcane Blast | 3 | 5 | 3 | active | 6 | `{"spell_damage": 22}` | Frost Lance |
| Divine | Smite | 1 | 1 | 1 | active | 3 | `{"spell_damage": 6}` | — |
| Divine | Faith | 1 | 1 | 1 | passive | — | `{"wis": 2}` | — |
| Divine | Healing Word | 2 | 3 | 2 | active | 4 | `{"heal": 12}` | — |
| Divine | Devotion | 2 | 3 | 2 | passive | — | `{"wis": 2, "con": 1}` | — |
| Divine | Divine Wrath | 3 | 5 | 3 | active | 6 | `{"spell_damage": 18}` | Healing Word |
| Nature | Thorn Lash | 1 | 1 | 1 | active | 3 | `{"spell_damage": 6}` | — |
| Nature | Wild Sense | 1 | 1 | 1 | passive | — | `{"wis": 2}` | — |
| Nature | Regrowth | 2 | 3 | 2 | active | 4 | `{"heal": 12}` | — |
| Nature | Barkskin | 2 | 3 | 2 | passive | — | `{"con": 2, "wis": 1}` | — |
| Nature | Entangling Storm | 3 | 5 | 3 | active | 6 | `{"spell_damage": 18}` | Regrowth |
| Shadow | Backstab | 1 | 1 | 1 | active | 3 | `{"damage": 7}` | — |
| Shadow | Nimble | 1 | 1 | 1 | passive | — | `{"dex": 2}` | — |
| Shadow | Flurry | 2 | 3 | 2 | active | 4 | `{"damage": 13}` | — |
| Shadow | Silver Tongue | 2 | 3 | 2 | passive | — | `{"cha": 2, "dex": 1}` | — |
| Shadow | Assassinate | 3 | 5 | 3 | active | 6 | `{"damage": 20}` | Flurry |
| Occult | Eldritch Bolt | 1 | 1 | 1 | active | 3 | `{"spell_damage": 7}` | — |
| Occult | Dark Pact | 1 | 1 | 1 | passive | — | `{"cha": 2}` | — |
| Occult | Life Tap | 2 | 3 | 2 | active | 4 | `{"heal": 10}` | — |
| Occult | Void Insight | 2 | 3 | 2 | passive | — | `{"cha": 2, "int": 1}` | — |
| Occult | Doom | 3 | 5 | 3 | active | 6 | `{"spell_damage": 22}` | Life Tap |

Starting-skill map (class → tree T1 active): fighter/barbarian/monk → Crushing Blow (Martial); mage/sorcerer → Firebolt (Arcana); cleric/paladin → Smite (Divine); druid/ranger → Thorn Lash (Nature); rogue/bard → Backstab (Shadow); warlock → Eldritch Bolt (Occult).

---

### Task 1: Seed the six archetype trees and their skills

**Files:**
- Modify: `app/seed_skills.py` (TREES and SKILLS tables; the upsert code already handles new entries — content-only change)
- Test: `tests/test_seed_skills_archetypes.py` (create)

**Interfaces:**
- Consumes: existing `seed_skills()` upsert machinery (unchanged).
- Produces: DB rows for the 6 trees / 27 skills above. Later tasks look up trees by exact `name` and skills by exact `name` within a tree — spelling in the canonical table is binding.

- [ ] **Step 1: Write the failing test**

```python
"""Archetype skill trees seed content."""
from app import app as flask_app
from app.models.skill import Skill, SkillTree
from app.seed_skills import seed_skills

EXPECTED_TREES = {
    "Combat": None,
    "Martial": "fighter,barbarian,monk",
    "Arcana": "mage,sorcerer",
    "Divine": "cleric,paladin",
    "Nature": "druid,ranger",
    "Shadow": "rogue,bard",
    "Occult": "warlock",
}
STARTING_ACTIVES = {
    "Martial": "Crushing Blow",
    "Arcana": "Firebolt",
    "Divine": "Smite",
    "Nature": "Thorn Lash",
    "Shadow": "Backstab",
    "Occult": "Eldritch Bolt",
}


def test_seed_creates_all_archetype_trees(test_app):
    with flask_app.app_context():
        seed_skills(verbose=False)
        for name, req in EXPECTED_TREES.items():
            tree = SkillTree.query.filter_by(name=name).first()
            assert tree is not None, f"tree {name} missing"
            assert tree.class_requirement == req


def test_every_tree_has_tier1_active_and_prereqs_resolve(test_app):
    with flask_app.app_context():
        seed_skills(verbose=False)
        for tree_name, skill_name in STARTING_ACTIVES.items():
            tree = SkillTree.query.filter_by(name=tree_name).first()
            s = Skill.query.filter_by(tree_id=tree.id, name=skill_name).first()
            assert s is not None and s.skill_type == "active" and s.tier == 1 and s.required_level == 1
        # every tier-3 skill has a resolved prerequisite in the same tree
        for s in Skill.query.filter_by(tier=3).all():
            assert s.required_skill_id is not None


def test_seed_is_idempotent(test_app):
    with flask_app.app_context():
        n1 = seed_skills(verbose=False)
        n2 = seed_skills(verbose=False)
        assert n1 == n2
        assert Skill.query.count() == Skill.query.distinct(Skill.tree_id, Skill.name).count()
```

(Adapt the fixture name to what `tests/conftest.py` actually provides — look at an existing seed test such as `tests/test_seed_items_level.py` for the established pattern, including any `db_isolation` marker convention.)

- [ ] **Step 2: Run it, confirm it fails** (`pytest tests/test_seed_skills_archetypes.py -q` → trees missing)
- [ ] **Step 3: Add the content** — extend `TREES` and `SKILLS` in `app/seed_skills.py` with exactly the canonical tables above (Arcana tree entry's `class_requirement` becomes `"mage,sorcerer"`; keep its existing two skills; append the other 25 skill dicts using the existing dict shape: `tree/name/description/tier/required_level/cost/skill_type/cooldown/effect/required_skill`). Write one-line flavor descriptions for each new skill.
- [ ] **Step 4: Run the test file → PASS; run full suite → green**
- [ ] **Step 5: Commit** — `feat(skills): seed six class-archetype skill trees (27 skills)`

---

### Task 2: Class gating — server-enforced, comma-aware

**Files:**
- Modify: `app/models/skill.py` (add `SkillTree.allows_class`)
- Modify: `app/routes/skill_api.py::unlock_skill` (enforce)
- Modify: `app/static/js/skill-tree.js` (filter tree list by the character's class; show all comma classes in the selector label)
- Test: `tests/test_skill_class_gating.py` (create)

**Interfaces:**
- Consumes: `stats["class"]` (lowercase string in the character's stats JSON).
- Produces: `SkillTree.allows_class(char_class: str | None) -> bool` — `True` when `class_requirement` is `None`/empty (universal) or when `char_class` is in the comma-separated list (case-insensitive, whitespace-tolerant). Task 3 reuses it.

- [ ] **Step 1: Write the failing test**

```python
import json
from app import app as flask_app, db
from app.models.skill import Skill, SkillTree
from app.seed_skills import seed_skills


def test_allows_class():
    t = SkillTree(name="x", class_requirement="mage,sorcerer")
    assert t.allows_class("sorcerer") and t.allows_class("MAGE")
    assert not t.allows_class("fighter") and not t.allows_class(None)
    u = SkillTree(name="y", class_requirement=None)
    assert u.allows_class("fighter") and u.allows_class(None)


def test_unlock_rejects_wrong_class(auth_client, test_app):
    # find the logged-in user's character, force class to fighter, then try to
    # unlock an Arcana (mage,sorcerer) skill -> 403
    ...
```

Write the endpoint test concretely against the existing patterns in `tests/test_skill_unlock.py` (same client fixture, same way of fabricating a character + talent points); assert a 403 with an error naming the class restriction, and that unlocking a Combat (universal) skill still succeeds for the same character.

- [ ] **Step 2: RED**, then implement:

```python
# app/models/skill.py — on SkillTree
def allows_class(self, char_class: str | None) -> bool:
    """True if this tree is universal or char_class is in the comma list."""
    if not self.class_requirement:
        return True
    if not char_class:
        return False
    allowed = {c.strip().lower() for c in self.class_requirement.split(",")}
    return char_class.strip().lower() in allowed
```

In `unlock_skill` (after the skill lookup, before the level check):

```python
import json as _json
tree = db.session.get(SkillTree, skill.tree_id)
try:
    char_class = (_json.loads(character.stats) or {}).get("class")
except Exception:
    char_class = None
if tree and not tree.allows_class(char_class):
    return jsonify({"error": f"{tree.name} requires class: {tree.class_requirement}"}), 403
```

(Match the file's existing import style — `json` may already be imported.)

- [ ] **Step 3: skill-tree.js** — where the tree selector is built (the code that renders `tree.class_requirement || 'Universal'`, ~line 86): filter the fetched tree list to `!tree.class_requirement || tree.class_requirement.split(',').map(s => s.trim().toLowerCase()).includes(characterClass)` where `characterClass` is the lowercase class of the character whose tree was opened (the surrounding code already knows which character it opened the modal for — find how it gets the character and reuse; if the class isn't in scope, fetch it from the same character payload the dashboard already exposes rather than adding a new endpoint).
- [ ] **Step 4: GREEN + full suite green**
- [ ] **Step 5: Commit** — `feat(skills): enforce class-gated skill trees (comma-separated classes), filter tree UI`

---

### Task 3: Starting skill at character creation

**Files:**
- Modify: `app/services/progression.py` (add `grant_starting_skill`)
- Modify: `app/routes/dashboard.py` (~line 272 and ~line 415 — after each `Character(...)` is flushed/committed with an id)
- Modify: `app/routes/dashboard_helpers.py` (~line 350, the autofill creation loop — same hook)
- Test: `tests/test_starting_skills.py` (create)

**Interfaces:**
- Consumes: `SkillTree.allows_class` (Task 2), seeded content (Task 1).
- Produces: `grant_starting_skill(character) -> Skill | None` — creates a cost-free `CharacterSkill` (rank 1) for the tier-1 active of the first archetype tree matching the character's class; falls back to the universal `Combat` tree's tier-1 active when no archetype tree matches; returns the granted Skill or None (already-granted / no skills seeded). Never touches talent points. Idempotent.

- [ ] **Step 1: Failing test** — for each of the 12 classes: build a character (reuse the factory/fixture pattern from `tests/factories.py` or `tests/test_levelup_gating.py`), call `grant_starting_skill`, assert exactly one `CharacterSkill` exists, it is `skill_type == "active"`, `tier == 1`, belongs to a tree where `allows_class(cls)` is true, and `CharacterTalentPoints` for the character is absent or has `total_spent == 0`. Plus: calling it twice grants nothing new; a DB with no seeded skills returns `None` without raising.
- [ ] **Step 2: RED**, then implement:

```python
def grant_starting_skill(character):
    """Give a freshly created character its class's tier-1 active, cost-free.

    Chooses the first active tier-1 skill in a class-gated tree that allows
    the character's class (archetype trees are the only class-gated ones);
    falls back to the universal Combat tree. Idempotent; never spends points.
    """
    import json as _json

    from app.models.skill import CharacterSkill, Skill, SkillTree

    try:
        char_class = (_json.loads(character.stats) or {}).get("class")
    except Exception:
        char_class = None

    trees = SkillTree.query.filter_by(is_active=True).all()
    gated = [t for t in trees if t.class_requirement and t.allows_class(char_class)]
    universal = [t for t in trees if not t.class_requirement]
    for tree in gated + universal:
        skill = (
            Skill.query.filter_by(tree_id=tree.id, tier=1, skill_type="active", is_active=True)
            .order_by(Skill.id)
            .first()
        )
        if not skill:
            continue
        existing = CharacterSkill.query.filter_by(character_id=character.id, skill_id=skill.id).first()
        if existing:
            return None
        db.session.add(CharacterSkill(character_id=character.id, skill_id=skill.id, skill_rank=1))
        db.session.commit()
        return skill
    return None
```

(Confirm `CharacterSkill`'s actual column names — `skill_rank` per `unlock_skill` — and whether `db` is already imported in progression.py.)

- [ ] **Step 3: Wire the three creation sites** — immediately after each new `Character` gets its id (post-`flush`/`commit`), call `progression.grant_starting_skill(ch)` inside a `try/except` that logs via the file's existing logger pattern and never blocks creation. Grep first: `grep -n "Character(" app/routes/dashboard.py app/routes/dashboard_helpers.py` — cover every real creation site you find, not just the three line numbers above (they may have drifted).
- [ ] **Step 4: GREEN + full suite; also assert (in one of the endpoint-level creation tests, e.g. autofill) that a created character now has 1 unlocked skill.**
- [ ] **Step 5: Commit** — `feat(progression): new characters start with their class's tier-1 active skill`

---

### Task 4: Full-clear detection + extraction bonus + achievement

**Files:**
- Modify: `app/services/extraction_service.py` (add `is_full_clear`; wire bonus into `extract_party`)
- Modify: `app/seed_dungeon_achievements.py` (one new achievement row)
- Test: `tests/test_full_clear_bonus.py` (create)

**Interfaces:**
- Consumes: `DungeonInstance.bosses_defeated` / `bosses_total`; `DungeonEntity` rows (`type="monster"`, `instance_id`); `progression.progression_config()`; `achievement_service.check_achievements(character_id, event_type, event_data)`.
- Produces: `is_full_clear(instance) -> bool`; `extract_party` result dict gains `"full_clear": bool` (Task 5's UI reads exactly this key); config keys `full_clear_copper_mult` (default `1.25`) and `full_clear_xp_bonus` (default `0.5`, i.e. +50% of `extraction_xp`) in `progression_config`; achievement event `dungeon_full_clear`.

- [ ] **Step 1: Failing tests**

```python
def test_is_full_clear_requires_boss_and_no_monsters(...):
    # instance with bosses_total=1, bosses_defeated=1, zero DungeonEntity
    # type="monster" rows -> True
    # same but one monster entity remains -> False
    # bosses_defeated=0 -> False
    # bosses_total=0 (no boss generated) -> False  (never trivially "won")

def test_extract_party_applies_full_clear_bonus(...):
    # build a full-clear instance + one locked character with run copper;
    # extract; assert result["full_clear"] is True, secured copper is
    # int(base * 1.25), and xp granted = extraction_xp * (1 + 0.5) scaled
    # by the normal multiplier. Non-full-clear control case gets base values
    # and full_clear False.
```

Write these concretely following `tests/test_extraction_economy.py`'s existing setup helpers (it already builds instances + locked characters).

- [ ] **Step 2: RED**, then implement:

```python
def is_full_clear(instance: DungeonInstance) -> bool:
    """Boss(es) dead AND no monster entities left on the map.

    ponytail: entities are deleted when combat *starts* (finite pool), so a
    fled encounter still counts toward the clear; upgrade path is a real
    kill counter on the instance if flee-abuse ever matters.
    """
    total = int(getattr(instance, "bosses_total", 0) or 0)
    if total <= 0 or int(instance.bosses_defeated or 0) < total:
        return False
    from app.models.entities import DungeonEntity  # match the real import path

    remaining = DungeonEntity.query.filter_by(instance_id=instance.id, type="monster").count()
    return remaining == 0
```

(Verify the entity model/module name and its FK/`type` column values by reading `app/dungeon/api_helpers/encounters.py`'s `_DE` usage — mirror exactly what collision combat queries.)

In `extract_party`: compute `full_clear = is_full_clear(instance)` once, before the per-character loop. Apply:
- copper: after `secured_copper` is summed, `if full_clear and not early_extraction: secured_copper = int(secured_copper * float(cfg.get("full_clear_copper_mult", 1.25)))` — the multiplier must apply to what lands in the hoard, so apply it where copper is added to the hoard, not only to the reported number (read how `pool_run_haul` moves copper and hook accordingly — most likely by adding the bonus delta to the hoard afterward with a comment).
- xp: extend the existing `extraction_xp` grant: `if full_clear: extraction_xp = int(extraction_xp * (1 + float(cfg.get("full_clear_xp_bonus", 0.5))))` — reusing the same `progression_config()` dict (add both defaults to `DEFAULTS` in `progression.py` next to `extraction_xp`).
- achievement: for each successfully extracted character, `check_achievements(char.id, "dungeon_full_clear", {"count": 1})` inside try/except (match how other services call it).
- result dict: add `"full_clear": full_clear`.

Add to `app/seed_dungeon_achievements.py`'s list:

```python
{
    "slug": "dungeon-full-clear",
    "name": "Leave Nothing Standing",
    "description": "Extract after slaying every monster and the boss in a single run.",
    "category": "combat",
    "icon": "skull",
    "points": 25,
    "hidden": False,
    "requirement_type": "dungeon_full_clear",
    "requirement_value": 1,
    "reward_gold": 0,
},
```

- [ ] **Step 3: GREEN + full suite green**
- [ ] **Step 4: Commit** — `feat(extraction): full-clear bonus (copper mult + xp bonus + achievement)`

---

### Task 5: Surface full clear in the extraction UI

**Files:**
- Modify: `app/static/js/adventure-extraction.js` (the "secured to hoard" confirmation panel)
- Test: none automated (no JS test infra) — include a `node --check app/static/js/adventure-extraction.js` syntax pass and note that visual confirmation belongs to the next live playtest.

**Interfaces:**
- Consumes: `result.full_clear` from the extraction response (Task 4).

- [ ] **Step 1:** Find where the confirmation panel renders secured copper/items (the panel added by the "Run/extraction surface" spec). When `result.full_clear` is true, prepend one highlighted line: `FULL CLEAR — bonus loot and XP secured!` styled with the panel's existing accent classes (reuse an existing class like the panel's header/success styling; add no new CSS unless nothing fits, in which case one rule in the page's existing stylesheet using `var(--ui-*)` tokens).
- [ ] **Step 2:** `node --check` the file; run the full suite (unchanged, but confirms nothing else broke).
- [ ] **Step 3: Commit** — `feat(ui): show full-clear bonus line on extraction confirmation`

---

### Task 6: Deploy wiring + docs

**Files:**
- Modify: `docs/superpowers/TODO.md` (mark the sorcerer-no-spells / class-skills gap and win-condition items done; note the deploy step)
- Test: run the two seed commands against the test DB once to prove they work end-to-end.

- [ ] **Step 1:** Verify `python run.py seed-skills` and the dungeon-achievements seeding path (find how `seed_dungeon_achievements` is invoked — `run.py` subcommand or admin reseed; if the new achievement isn't reachable by an existing command, wire it into whichever command already runs that seeder) both apply the new content idempotently. Evidence: run each twice against the test DB, second run changes nothing.
- [ ] **Step 2:** TODO.md: add a dated entry — class archetype trees (6 trees / 27 skills), starting actives per class, server-side class gating, full-clear bonus + achievement; deploy note: run `python run.py seed-skills` and the achievements seeder on the dev/prod DB.
- [ ] **Step 3: Commit** — `docs(todo): class skill trees + full-clear bonus shipped; deploy seed steps`
