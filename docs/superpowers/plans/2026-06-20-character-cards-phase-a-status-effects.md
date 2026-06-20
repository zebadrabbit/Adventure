# Character Cards Phase A: Persistent Status Effects — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make poison a persistent per-character effect that survives past combat (decaying via the overworld GameClock instead of vanishing at combat end), and add slow out-of-combat HP/MP regeneration — the data foundation later phases (dashboard/combat card redesigns) will read from.

**Architecture:** A new `CharacterStatusEffect` table holds active effects per character. Two independent decay paths feed it: `time_service.advance_time()` (overworld ticks: movement/search/camp) and the existing turn-based combat loop (now wired to actually apply to players, not just monsters, plus load/save persisted poison at combat start/end).

**Tech Stack:** Flask, SQLAlchemy (Flask-SQLAlchemy 3.1), Alembic, pytest.

## Global Constraints

- Out-of-combat poison damage floors at 1 HP — it can decay a character down but never kill them while exploring.
- Regen rate defaults: `hp_pct_per_tick=0.5`, `mp_pct_per_tick=1.0` (percent of computed max, per tick), overridable via `GameConfig.get("regen_rates")`, falling back to defaults on missing/invalid config (same pattern as `time_service._load_action_costs`).
- Only `poison` persists across combat boundaries. `stun` stays combat-only, no changes to it.
- `compute_hp_mana_max()` (new helper) is used **only** by the new decay/regen code in this plan. Do not modify `combat_service._derive_stats` or `dashboard_helpers.build_party_payload` — they keep their existing, already-correct, duplicated formulas untouched (confirmed with the user: avoids risking working combat/dashboard code for a tangential dedup).
- A real Alembic migration is required for the new table — this is a genuinely new model, not schema the self-stamping bootstrap already covers.
- Every DB-writing function in this plan wraps in try/except + `db.session.rollback()` on failure, matching the existing pattern throughout `time_service.py` and `combat_service.py` — a decay/regen/persistence failure must never block the action that triggered it.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/models/status_effect.py` (new) | `CharacterStatusEffect` model |
| `app/models/__init__.py` (modify) | Export `CharacterStatusEffect` |
| `migrations/versions/c7d8e9f0a1b2_add_character_status_effect.py` (new) | Creates `character_status_effect` table |
| `app/services/character_stats.py` (new) | `compute_hp_mana_max(character)` — single source of truth for the new code's HP/mana cap math |
| `app/services/status_effects.py` (modify) | Add `apply_tick_decay(delta)` — the actual decay/regen pass |
| `app/services/time_service.py` (modify) | `advance_time()` calls `apply_tick_decay(delta)` after committing the tick |
| `app/services/combat_service.py` (modify) | `_derive_stats()` loads persisted poison into the player snapshot; `_skip_if_unconscious()` applies start-of-turn poison to the active player (new — today only monsters get this); `_persist_party_resources()` writes remaining poison back |
| `tests/test_status_effects_decay.py` (new) | Unit tests for `compute_hp_mana_max` and `apply_tick_decay` |
| `tests/test_time_system.py` (modify) | Integration test: decay fires on tick advance, not during combat |
| `tests/test_combat_poison_persistence.py` (new) | Combat round-trip: load → tick → save |

---

### Task 1: `CharacterStatusEffect` model + migration

**Files:**
- Create: `app/models/status_effect.py`
- Modify: `app/models/__init__.py`
- Create: `migrations/versions/c7d8e9f0a1b2_add_character_status_effect.py`
- Test: `tests/test_status_effects_decay.py`

**Interfaces:**
- Produces: `CharacterStatusEffect(character_id: int, name: str, remaining: int, data: str | None, created_at: datetime)`, importable as `from app.models import CharacterStatusEffect`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_status_effects_decay.py`:

```python
from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character, User


def _make_character(username_suffix):
    user = User(username=f"statuseffect_{username_suffix}")
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    char = Character(
        user_id=user.id,
        name="Hero",
        stats='{"con": 10, "int": 10, "hp": 50, "current_mana": 20}',
        gear="{}",
        items="[]",
    )
    db.session.add(char)
    db.session.commit()
    return char


def test_character_status_effect_round_trip():
    char = _make_character("model")
    effect = CharacterStatusEffect(
        character_id=char.id,
        name="poison",
        remaining=3,
        data='{"damage": 5}',
    )
    db.session.add(effect)
    db.session.commit()

    fetched = CharacterStatusEffect.query.filter_by(character_id=char.id).first()
    assert fetched is not None
    assert fetched.name == "poison"
    assert fetched.remaining == 3
    assert fetched.data == '{"damage": 5}'
    assert fetched.created_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py::test_character_status_effect_round_trip -v`

Expected: FAIL with `ImportError: cannot import name 'CharacterStatusEffect' from 'app.models'`

- [ ] **Step 3: Create the model**

Create `app/models/status_effect.py`:

```python
"""
project: Adventure MUD
module: status_effect.py

Persistent per-character status effects (e.g. poison) that survive past the
end of a single combat encounter, decaying via the overworld GameClock
instead of only combat turns. See app/services/status_effects.py for the
decay/regen logic that reads and writes this table.
"""

from datetime import datetime

from app import db


class CharacterStatusEffect(db.Model):
    """An active status effect attached to a character.

    Attributes:
        character_id: FK to Character.id the effect is attached to.
        name: Effect identifier, e.g. "poison". Only "poison" is supported
            as a persistent effect today; combat-only effects (e.g. "stun")
            never get a row here.
        remaining: Ticks (overworld) or turns (combat) left before the
            effect expires and its row is deleted.
        data: Optional JSON string payload, e.g. '{"damage": 5}'. Mirrors
            the in-memory effect payload shape used by status_effects.py's
            combat-turn handlers, so the same handler functions can read
            either source without translation.
        created_at: Row creation timestamp, for debugging/observability.
    """

    __tablename__ = "character_status_effect"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    remaining = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
```

- [ ] **Step 4: Export it from `app/models/__init__.py`**

In `app/models/__init__.py`, add the import alongside the other re-exports and add to `__all__`:

```python
from .dungeon_instance import DungeonInstance  # noqa: F401 re-export
from .dungeon_tier import DungeonAffix, DungeonTier  # noqa: F401 re-export
from .enemy_archetype import EnemyArchetype  # noqa: F401 re-export
from .entities import DungeonEntity  # noqa: F401
from .loot import DungeonLoot  # noqa: F401 re-export
from .models import GameClock, GameConfig, MonsterCatalog  # noqa: F401 re-export
from .status_effect import CharacterStatusEffect  # noqa: F401 re-export
from .theme import Theme  # noqa: F401 re-export
from .weapon_category import WeaponCategory  # noqa: F401 re-export

__all__ = [
    "DungeonInstance",
    "DungeonLoot",
    "GameClock",
    "GameConfig",
    "MonsterCatalog",
    "DungeonEntity",
    "Theme",
    "WeaponCategory",
    "EnemyArchetype",
    "DungeonTier",
    "DungeonAffix",
    "CharacterStatusEffect",
]
```

- [ ] **Step 5: Create the schema for the test DB directly (test DB doesn't run Alembic)**

The test suite builds its schema via `db.create_all()` at app bootstrap (see `app/__init__.py`), which will pick up the new model automatically once it's imported via `app/models/__init__.py`. No extra step needed here — just re-run the test:

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py::test_character_status_effect_round_trip -v`

Expected: PASS

- [ ] **Step 6: Write the Alembic migration for real deployments**

Create `migrations/versions/c7d8e9f0a1b2_add_character_status_effect.py`:

```python
"""add character_status_effect table

Revision ID: c7d8e9f0a1b2
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_status_effect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=False),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_character_status_effect_character_id"),
        "character_status_effect",
        ["character_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_character_status_effect_character_id"), table_name="character_status_effect")
    op.drop_table("character_status_effect")
```

- [ ] **Step 7: Verify the migration applies cleanly against the dev DB**

Run: `source .venv/bin/activate && export DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure" && alembic upgrade head`

Expected: Output shows it running revision `c7d8e9f0a1b2`, no errors. Then `alembic current` should report `c7d8e9f0a1b2 (head)`.

- [ ] **Step 8: Commit**

```bash
git add app/models/status_effect.py app/models/__init__.py migrations/versions/c7d8e9f0a1b2_add_character_status_effect.py tests/test_status_effects_decay.py
git commit -m "feat(models): add CharacterStatusEffect for persistent per-character effects"
```

---

### Task 2: `compute_hp_mana_max` helper

**Files:**
- Create: `app/services/character_stats.py`
- Test: `tests/test_status_effects_decay.py` (append)

**Interfaces:**
- Consumes: `Character` model (from Task 1's test helper `_make_character`), `app.loot.equip.gear_bonuses(gear: dict) -> dict`, `app.services.skill_effects.passive_bonuses(character_id: int) -> dict`.
- Produces: `compute_hp_mana_max(character: Character) -> tuple[int, int]` (hp_max, mana_max), importable as `from app.services.character_stats import compute_hp_mana_max`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_status_effects_decay.py`:

```python
import json

from app.services.character_stats import compute_hp_mana_max


def test_compute_hp_mana_max_uses_con_int_level_and_gear():
    char = _make_character("hpmax")
    char.stats = json.dumps({"con": 14, "int": 12})
    char.level = 3
    char.gear = "{}"
    db.session.add(char)
    db.session.commit()

    hp_max, mana_max = compute_hp_mana_max(char)

    # base 50 + CON*2 + level*5 = 50 + 28 + 15 = 93
    assert hp_max == 93
    # base 20 + INT*2 = 20 + 24 = 44
    assert mana_max == 44


def test_compute_hp_mana_max_defaults_when_stats_missing():
    char = _make_character("hpmaxdefault")
    char.stats = "{}"
    char.level = 1
    char.gear = "{}"
    db.session.add(char)
    db.session.commit()

    hp_max, mana_max = compute_hp_mana_max(char)

    # base 50 + CON(10)*2 + level(1)*5 = 75
    assert hp_max == 75
    # base 20 + INT(10)*2 = 40
    assert mana_max == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py -v -k compute_hp_mana_max`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.character_stats'`

- [ ] **Step 3: Write the implementation**

Create `app/services/character_stats.py`:

```python
"""
project: Adventure MUD
module: character_stats.py

Single source of truth for the HP/mana cap math used by the persistent
status-effect decay/regen pass (app/services/status_effects.py). This is a
deliberately narrow extraction: combat_service._derive_stats and
dashboard_helpers.build_party_payload compute their own (already-correct,
slightly different in scope -- they also derive attack/defense/speed) hp_max
/mana_max inline and are intentionally left untouched by this module, to
avoid risking working combat/dashboard code for a tangential dedup.
"""

from __future__ import annotations

import json
from typing import Tuple

from app.models.models import Character


def compute_hp_mana_max(character: Character) -> Tuple[int, int]:
    """Return (hp_max, mana_max) for a character, folding in gear and
    passive skill bonuses the same way combat does.
    """
    try:
        stats = json.loads(character.stats) if character.stats else {}
        if not isinstance(stats, dict):
            stats = {}
    except Exception:
        stats = {}

    level = getattr(character, "level", 1) or 1
    con = int(stats.get("con", stats.get("CON", 10)) or 10)
    intelligence = int(stats.get("int", stats.get("INT", 10)) or 10)

    hp_max = 50 + con * 2 + level * 5
    mana_max = 20 + intelligence * 2

    from app.loot.equip import gear_bonuses

    try:
        gear = json.loads(character.gear) if getattr(character, "gear", None) else {}
    except Exception:
        gear = {}
    gb = gear_bonuses(gear)

    try:
        from app.services.skill_effects import passive_bonuses

        for key, value in passive_bonuses(character.id).items():
            gb[key] = gb.get(key, 0) + value
    except Exception:
        pass

    hp_max += int(gb.get("max_hp", 0)) + int(gb.get("con", 0)) * 2
    mana_max += int(gb.get("mana", 0)) + int(gb.get("int", 0)) * 2

    return hp_max, mana_max
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py -v -k compute_hp_mana_max`

Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/character_stats.py tests/test_status_effects_decay.py
git commit -m "feat(services): add compute_hp_mana_max helper for status-effect decay"
```

---

### Task 3: `apply_tick_decay` — poison decay + regen

**Files:**
- Modify: `app/services/status_effects.py`
- Test: `tests/test_status_effects_decay.py` (append)

**Interfaces:**
- Consumes: `CharacterStatusEffect` (Task 1), `compute_hp_mana_max` (Task 2), `app.models.GameConfig.get(key: str) -> str | None`.
- Produces: `apply_tick_decay(delta: int) -> None`, importable as `from app.services.status_effects import apply_tick_decay`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_status_effects_decay.py`:

```python
from app.services.status_effects import apply_tick_decay


def test_apply_tick_decay_applies_poison_damage_and_floors_at_one_hp():
    from app.models import GameConfig

    # Zero out regen for this test so it isolates poison's floor behavior --
    # regen runs in the same pass and would otherwise heal the character
    # back above 1, which is correct combined behavior but not what this
    # test is checking.
    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 0.0, "mp_pct_per_tick": 0.0}))
    db.session.commit()

    char = _make_character("poisondecay")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 3, "current_mana": 20})
    db.session.add(char)
    db.session.commit()
    effect = CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 10}')
    db.session.add(effect)
    db.session.commit()

    apply_tick_decay(1)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    assert stats["hp"] == 1  # floored, not 0 or negative

    remaining_effect = CharacterStatusEffect.query.filter_by(character_id=char.id).first()
    assert remaining_effect.remaining == 4


def test_apply_tick_decay_deletes_expired_effects():
    char = _make_character("expiredecay")
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=1, data='{"damage": 1}'))
    db.session.commit()

    apply_tick_decay(1)

    assert CharacterStatusEffect.query.filter_by(character_id=char.id).count() == 0


def test_apply_tick_decay_regen_caps_at_max_and_scales_with_delta():
    char = _make_character("regendecay")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, mana_max = compute_hp_mana_max(char)

    apply_tick_decay(10)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    # 0.5% of hp_max per tick * 10 ticks, at least 1 hp healed, never exceeding max
    assert stats["hp"] > 1
    assert stats["hp"] <= hp_max
    assert stats["current_mana"] > 1
    assert stats["current_mana"] <= mana_max


def test_apply_tick_decay_noop_when_nothing_to_update():
    char = _make_character("noopdecay")
    hp_max, mana_max = compute_hp_mana_max(char)
    char.stats = json.dumps({"con": 10, "int": 10, "hp": hp_max, "current_mana": mana_max})
    db.session.add(char)
    db.session.commit()
    before = char.stats

    apply_tick_decay(5)

    db.session.refresh(char)
    assert char.stats == before


def test_apply_tick_decay_respects_custom_regen_rates_from_game_config():
    from app.models import GameConfig

    GameConfig.set("regen_rates", json.dumps({"hp_pct_per_tick": 50.0, "mp_pct_per_tick": 0.0}))
    db.session.commit()

    char = _make_character("customrates")
    char.stats = json.dumps({"con": 10, "int": 10, "hp": 1, "current_mana": 1})
    db.session.add(char)
    db.session.commit()
    hp_max, mana_max = compute_hp_mana_max(char)

    apply_tick_decay(1)

    db.session.refresh(char)
    stats = json.loads(char.stats)
    # 50% of hp_max in one tick should heal far more than the 0.5% default would
    assert stats["hp"] > 1 + int(hp_max * 0.01)
    # mp_pct_per_tick of 0 means no mana regen at all
    assert stats["current_mana"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py -v -k apply_tick_decay`

Expected: FAIL with `ImportError: cannot import name 'apply_tick_decay'`

- [ ] **Step 3: Write the implementation**

In `app/services/status_effects.py`, add near the top (after the existing imports) and at the end of the file (before `__all__`):

```python
import json
import math

DEFAULT_REGEN_RATES = {"hp_pct_per_tick": 0.5, "mp_pct_per_tick": 1.0}


def _load_regen_rates() -> Dict[str, float]:
    from app.models import GameConfig

    try:
        raw = GameConfig.get("regen_rates")
        if not raw:
            return dict(DEFAULT_REGEN_RATES)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(DEFAULT_REGEN_RATES)
        merged = dict(DEFAULT_REGEN_RATES)
        for key in ("hp_pct_per_tick", "mp_pct_per_tick"):
            try:
                merged[key] = float(data.get(key, merged[key]))
            except Exception:
                continue
        return merged
    except Exception:
        return dict(DEFAULT_REGEN_RATES)


def apply_tick_decay(delta: int) -> None:
    """Apply ``delta`` ticks worth of persisted effect decay and passive
    HP/MP regen to every character that has an active effect or is below
    their max HP/mana.

    Safe to call frequently; no-ops cleanly (no DB writes) if a given
    character has nothing to update. Never raises -- failures roll back and
    are swallowed, matching the rest of time_service.py's error handling, so
    a decay/regen failure never blocks the action that triggered it.
    """
    if delta <= 0:
        return

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character
    from app.services.character_stats import compute_hp_mana_max

    try:
        rates = _load_regen_rates()
        effect_char_ids = {
            row[0]
            for row in db.session.query(CharacterStatusEffect.character_id).distinct().all()
        }

        candidates = (
            Character.query.filter(Character.id.in_(effect_char_ids)).all()
            if effect_char_ids
            else []
        )
        # Also consider characters with no active effect but below max --
        # cheaper to just check every character with a stats blob than to
        # try to pre-filter by HP/mana, since both live inside JSON.
        all_chars = {c.id: c for c in Character.query.all()}
        for c in candidates:
            all_chars[c.id] = c

        changed_any = False
        for char in all_chars.values():
            try:
                stats = json.loads(char.stats) if char.stats else {}
                if not isinstance(stats, dict):
                    stats = {}
            except Exception:
                stats = {}

            hp_max, mana_max = compute_hp_mana_max(char)
            hp = int(stats.get("hp", hp_max))
            mana_key = "current_mana" if "current_mana" in stats else "mana"
            mana = int(stats.get(mana_key, mana_max))

            row_changed = False

            effects = CharacterStatusEffect.query.filter_by(character_id=char.id).all()
            for effect in effects:
                if effect.name == "poison":
                    try:
                        payload = json.loads(effect.data) if effect.data else {}
                    except Exception:
                        payload = {}
                    damage = int(payload.get("damage", 0)) * delta
                    if damage > 0:
                        hp = max(1, hp - damage)
                        row_changed = True
                effect.remaining -= delta
                if effect.remaining <= 0:
                    db.session.delete(effect)
                else:
                    db.session.add(effect)
                row_changed = True

            if hp < hp_max:
                hp = min(hp_max, hp + math.ceil(hp_max * rates["hp_pct_per_tick"] / 100 * delta))
                row_changed = True
            if mana < mana_max:
                mana = min(mana_max, mana + math.ceil(mana_max * rates["mp_pct_per_tick"] / 100 * delta))
                row_changed = True

            if row_changed:
                stats["hp"] = hp
                stats[mana_key] = mana
                char.stats = json.dumps(stats)
                db.session.add(char)
                changed_any = True

        if changed_any or effect_char_ids:
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
```

Also update the module-level docstring's "Extension points" note to mention this, and add `apply_tick_decay` to `__all__`:

```python
__all__ = [
    "apply_start_of_turn",
    "can_act",
    "add_effect",
    "apply_tick_decay",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_status_effects_decay.py -v`

Expected: PASS (all tests in the file so far)

- [ ] **Step 5: Commit**

```bash
git add app/services/status_effects.py tests/test_status_effects_decay.py
git commit -m "feat(services): add apply_tick_decay for persistent poison + out-of-combat regen"
```

---

### Task 4: Wire `apply_tick_decay` into `time_service.advance_time`

**Files:**
- Modify: `app/services/time_service.py`
- Modify: `tests/test_time_system.py`

**Interfaces:**
- Consumes: `apply_tick_decay(delta: int) -> None` (Task 3).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_time_system.py`:

```python
def test_advance_time_triggers_decay_outside_combat(auth_client):
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect, GameClock
    from app.models.models import Character
    from app.services import time_service

    char = Character.query.filter_by(name="Hero").first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    GameClock.get()  # ensure row exists
    time_service.advance_time(1, reason="test")

    db.session.refresh(char)
    stats = _json.loads(char.stats)
    assert stats["hp"] == 3  # 5 - 2 damage from poison this tick


def test_advance_time_does_not_decay_during_combat(auth_client):
    import json as _json

    from app import db
    from app.models import CharacterStatusEffect
    from app.models.models import Character
    from app.services import time_service

    char = Character.query.filter_by(name="Hero").first()
    assert char is not None
    char.stats = _json.dumps({"con": 10, "int": 10, "hp": 5, "current_mana": 5})
    db.session.add(char)
    db.session.add(CharacterStatusEffect(character_id=char.id, name="poison", remaining=5, data='{"damage": 2}'))
    db.session.commit()

    time_service.set_combat_state(True)
    try:
        time_service.advance_time(1, reason="test")
        db.session.refresh(char)
        stats = _json.loads(char.stats)
        assert stats["hp"] == 5  # unchanged -- combat pauses overworld ticking entirely
    finally:
        time_service.set_combat_state(False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_time_system.py -v -k advance_time_triggers`

Expected: FAIL — `test_advance_time_triggers_decay_outside_combat` fails because hp stays 5 (decay not wired yet).

- [ ] **Step 3: Wire the call**

In `app/services/time_service.py`, modify `advance_time`:

```python
def advance_time(delta: int, reason: str, actor_id: Optional[int] = None) -> int:
    """Advance the global clock by delta ticks if not in combat.

    Emits a 'time_update' Socket.IO event on namespace '/adventure'.
    Returns the new tick count.
    """
    if delta <= 0:
        return GameClock.get().tick
    if in_combat():  # Pause ticking during combat
        return GameClock.get().tick
    clock = GameClock.get()
    clock.tick += delta
    try:
        db.session.add(clock)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return clock.tick  # return last known even if failed
    from .status_effects import apply_tick_decay

    apply_tick_decay(delta)
    payload = {"tick": clock.tick, "delta": delta, "reason": reason, "actor_id": actor_id}
    try:
        socketio.emit("time_update", payload, namespace="/adventure")
    except Exception:
        # Emission failure should not rollback time advancement
        pass
    return clock.tick
```

(The import is local, mirroring the existing local imports elsewhere in this codebase to avoid import cycles between `time_service` and `status_effects`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_time_system.py -v`

Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add app/services/time_service.py tests/test_time_system.py
git commit -m "feat(time): apply persistent status-effect decay on overworld tick advance"
```

---

### Task 5: Combat integration — load, tick, and persist poison

**Files:**
- Modify: `app/services/combat_service.py`
- Create: `tests/test_combat_poison_persistence.py`

**Interfaces:**
- Consumes: `CharacterStatusEffect` (Task 1), `apply_start_of_turn(participant: dict) -> list[str]` (existing, `status_effects.py`).
- Produces: player participant dicts now always carry an `"effects"` key seeded from persisted poison; `_persist_party_resources` writes poison back on every combat-end path.

This task has three parts: (a) load persisted poison into the player snapshot at combat start, (b) actually apply start-of-turn effects to the active player each turn (today this only happens for monsters), (c) write surviving poison back to the DB wherever combat ends.

- [ ] **Step 1: Write the failing test**

Create `tests/test_combat_poison_persistence.py`:

```python
import json

from app import db
from app.models import CharacterStatusEffect
from app.models.models import Character
from app.services import combat_service


def _give_character_poison(auth_client, remaining=3, damage=4):
    char = Character.query.filter_by(name="Hero").first()
    assert char is not None
    db.session.add(
        CharacterStatusEffect(character_id=char.id, name="poison", remaining=remaining, data=json.dumps({"damage": damage}))
    )
    db.session.commit()
    return char


def test_persisted_poison_loads_into_combat_snapshot(auth_client):
    char = _give_character_poison(auth_client)

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
    )

    party = json.loads(session.party_snapshot_json)
    member = next(m for m in party["members"] if m.get("char_id") == char.id)
    assert any(e["name"] == "poison" for e in member.get("effects", []))


def test_poison_damages_player_on_their_turn(auth_client):
    char = _give_character_poison(auth_client, remaining=3, damage=4)
    starting_hp = json.loads(char.stats).get("hp")

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": -100, "xp": 5},
    )
    # Negative monster speed all but guarantees the player acts first.
    initiative = json.loads(session.initiative_json)
    if initiative[0]["type"] != "player":
        return  # initiative is randomized; skip on the rare unlucky roll

    combat_service.player_defend(session.id, char.user_id, session.version, actor_id=char.id)

    party = json.loads(combat_service._load_session(session.id).party_snapshot_json)
    member = next(m for m in party["members"] if m.get("char_id") == char.id)
    assert member["hp"] == starting_hp - 4


def test_remaining_poison_persists_after_combat_ends(auth_client):
    char = _give_character_poison(auth_client, remaining=10, damage=1)

    session = combat_service.start_session(
        user_id=char.user_id,
        monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
    )
    combat_service.player_flee(session.id, char.user_id, session.version, actor_id=char.id)

    # Flee has a 50% chance; retry a few times against fresh sessions if it failed.
    reloaded = combat_service._load_session(session.id)
    attempts = 0
    while reloaded.status != "complete" and attempts < 20:
        session = combat_service.start_session(
            user_id=char.user_id,
            monster={"name": "Rat", "hp": 10, "armor": 0, "speed": 5, "xp": 5},
        )
        combat_service.player_flee(session.id, char.user_id, session.version, actor_id=char.id)
        reloaded = combat_service._load_session(session.id)
        attempts += 1
    assert reloaded.status == "complete"

    remaining_effect = CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").first()
    assert remaining_effect is not None
    assert remaining_effect.remaining > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_combat_poison_persistence.py -v`

Expected: FAIL — `test_persisted_poison_loads_into_combat_snapshot` fails because `member.get("effects", [])` is empty (nothing loads persisted poison yet).

- [ ] **Step 3a: Load persisted poison at combat start**

In `app/services/combat_service.py`, modify `_derive_stats` to add an `"effects"` key. Insert this right before the function's `return` statement (currently ending at the line with `"buffs": [],`):

```python
    from app.models import CharacterStatusEffect

    try:
        effects = [
            {"name": row.name, "remaining": row.remaining, "data": json.loads(row.data) if row.data else {}}
            for row in CharacterStatusEffect.query.filter_by(character_id=char.id, name="poison").all()
        ]
    except Exception:
        effects = []

    return {
        # Controller user id retained separately from participant (character) id.
        "controller_id": char.user_id,
        "char_id": char.id,
        "name": char.name,
        "char_class": char_class,
        "hp": hp,
        "max_hp": max_hp,
        "attack": attack,
        "defense": defense,
        "speed": speed,
        "mana": mana,
        "mana_max": mana_max,
        "int_stat": INT,
        "str_stat": STR,
        "dex_stat": DEX,
        "resistances": {},
        "defending": False,
        "buffs": [],
        "effects": effects,
    }
```

- [ ] **Step 3b: Run test to verify the load path passes**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_combat_poison_persistence.py::test_persisted_poison_loads_into_combat_snapshot -v`

Expected: PASS

- [ ] **Step 4a: Apply start-of-turn effects to the active player**

`test_poison_damages_player_on_their_turn` will still fail at this point — today, `apply_start_of_turn` is only ever called for the monster (line ~1067), never for players. Modify `_skip_if_unconscious` in `app/services/combat_service.py`:

```python
def _skip_if_unconscious(session: CombatSession, party: Dict[str, Any], char_id: int) -> Optional[Dict[str, Any]]:
    """Apply start-of-turn effects (e.g. poison) to the acting character, then
    if they're downed (hp<=0), log it, skip their turn, and return the
    response dict the caller should return immediately.

    Returns None if the actor is conscious and the caller should proceed
    with its normal action handling.
    """
    actor_ref = _player_ref(party, char_id)
    if actor_ref:
        effect_logs = apply_start_of_turn(actor_ref)
        if effect_logs:
            for line in effect_logs:
                _append_log(session, line)
        session.party_snapshot_json = json.dumps(party)
    if actor_ref and actor_ref.get("hp", 0) <= 0:
        _append_log(session, f"{actor_ref.get('name', 'Character')} is unconscious and cannot act!")
        _advance_turn(session)
        _check_end(session)
        db.session.commit()
        _emit_session("combat_update", session)
        _emit_if_completed(session)
        session = _auto_progress_monster_after_player(session)
        return {"ok": True, "state": session.to_dict(), "skipped": True}
    return None
```

- [ ] **Step 4b: Run test to verify it passes**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_combat_poison_persistence.py::test_poison_damages_player_on_their_turn -v`

Expected: PASS

- [ ] **Step 5a: Persist remaining poison at combat end**

Modify `_persist_party_resources` in `app/services/combat_service.py` to also write back poison effects, right after the existing hp/mana persistence block (inside the same `for m in members:` loop, after the `current_mana` block and before `db.session.add(row); changed = True`):

```python
def _persist_party_resources(session: CombatSession):
    """Persist surviving party HP and mana back into Character.stats JSON,
    and write back any remaining poison effects to CharacterStatusEffect.

    Assumptions / Simplifications:
    - Character.stats JSON contains (or can accept) 'hp' and 'mana' keys representing current values.
    - We do not yet track max_hp/mana persistently outside stats snapshot; we only update current.
    - Dead characters (hp <= 0) persist with hp=0 and do not get their effects written back
      (a dead character's status effects are moot -- unrelated death/revival handling applies).
    - Silently ignores any character ids not found (e.g., temporary generated hero placeholder).
    """
    try:
        if not session.party_snapshot_json:
            return
        import json as _json

        from app.models import CharacterStatusEffect

        party = _json.loads(session.party_snapshot_json) or {}
        members = party.get("members", [])
        if not members:
            return
        char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
        changed = False
        for m in members:
            cid = m.get("char_id") or m.get("id")
            row = char_rows.get(cid)
            if not row or not row.stats:
                continue
            try:
                stats_obj = _json.loads(row.stats) if isinstance(row.stats, str) else {}
            except Exception:
                stats_obj = {}
            # Update only the instantaneous current values
            try:
                stats_obj["hp"] = int(m.get("hp", stats_obj.get("hp", 0)))
            except Exception:
                pass
            try:
                stats_obj["current_mana"] = int(m.get("mana", stats_obj.get("current_mana", stats_obj.get("mana", 0))))
            except Exception:
                pass
            row.stats = _json.dumps(stats_obj)
            db.session.add(row)
            changed = True

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
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
    except Exception:
        pass
```

- [ ] **Step 5b: Run all combat poison tests to verify they pass**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && python -m pytest -q tests/test_combat_poison_persistence.py -v`

Expected: PASS (all three tests)

- [ ] **Step 6: Commit**

```bash
git add app/services/combat_service.py tests/test_combat_poison_persistence.py
git commit -m "feat(combat): load/apply/persist poison across combat boundaries"
```

---

### Task 6: Full regression pass

**Files:** None (verification only).

- [ ] **Step 1: Run the full suite three times**

Run: `source .venv/bin/activate && export TEST_DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test" && export DATABASE_URL="$TEST_DATABASE_URL" && for i in 1 2 3; do python -m pytest -q 2>&1 | tail -3; done`

Expected: All three runs report the same `N passed, M skipped` with zero failures (matches the count from before this plan's changes, plus the new tests added in Tasks 1-5).

- [ ] **Step 2: Verify the migration story end-to-end against a fresh DB**

Run:
```bash
source .venv/bin/activate
export DATABASE_URL="postgresql://adventure:changeme@localhost:5433/adventure_test"
python -c "from app import create_app, db; app=create_app();
with app.app_context():
    db.drop_all()"
alembic upgrade head
```

Expected: No errors; `alembic current` reports `c7d8e9f0a1b2 (head)`.

- [ ] **Step 3: Update TODO.md**

Find the existing `- [ ] **Character cards need more detail (deferred feature, not a bug)**:` entry in `docs/superpowers/TODO.md` and replace it with:

```markdown
- [x] **Character cards Phase A: persistent status effects — done.** Added
      `CharacterStatusEffect` (new table, migration `c7d8e9f0a1b2`) so poison
      survives past combat instead of vanishing at combat end, decaying via
      the overworld GameClock (`apply_tick_decay`, hooked into
      `time_service.advance_time`) when out of a fight, and via the existing
      turn-based loop in combat (now actually wired for players too --
      `apply_start_of_turn` previously only ever ran for the monster).
      Out-of-combat poison floors at 1 HP (can't kill while exploring).
      Added slow passive HP/MP regen on the same tick hook, rates tunable
      via `GameConfig` `regen_rates` (defaults 0.5%/1% of max per tick).
      Extracted `compute_hp_mana_max` as the one place this phase's new code
      computes HP/mana caps -- deliberately did **not** touch the two
      pre-existing duplicated copies in `combat_service._derive_stats` and
      `dashboard_helpers.build_party_payload` to avoid risking working
      combat/dashboard code for a tangential dedup. Spec:
      `docs/superpowers/specs/2026-06-20-character-cards-phase-a-status-effects-design.md`.
      Foundation only -- no card UI changes yet. Three more phases remain,
      each its own future brainstorm/spec:
      - [ ] Phase B: new effect sources (potion regen-over-time buff, camp buff).
      - [ ] Phase C: dashboard roster card redesign (collapsed HP/MP/buffs/debuffs,
            expand-on-select to a context area with actions + full stats).
      - [ ] Phase D: combat party card redesign (collapsed, auto-expand on that
            character's turn) + accurate per-character spell costs.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/TODO.md
git commit -m "docs(todo): mark character cards Phase A (status effects) done"
```
