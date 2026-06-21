# Character Cards Phase B: New Effect Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `regen_buff` status-effect type plus two sources for it — a new `potion-regen` item (usable in and out of combat) and a "well-rested" buff applied by camping — on top of the existing Phase A persisted status-effect foundation.

**Architecture:** Mirror the existing `poison` effect's dual-path pattern (in-memory `EFFECT_START` handler for combat, persisted `CharacterStatusEffect` row + `apply_tick_decay` branch for out-of-combat) with a new `regen_buff` effect type that heals instead of damages, and is a temporary multiplier on the existing passive regen rate rather than a flat amount.

**Tech Stack:** Flask, SQLAlchemy, existing `app/services/status_effects.py` / `app/services/combat_service.py` modules, pytest.

## Global Constraints

- Potion: `hp_mult=3.0, mp_mult=3.0`, `remaining=5` (ticks out of combat / turns in combat).
- Camp: `hp_mult=2.0, mp_mult=2.0`, `remaining=10` ticks.
- Re-applying `regen_buff` to a character/participant that already has one **replaces** it (delete-then-insert / remove-then-append) — never stacks.
- No new `GameConfig` key for these multipliers/durations — fixed constants in code.
- No schema migration — reuses the existing `CharacterStatusEffect` table from Phase A.
- No combat.js / UI button changes — out of scope for this phase (Phase C/D own card UI; the existing combat "Potion" button staying hardcoded to `potion-healing` is a pre-existing, separately-tracked follow-up).

---

### Task 1: `regen_buff` combat handler in `status_effects.py`

**Files:**
- Modify: `app/services/status_effects.py`
- Test: `tests/test_status_effects_decay.py` (add cases to the existing file — it already covers both combat-shaped and persisted-shaped behavior for `poison`)

**Interfaces:**
- Produces: `EFFECT_START["regen_buff"]` registered handler `_regen_buff_start(target: Participant, effect: Effect) -> List[str]`.
- Produces: `replace_effect(effects: List[Effect], name: str, remaining: int, **data) -> List[Effect]` — pure helper: returns a new list with any existing entry named `name` removed and a fresh `{"name": name, "remaining": remaining, "data": data}` appended. Used by Task 1 (combat) and reused conceptually (not directly importable across the in-memory/persisted boundary) by Task 3's persisted equivalent.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_status_effects_decay.py` (new imports already mostly present — add `from app.services.status_effects import apply_start_of_turn, replace_effect` near the existing `apply_tick_decay` import):

```python
def test_regen_buff_start_heals_and_caps_at_max_hp_and_mana():
    participant = {
        "name": "Hero",
        "hp": 10,
        "max_hp": 100,
        "mana": 5,
        "mana_max": 50,
        "effects": [{"name": "regen_buff", "remaining": 2, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}],
    }
    logs = apply_start_of_turn(participant)
    assert participant["hp"] > 10
    assert participant["hp"] <= 100
    assert participant["mana"] > 5
    assert participant["mana"] <= 50
    assert participant["effects"][0]["remaining"] == 1
    assert logs  # produced a log line


def test_regen_buff_start_caps_at_max_hp_when_near_full():
    participant = {
        "name": "Hero",
        "hp": 99,
        "max_hp": 100,
        "mana": 49,
        "mana_max": 50,
        "effects": [{"name": "regen_buff", "remaining": 1, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}],
    }
    apply_start_of_turn(participant)
    assert participant["hp"] == 100
    assert participant["mana"] == 50


def test_regen_buff_pruned_after_expiry():
    participant = {
        "name": "Hero",
        "hp": 10,
        "max_hp": 100,
        "mana": 5,
        "mana_max": 50,
        "effects": [{"name": "regen_buff", "remaining": 1, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}],
    }
    apply_start_of_turn(participant)
    assert participant["effects"] == []


def test_replace_effect_removes_existing_entry_of_same_name():
    effects = [
        {"name": "regen_buff", "remaining": 2, "data": {"hp_mult": 2.0, "mp_mult": 2.0}},
        {"name": "poison", "remaining": 5, "data": {"damage": 3}},
    ]
    result = replace_effect(effects, "regen_buff", 5, hp_mult=3.0, mp_mult=3.0)
    regen_entries = [e for e in result if e["name"] == "regen_buff"]
    assert len(regen_entries) == 1
    assert regen_entries[0]["remaining"] == 5
    assert regen_entries[0]["data"] == {"hp_mult": 3.0, "mp_mult": 3.0}
    # untouched poison entry still present
    assert any(e["name"] == "poison" for e in result)


def test_replace_effect_on_empty_list_just_appends():
    result = replace_effect([], "regen_buff", 5, hp_mult=3.0, mp_mult=3.0)
    assert result == [{"name": "regen_buff", "remaining": 5, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_status_effects_decay.py -k "regen_buff or replace_effect" -v`
Expected: FAIL — `ImportError: cannot import name 'replace_effect'` (and `regen_buff` produces no heal since no handler is registered).

- [ ] **Step 3: Implement `_regen_buff_start` and `replace_effect` in `status_effects.py`**

In `app/services/status_effects.py`, add after the existing `_poison_start` function (around line 38, right before the `# stun has no start damage` comment):

```python
def _regen_buff_start(target: Participant, effect: Effect) -> List[str]:
    """Heal a flat 2% of max HP/mana per turn, scaled by this effect's
    hp_mult/mp_mult -- e.g. hp_mult=3.0 heals 6% of max HP this turn.
    Capped at max, never overheals.
    """
    data = effect.get("data", {}) or {}
    try:
        hp_mult = float(data.get("hp_mult", 1.0))
    except Exception:
        hp_mult = 1.0
    try:
        mp_mult = float(data.get("mp_mult", 1.0))
    except Exception:
        mp_mult = 1.0
    max_hp = int(target.get("max_hp", 0))
    max_mana = int(target.get("mana_max", 0))
    hp_heal = math.ceil(max_hp * 0.02 * hp_mult)
    mp_heal = math.ceil(max_mana * 0.02 * mp_mult)
    target["hp"] = min(max_hp, int(target.get("hp", 0)) + hp_heal) if max_hp else target.get("hp", 0)
    target["mana"] = min(max_mana, int(target.get("mana", 0)) + mp_heal) if max_mana else target.get("mana", 0)
    return [f"{target.get('name', '?')} is well-rested, regenerating ({target.get('hp')} hp, {target.get('mana')} mp)"]
```

Register it in `EFFECT_START` (modify the existing dict):

```python
EFFECT_START = {
    "poison": _poison_start,
    "regen_buff": _regen_buff_start,
}
```

Add `replace_effect` after `add_effect` (which already exists in the file):

```python
def replace_effect(effects: List[Effect], name: str, remaining: int, **data: Any) -> List[Effect]:
    """Return a new effects list with any existing entry named ``name``
    removed and a fresh one appended -- replace, not stack."""
    kept = [e for e in effects if e.get("name") != name]
    kept.append({"name": name, "remaining": int(remaining), "data": data})
    return kept
```

Add `"replace_effect"` to the `__all__` list at the bottom of the file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_status_effects_decay.py -k "regen_buff or replace_effect" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/status_effects.py tests/test_status_effects_decay.py
git commit -m "feat(status-effects): add regen_buff combat handler + replace_effect helper"
```

---

### Task 2: Persisted `regen_buff` branch in `apply_tick_decay`

**Files:**
- Modify: `app/services/status_effects.py`
- Test: `tests/test_status_effects_decay.py`

**Interfaces:**
- Consumes: `CharacterStatusEffect` model (`app.models.CharacterStatusEffect`), already imported inside `apply_tick_decay`.
- Produces: `apply_tick_decay` now also handles `effect.name == "regen_buff"`, multiplying that tick's `hp_pct_per_tick`/`mp_pct_per_tick` for the character carrying it. No new public function.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_status_effects_decay.py`:

```python
def test_apply_tick_decay_regen_buff_multiplies_regen_rate():
    from app.models import GameConfig

    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 1.0, "mp_pct_per_tick": 1.0}))
    db.session.commit()

    char = _make_character("regenbuffdecay")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, mana_max = compute_hp_mana_max(char)
    db.session.add(
        CharacterStatusEffect(character_id=char.id, name="regen_buff", remaining=5, data='{"hp_mult": 3.0, "mp_mult": 3.0}')
    )
    db.session.commit()

    apply_tick_decay(1, character_ids=[char.id])

    db.session.refresh(char)
    stats = json.loads(char.stats)
    base_heal = math.ceil(hp_max * 1.0 / 100)
    buffed_heal = math.ceil(hp_max * 3.0 / 100)
    assert stats["hp"] - 1 == buffed_heal
    assert stats["hp"] - 1 > base_heal

    remaining_effect = CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").first()
    assert remaining_effect.remaining == 4


def test_apply_tick_decay_regen_buff_expires_and_is_pruned():
    char = _make_character("regenbuffexpire")
    db.session.add(
        CharacterStatusEffect(character_id=char.id, name="regen_buff", remaining=1, data='{"hp_mult": 3.0, "mp_mult": 3.0}')
    )
    db.session.commit()

    apply_tick_decay(1, character_ids=[char.id])

    assert CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").count() == 0


def test_apply_tick_decay_regen_buff_malformed_data_falls_back_to_base_rate():
    from app.models import GameConfig

    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 1.0, "mp_pct_per_tick": 1.0}))
    db.session.commit()

    char = _make_character("regenbuffmalformed")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, _ = compute_hp_mana_max(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="regen_buff", remaining=5, data="not json"))
    db.session.commit()

    apply_tick_decay(1, character_ids=[char.id])

    db.session.refresh(char)
    stats = json.loads(char.stats)
    base_heal = math.ceil(hp_max * 1.0 / 100)
    assert stats["hp"] - 1 == base_heal


def test_apply_tick_decay_poison_and_regen_buff_combine_independently():
    from app.models import GameConfig

    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 0.0, "mp_pct_per_tick": 0.0}))
    db.session.commit()

    char = _make_character("poisonplusregenbuff")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 50, "current_mana": 20})
    db.session.add(char)
    db.session.commit()
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 10}'))
    db.session.add(
        CharacterStatusEffect(character_id=char.id, name="regen_buff", remaining=5, data='{"hp_mult": 3.0, "mp_mult": 3.0}')
    )
    db.session.commit()

    apply_tick_decay(1, character_ids=[char.id])

    db.session.refresh(char)
    stats = json.loads(char.stats)
    # base rate is 0, so regen_buff's multiplier of 0 contributes nothing --
    # net effect is just poison damage.
    assert stats["hp"] == 40
```

Add `import math` to the test file's imports if not already present (check top of `tests/test_status_effects_decay.py` first — it currently imports `json` only).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_status_effects_decay.py -k "regen_buff_multiplies or regen_buff_expires or regen_buff_malformed or combine_independently" -v`
Expected: FAIL — regen heal amount won't reflect the multiplier (no `regen_buff` branch exists yet, so the buff row is read by nothing and the base 0.5%/default rate applies instead).

- [ ] **Step 3: Implement the `regen_buff` branch in `apply_tick_decay`**

In `app/services/status_effects.py`, inside `apply_tick_decay`'s per-character loop, the current code reads:

```python
            effects = CharacterStatusEffect.query.filter_by(character_id=char.id).all()
            if effects:
                effects_touched = True
            for effect in effects:
                if effect.name == "poison":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                    except Exception:
                        payload = {}
                    damage = int(payload.get("damage", 0)) * delta
                    if damage > 0:
                        hp = max(1, hp - damage)
                        stats_changed = True
                effect.remaining -= delta
                if effect.remaining <= 0:
                    db.session.delete(effect)
                else:
                    db.session.add(effect)

            if hp < hp_max:
                hp = min(hp_max, hp + math.ceil(hp_max * rates["hp_pct_per_tick"] / 100 * delta))
                stats_changed = True
            if mana < mana_max:
                mana = min(mana_max, mana + math.ceil(mana_max * rates["mp_pct_per_tick"] / 100 * delta))
                stats_changed = True
```

Replace with (adds a `hp_mult`/`mp_mult` accumulator read from any active `regen_buff` row, defaulting to `1.0`, applied when computing the regen amounts below):

```python
            effects = CharacterStatusEffect.query.filter_by(character_id=char.id).all()
            if effects:
                effects_touched = True
            hp_mult = 1.0
            mp_mult = 1.0
            for effect in effects:
                if effect.name == "poison":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                    except Exception:
                        payload = {}
                    damage = int(payload.get("damage", 0)) * delta
                    if damage > 0:
                        hp = max(1, hp - damage)
                        stats_changed = True
                elif effect.name == "regen_buff":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                        if not isinstance(payload, dict):
                            payload = {}
                    except Exception:
                        payload = {}
                    try:
                        hp_mult = float(payload.get("hp_mult", 1.0))
                    except Exception:
                        hp_mult = 1.0
                    try:
                        mp_mult = float(payload.get("mp_mult", 1.0))
                    except Exception:
                        mp_mult = 1.0
                effect.remaining -= delta
                if effect.remaining <= 0:
                    db.session.delete(effect)
                else:
                    db.session.add(effect)

            if hp < hp_max:
                hp = min(hp_max, hp + math.ceil(hp_max * rates["hp_pct_per_tick"] * hp_mult / 100 * delta))
                stats_changed = True
            if mana < mana_max:
                mana = min(mana_max, mana + math.ceil(mana_max * rates["mp_pct_per_tick"] * mp_mult / 100 * delta))
                stats_changed = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_status_effects_decay.py -v`
Expected: PASS (all tests in the file, including the pre-existing poison/regen ones — confirms no regression)

- [ ] **Step 5: Commit**

```bash
git add app/services/status_effects.py tests/test_status_effects_decay.py
git commit -m "feat(status-effects): apply_tick_decay multiplies regen rate when regen_buff is active"
```

---

### Task 3: Round-trip `regen_buff` through combat start/end alongside poison

**Files:**
- Modify: `app/services/combat_service.py`
- Test: `tests/test_status_effects_decay.py` or a new `tests/test_regen_buff_combat_roundtrip.py` (create the latter — keeps combat-session-shaped tests separate from the no-session unit tests already in `test_status_effects_decay.py`)

**Interfaces:**
- Consumes: `replace_effect` from Task 1, `CharacterStatusEffect` model.
- Modifies: `_base_player_snapshot`'s effects-loading query (currently filters `name="poison"` only) and `_persist_party_resources`'s write-back block (currently writes back only `name="poison"`).
- Produces: no new public function; both code paths now also handle `regen_buff` the same way they already handle `poison`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_regen_buff_combat_roundtrip.py`:

```python
"""regen_buff must round-trip through combat the same way poison already
does: loaded into the in-memory participant snapshot at session start, and
written back to CharacterStatusEffect for survivors at combat end."""

import json
import random

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster(hp=10):
    return {
        "slug": "regen-test-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": hp,
        "damage": 1,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 0,
        "boss": False,
    }


def test_regen_buff_loaded_into_combat_snapshot_at_session_start(test_app):
    with test_app.app_context():
        user = User(username=f"regenbuff-start-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12, "hp": 50}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()
        db.session.add(
            CharacterStatusEffect(character_id=char.id, name="regen_buff", remaining=3, data='{"hp_mult": 3.0, "mp_mult": 3.0}')
        )
        db.session.commit()

        session = combat_service.start_session(user.id, _simple_monster())
        party = json.loads(session.party_snapshot_json)
        member = party["members"][0]
        assert any(e["name"] == "regen_buff" and e["remaining"] == 3 for e in member.get("effects", []))


def test_regen_buff_written_back_to_db_for_survivors_at_combat_end(test_app, monkeypatch):
    with test_app.app_context():
        user = User(username=f"regenbuff-end-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12, "hp": 50}),
            gear="{}",
            items="[]",
        )
        db.session.add(char)
        db.session.commit()

        init_seq = iter([20, 1])  # player acts first
        monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
        session = combat_service.start_session(user.id, _simple_monster(hp=10))

        party = json.loads(session.party_snapshot_json)
        member = party["members"][0]
        member["effects"] = [{"name": "regen_buff", "remaining": 2, "data": {"hp_mult": 3.0, "mp_mult": 3.0}}]
        session.party_snapshot_json = json.dumps(party)
        db.session.commit()

        initiative = json.loads(session.initiative_json)
        actor_id = initiative[session.active_index]["id"]
        result = combat_service.player_attack(session.id, user.id, session.version, actor_id=actor_id)
        assert result.get("ok") is True

        row = CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").first()
        assert row is not None
        assert row.remaining == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regen_buff_combat_roundtrip.py -v`
Expected: FAIL — first test fails because `_base_player_snapshot` only queries `name="poison"`, so `effects` is empty; second fails because `_persist_party_resources` only writes back `name="poison"` rows, so no `regen_buff` row exists after combat ends.

- [ ] **Step 3: Generalize the poison-only filter to include `regen_buff`**

In `app/services/combat_service.py`, find the effects-loading block inside the player-snapshot builder (the function containing `char_class` inference, around line 168):

```python
    from app.models import CharacterStatusEffect

    try:
        effects = [
            {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
            for row in CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").all()
        ]
    except Exception:
        effects = []
```

Replace `filter_by(character_id=char.id, name="poison")` with a multi-name filter:

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

Now find `_persist_party_resources`'s write-back block (around line 890):

```python
            # Write back remaining poison -- delete-then-recreate is simplest
            # and avoids diffing old vs new rows. Dead characters (hp<=0)
            # don't get effects written back.
            try:
                CharacterStatusEffect.query.filter_by(character_id=cid, name="poison").delete()
                if int(m.get("hp", 0)) > 0:
                    for eff in m.get("effects", []) or []:
                        if eff.get("name") == "poison" and int(eff.get("remaining", 0)) > 0:
                            db.session.add(
                                CharacterStatusEffect(
                                    character_id=cid,
                                    name="poison",
                                    remaining=int(eff["remaining"]),
                                    data=_json.dumps(eff.get("data", {})),
                                )
                            )
            except Exception:
                pass
```

Replace with a name-agnostic version covering both persisted effect types:

```python
            # Write back remaining poison/regen_buff -- delete-then-recreate is
            # simplest and avoids diffing old vs new rows. Dead characters
            # (hp<=0) don't get effects written back.
            try:
                PERSISTED_EFFECT_NAMES = ("poison", "regen_buff")
                CharacterStatusEffect.query.filter(
                    CharacterStatusEffect.character_id == cid,
                    CharacterStatusEffect.name.in_(PERSISTED_EFFECT_NAMES),
                ).delete(synchronize_session=False)
                if int(m.get("hp", 0)) > 0:
                    for eff in m.get("effects", []) or []:
                        if eff.get("name") in PERSISTED_EFFECT_NAMES and int(eff.get("remaining", 0)) > 0:
                            db.session.add(
                                CharacterStatusEffect(
                                    character_id=cid,
                                    name=eff["name"],
                                    remaining=int(eff["remaining"]),
                                    data=_json.dumps(eff.get("data", {})),
                                )
                            )
            except Exception:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_regen_buff_combat_roundtrip.py tests/test_status_effects_decay.py -v`
Expected: PASS (both new tests; no regressions in the existing poison round-trip tests)

Also run the pre-existing poison round-trip coverage to confirm no regression:
Run: `.venv/bin/python -m pytest tests/ -k "poison" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/combat_service.py tests/test_regen_buff_combat_roundtrip.py
git commit -m "feat(combat): round-trip regen_buff through combat start/end alongside poison"
```

---

### Task 4: New item `potion-regen` + combat-side `player_use_item` branch

**Files:**
- Modify: `app/server.py` (item seed list inside `seed_items()`)
- Modify: `app/services/combat_service.py`
- Test: `tests/test_potions_per_character.py` (add new test functions; reuses its existing `_simple_monster`/`_two_character_session`-style helpers) or a new file — use a new file to avoid coupling to that file's potion-healing-specific helper names.
- Test: `tests/test_regen_potion_combat.py` (new)

**Interfaces:**
- Consumes: `replace_effect` (Task 1) for the in-memory regen_buff application.
- Produces: `Item(slug="potion-regen", ...)` seed row. `player_use_item` now handles `slug == "potion-regen"` the same structural way it handles `"potion-healing"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_regen_potion_combat.py`:

```python
"""Using potion-regen in combat applies a regen_buff effect instead of an
instant heal, and deducts from the acting character's own inventory only
(mirrors tests/test_potions_per_character.py's potion-healing coverage)."""

import json
import random

from app import db
from app.models.models import Character, User
from app.services import combat_service


def _simple_monster():
    return {
        "slug": "regen-potion-test-mob",
        "name": "Training Dummy",
        "level": 1,
        "hp": 500,
        "damage": 10,
        "armor": 0,
        "speed": 8,
        "rarity": "common",
        "family": "test",
        "traits": [],
        "resistances": {},
        "damage_types": [],
        "loot_table": "",
        "special_drop_slug": None,
        "xp": 0,
        "boss": False,
    }


def test_using_potion_regen_in_combat_applies_regen_buff_and_deducts_inventory(test_app, monkeypatch):
    with test_app.app_context():
        user = User(username=f"regenpotion-{random.randint(1, 10**9)}", email=None)
        user.set_password("pw")
        db.session.add(user)
        db.session.commit()
        stats = json.dumps({"str": 12, "dex": 10, "int": 10, "con": 12})
        char = Character(
            user_id=user.id,
            name="Hero",
            stats=stats,
            gear="{}",
            items=json.dumps([{"slug": "potion-regen", "qty": 2}]),
        )
        db.session.add(char)
        db.session.commit()

        init_seq = iter([20, 1])  # player acts first
        monkeypatch.setattr(random, "randint", lambda a, b: next(init_seq, 10))
        session = combat_service.start_session(user.id, _simple_monster())
        initiative = json.loads(session.initiative_json)
        actor_id = initiative[session.active_index]["id"]

        result = combat_service.player_use_item(session.id, user.id, session.version, "potion-regen", actor_id=actor_id)
        assert result.get("ok") is True, result

        refreshed = combat_service._load_session(session.id)
        party = json.loads(refreshed.party_snapshot_json)
        member = next(m for m in party["members"] if m.get("char_id") == actor_id)
        assert any(e["name"] == "regen_buff" for e in member.get("effects", []))

        db.session.refresh(char)
        inv = json.loads(char.items)
        assert inv == [{"slug": "potion-regen", "qty": 1}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regen_potion_combat.py -v`
Expected: FAIL with `result.get("ok") is True` failing (`player_use_item` returns `{"error": "cannot_use"}` since no `potion-regen` branch exists yet).

- [ ] **Step 3: Add the item seed row and the combat branch**

In `app/server.py`'s `seed_items()`, add a new dict immediately after the existing `potion-mana` dict (around line 217):

```python
        dict(
            slug="potion-regen",
            name="Potion of Regeneration",
            type="potion",
            description="Grants a temporary boost to natural HP/mana regeneration.",
            value_copper=200,
            level=0,
            rarity="uncommon",
        ),
```

In `app/services/combat_service.py`, find the `player_use_item` body's potion branch (around line 1457):

```python
    used = False
    for m in party.get("members", []):
        if m.get("char_id") == actor_id:
            if slug == "potion-healing":
                heal = 25
                m["hp"] = min(m.get("max_hp", 100), m.get("hp", 0) + heal)
                used = True
            break
    if not used:
        return {"error": "cannot_use"}
```

Replace with:

```python
    used = False
    for m in party.get("members", []):
        if m.get("char_id") == actor_id:
            if slug == "potion-healing":
                heal = 25
                m["hp"] = min(m.get("max_hp", 100), m.get("hp", 0) + heal)
                used = True
            elif slug == "potion-regen":
                from app.services.status_effects import replace_effect

                m["effects"] = replace_effect(m.get("effects", []) or [], "regen_buff", 5, hp_mult=3.0, mp_mult=3.0)
                used = True
            break
    if not used:
        return {"error": "cannot_use"}
```

The inventory-deduction block below this (around line 1467) already operates generically on `slug` — it removes whatever `slug` was passed regardless of which potion branch ran, so it requires no change for `potion-regen` to be deducted correctly.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_regen_potion_combat.py -v`
Expected: PASS

Also re-run the existing potion-healing combat tests to confirm no regression:
Run: `.venv/bin/python -m pytest tests/test_potions_per_character.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/server.py app/services/combat_service.py tests/test_regen_potion_combat.py
git commit -m "feat(items): add potion-regen item + combat use_item branch applying regen_buff"
```

---

### Task 5: Out-of-combat `potion-regen` consume branch

**Files:**
- Modify: `app/routes/inventory_api.py`
- Test: `tests/test_regen_potion_out_of_combat.py` (new)

**Interfaces:**
- Consumes: `CharacterStatusEffect` model, `Character`/`Item` models, `db` from `app`, the existing `_char_owned`/`load_inventory`/`dump_inventory`/`remove_one`/`advance_for` helpers already imported in `inventory_api.py`.
- Produces: `POST /api/characters/<cid>/consume` with `{"slug": "potion-regen"}` now inserts a `CharacterStatusEffect(name="regen_buff", remaining=5, data={"hp_mult": 3.0, "mp_mult": 3.0})` row (replace-not-stack) instead of (or in addition to) the existing flat heal/mana branches.

- [ ] **Step 1: Write the failing test**

Create `tests/test_regen_potion_out_of_combat.py`:

```python
"""Consuming potion-regen outside combat applies a persisted regen_buff
CharacterStatusEffect instead of (or in addition to) the existing flat
heal/mana bump other potions get."""

import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, Item, User


def _ensure_potion_regen_item():
    item = Item.query.filter_by(slug="potion-regen").first()
    if item:
        return item
    item = Item(slug="potion-regen", name="Potion of Regeneration", type="potion", description="", value_copper=200)
    db.session.add(item)
    db.session.commit()
    return item


def test_consume_potion_regen_applies_persisted_regen_buff(test_app, auth_client):
    with test_app.app_context():
        _ensure_potion_regen_item()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-regen", "qty": 1}])
        db.session.commit()
        char_id = char.id

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-regen"})
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        effect = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").first()
        assert effect is not None
        assert effect.remaining == 5
        data = json.loads(effect.data)
        assert data == {"hp_mult": 3.0, "mp_mult": 3.0}

        char = db.session.get(Character, char_id)
        inv = json.loads(char.items)
        assert inv == []  # single potion consumed and removed


def test_consume_potion_regen_replaces_not_stacks(test_app, auth_client):
    with test_app.app_context():
        _ensure_potion_regen_item()
        user = User.query.filter_by(username="tester").first()
        char = Character.query.filter_by(user_id=user.id).first()
        char.items = json.dumps([{"slug": "potion-regen", "qty": 2}])
        db.session.commit()
        char_id = char.id
        db.session.add(CharacterStatusEffect(character_id=char_id, name="regen_buff", remaining=1, data='{"hp_mult": 1.5, "mp_mult": 1.5}'))
        db.session.commit()

    resp = auth_client.post(f"/api/characters/{char_id}/consume", json={"slug": "potion-regen"})
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        rows = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").all()
        assert len(rows) == 1
        assert rows[0].remaining == 5
```

Check `auth_client`'s fixture for whether `.username` is exposed (grep `tests/conftest.py` for the fixture before assuming — if it doesn't expose `.username`, use `current_user`-free lookup via the fixture's own returned user object instead; adjust the test to whatever `auth_client` actually returns. Read `tests/conftest.py`'s `auth_client` fixture definition first and match its actual return shape exactly).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_regen_potion_out_of_combat.py -v`
Expected: FAIL — `consume_item` returns `{"error": "not consumable"}` is avoided (type is "potion" so it passes that check), but no `regen_buff` row gets created since there's no `regen` branch yet; assertion on `effect is not None` fails.

- [ ] **Step 3: Add the `potion-regen` branch to `consume_item`**

In `app/routes/inventory_api.py`, add the import at the top (alongside the existing `from app.models.models import Character, Item` line):

```python
from app.models import CharacterStatusEffect
```

Find the consume logic (around line 517):

```python
    base_stats = _safe_json_load(ch.stats, {})
    # Simple effects
    heal = 0
    mana = 0
    sl = (item.slug or "").lower()
    if "healing" in sl:
        heal = 5
    elif "mana" in sl:
        mana = 5
    # Apply
    if heal:
        base_stats["hp"] = int(base_stats.get("hp", 0)) + heal
    if mana:
        base_stats["mana"] = int(base_stats.get("mana", 0)) + mana
    # Remove potion from bag
    removed = remove_one(inv, slug)
    if removed:
        ch.items = dump_inventory(inv)
    ch.stats = _safe_json_dump(base_stats)
    db.session.commit()
    try:
        advance_for("consume", character_ids=[ch.id])
    except Exception:
        pass
    return jsonify({"ok": True, "consumed": slug, "effects": {"hp": heal, "mana": mana}})
```

Replace with (adds a `regen` branch before the generic substring checks, since `"regen"` would otherwise fall through both existing `if`/`elif` with no effect):

```python
    base_stats = _safe_json_load(ch.stats, {})
    # Simple effects
    heal = 0
    mana = 0
    applied_regen_buff = False
    sl = (item.slug or "").lower()
    if "regen" in sl:
        CharacterStatusEffect.query.filter_by(character_id=ch.id, name="regen_buff").delete()
        db.session.add(
            CharacterStatusEffect(
                character_id=ch.id,
                name="regen_buff",
                remaining=5,
                data=json.dumps({"hp_mult": 3.0, "mp_mult": 3.0}),
            )
        )
        applied_regen_buff = True
    elif "healing" in sl:
        heal = 5
    elif "mana" in sl:
        mana = 5
    # Apply
    if heal:
        base_stats["hp"] = int(base_stats.get("hp", 0)) + heal
    if mana:
        base_stats["mana"] = int(base_stats.get("mana", 0)) + mana
    # Remove potion from bag
    removed = remove_one(inv, slug)
    if removed:
        ch.items = dump_inventory(inv)
    ch.stats = _safe_json_dump(base_stats)
    db.session.commit()
    try:
        advance_for("consume", character_ids=[ch.id])
    except Exception:
        pass
    return jsonify(
        {
            "ok": True,
            "consumed": slug,
            "effects": {"hp": heal, "mana": mana, "regen_buff": applied_regen_buff},
        }
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_regen_potion_out_of_combat.py -v`
Expected: PASS

Also re-run existing inventory consume tests for regressions:
Run: `.venv/bin/python -m pytest tests/ -k "consume" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/inventory_api.py tests/test_regen_potion_out_of_combat.py
git commit -m "feat(inventory): consuming potion-regen applies a persisted regen_buff effect"
```

---

### Task 6: Camp applies a "well-rested" regen buff

**Files:**
- Modify: `app/routes/dungeon_api.py`
- Test: `tests/test_camp_regen_buff.py` (new)

**Interfaces:**
- Consumes: `CharacterStatusEffect` model.
- Produces: `POST /api/dungeon/camp` now additionally applies `CharacterStatusEffect(name="regen_buff", remaining=10, data={"hp_mult": 2.0, "mp_mult": 2.0})` to every party character (replace-not-stack), on top of its existing unchanged instant restore.

- [ ] **Step 1: Write the failing test**

Create `tests/test_camp_regen_buff.py`:

```python
"""Camping applies a 'well-rested' regen_buff effect in addition to its
existing instant HP/mana restore -- the restore itself must stay unchanged."""

import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character


def test_camp_applies_regen_buff_alongside_existing_restore(test_app, auth_client):
    with test_app.app_context():
        char = Character.query.first()
        char.stats = json.dumps({"hp": 10, "max_hp": 100, "mana": 5, "max_mana": 50})
        db.session.commit()
        char_id = char.id

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        char = db.session.get(Character, char_id)
        stats = json.loads(char.stats)
        # existing instant-restore behavior unchanged: 30% of 100 = 30 hp, 50% of 50 = 25 mana
        assert stats["hp"] == 40
        assert stats["mana"] == 30

        effect = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").first()
        assert effect is not None
        assert effect.remaining == 10
        data = json.loads(effect.data)
        assert data == {"hp_mult": 2.0, "mp_mult": 2.0}


def test_camp_regen_buff_replaces_not_stacks(test_app, auth_client):
    with test_app.app_context():
        char = Character.query.first()
        char.stats = json.dumps({"hp": 10, "max_hp": 100, "mana": 5, "max_mana": 50})
        db.session.commit()
        char_id = char.id
        db.session.add(CharacterStatusEffect(character_id=char_id, name="regen_buff", remaining=1, data='{"hp_mult": 3.0, "mp_mult": 3.0}'))
        db.session.commit()

    resp = auth_client.post("/api/dungeon/camp")
    assert resp.status_code == 200, resp.get_json()

    with test_app.app_context():
        rows = CharacterStatusEffect.query.filter_by(character_id=char_id, name="regen_buff").all()
        assert len(rows) == 1
        assert rows[0].remaining == 10
```

`auth_client` (`tests/conftest.py`) already provisions exactly one `Character` (named "Hero", owned by user "tester") and sets `session["dungeon_instance_id"]`, so `Character.query.first()` and the bare `auth_client.post("/api/dungeon/camp")` call above are valid as written — no fixture changes needed.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_camp_regen_buff.py -v`
Expected: FAIL — instant-restore assertions pass (unchanged behavior), but `effect is not None` fails since `dungeon_camp()` doesn't apply any `regen_buff` yet.

- [ ] **Step 3: Apply the buff in `dungeon_camp()`**

In `app/routes/dungeon_api.py`, the camp handler's restore loop currently ends with:

```python
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Advance time
```

Add the import `from app.models import CharacterStatusEffect` near the top of the file (alongside the existing `from app.models import DungeonEntity` line), then insert a new block between the existing commit and the "Advance time" comment:

```python
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Apply a "well-rested" regen buff on top of the instant restore above --
    # replace-not-stack, same shape the regen potion uses, just longer/weaker.
    try:
        for char in party_chars:
            CharacterStatusEffect.query.filter_by(character_id=char.id, name="regen_buff").delete()
            db.session.add(
                CharacterStatusEffect(
                    character_id=char.id,
                    name="regen_buff",
                    remaining=10,
                    data=json.dumps({"hp_mult": 2.0, "mp_mult": 2.0}),
                )
            )
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Advance time
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_camp_regen_buff.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/dungeon_api.py tests/test_camp_regen_buff.py
git commit -m "feat(dungeon): camp applies a well-rested regen_buff alongside its instant restore"
```

---

### Task 7: Full suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

```bash
export DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
export TEST_DATABASE_URL=$DATABASE_URL
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```

Expected: all tests pass (matching the pre-existing baseline noted in `docs/superpowers/TODO.md` — currently 421 passed, 2 skipped, 3 deselected, 1 xpassed; this plan adds roughly 16 new tests across the 6 task files and should not change any pre-existing test's outcome).

- [ ] **Step 2: If anything fails, fix forward**

Diagnose via `systematic-debugging` if a failure isn't immediately obvious from the traceback — do not skip or weaken assertions to force a pass.

- [ ] **Step 3: Update the handoff TODO**

Add a entry to `docs/superpowers/TODO.md` under Spec 4 (or as a new "Character Cards Phase B" entry near the existing Phase A entry) summarizing what shipped: `regen_buff` effect type, `potion-regen` item (combat + out-of-combat), camp's well-rested buff — and note Phase C/D (dashboard/combat card redesigns) remain as the next steps in this series.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark Character Cards Phase B (new effect sources) done"
```
