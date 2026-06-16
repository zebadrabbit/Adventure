# Procedural Floor Loot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the dungeon floor drop procedural gear instances (not just catalog items), controlled by a config-driven chance and rarity weights, claimable into a character's bag.

**Architecture:** `DungeonLoot` gains a nullable `instance_json` (and `item_id` becomes nullable); exactly one is set per node. `generate_loot_for_seed` rolls a per-node `procedural_gear_chance` from `GameConfig["floor_loot"]` and, on a hit, places a `generate_item(...)` instance with a config-weighted rarity. `claim_loot` branches: instance nodes append the gear dict to the bag (instance-aware utils), catalog nodes use the existing slug path. Determinism is preserved (all rolls use the seeded `rng`).

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Migrate (Alembic), pytest, PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-06-16-procedural-floor-loot-design.md`

**Test DB:** Prefix every pytest command with `TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test` and use the project venv (`.venv/bin/python`). The test schema is built by `db.create_all()` in `tests/conftest.py`, so new columns appear automatically. The session test DB is NOT reset between unmarked tests and `create_user` is idempotent, so any test creating users/characters must use UNIQUE usernames (uuid suffix).

---

## File Structure

- **Modify** `app/models/loot.py` — `item_id` nullable; add `instance_json`; document the one-of invariant.
- **Modify** `app/loot/generator.py` — add `_floor_loot_config()`; branch placement in `generate_loot_for_seed`.
- **Modify** `app/routes/loot_api.py` — branch `claim_loot` for instance nodes.
- **Create** `migrations/versions/<rev>_floor_loot_instance.py`.
- **Create** `tests/test_floor_loot_procedural.py`.

---

## Task 1: Schema — make DungeonLoot hold a gear instance

**Files:**
- Modify: `app/models/loot.py`
- Test: `tests/test_floor_loot_procedural.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_floor_loot_procedural.py
import json

from app import db
from app.models.loot import DungeonLoot


def test_dungeon_loot_can_store_instance_without_item_id():
    inst = {"uid": "abc123", "base": "shortsword", "slot": "weapon", "name": "Test Blade", "rarity": "rare", "value": 100}
    row = DungeonLoot(seed=12345, x=1, y=2, z=0, item_id=None, instance_json=json.dumps(inst))
    db.session.add(row)
    db.session.commit()
    fetched = DungeonLoot.query.filter_by(seed=12345, x=1, y=2).first()
    assert fetched.item_id is None
    assert json.loads(fetched.instance_json)["uid"] == "abc123"
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_floor_loot_procedural.py::test_dungeon_loot_can_store_instance_without_item_id -v`
Expected: FAIL — either `TypeError` (no `instance_json` kwarg) or an IntegrityError on null `item_id`.

- [ ] **Step 3: Modify `app/models/loot.py`**

Change the `item_id` column to nullable and add `instance_json`. The model becomes:

```python
from datetime import datetime

from app import db


class DungeonLoot(db.Model):
    """A loot node on the dungeon floor.

    Exactly one of `item_id` (a catalog Item) or `instance_json` (a procedurally
    generated gear instance dict) is set per row.
    """

    __tablename__ = "dungeon_loot"
    id = db.Column(db.Integer, primary_key=True)
    seed = db.Column(db.BigInteger, index=True, nullable=False)
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    z = db.Column(db.Integer, nullable=False, default=0)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)
    instance_json = db.Column(db.Text, nullable=True)
    claimed = db.Column(db.Boolean, nullable=False, default=False)
    claimed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def mark_claimed(self):
        if not self.claimed:
            from datetime import datetime as _dt

            self.claimed = True
            self.claimed_at = _dt.utcnow()
```

- [ ] **Step 4: Reset the test schema so the new column + nullability apply, then run**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -c "import os; os.environ['DATABASE_URL']=os.environ['TEST_DATABASE_URL']; from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/test_floor_loot_procedural.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models/loot.py tests/test_floor_loot_procedural.py
git commit -m "feat(loot): DungeonLoot can store a procedural gear instance"
```

---

## Task 2: Placement — drop procedural gear by config chance

**Files:**
- Modify: `app/loot/generator.py`
- Test: `tests/test_floor_loot_procedural.py` (append)

**Background:** `generate_loot_for_seed(cfg, walkable_tiles)` selects `chosen_tiles` and `chosen_items` (catalog), then creates `DungeonLoot(seed, x, y, z, item_id=item.id)` per tile. We add a per-tile roll: on a hit, place an instance instead. `generate_item(level, rarity=None, slot=None, rng=...)` already exists in this module; `_level_window(cfg.avg_party_level)` gives `(lo, hi)`; `RARITY_ORDER` is imported. `GameConfig` (`app/models/models.py`) has `GameConfig.get(key) -> str|None`.

- [ ] **Step 1: Append failing tests**

```python
# tests/test_floor_loot_procedural.py (append)
import json as _json

from app.loot.generator import LootConfig, generate_loot_for_seed
from app.models.models import GameConfig


def _set_floor_loot(chance):
    GameConfig.set("floor_loot", _json.dumps({"procedural_gear_chance": chance}))


def _tiles(n=40):
    return [(i, 0) for i in range(n)]


def test_all_procedural_when_chance_one():
    _set_floor_loot(1.0)
    seed = 777001
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    created = generate_loot_for_seed(cfg, _tiles())
    assert created > 0
    rows = DungeonLoot.query.filter_by(seed=seed).all()
    assert rows and all(r.item_id is None and r.instance_json for r in rows)
    assert all(_json.loads(r.instance_json).get("uid") for r in rows)


def test_all_catalog_when_chance_zero():
    _set_floor_loot(0.0)
    seed = 777002
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    created = generate_loot_for_seed(cfg, _tiles())
    assert created > 0
    rows = DungeonLoot.query.filter_by(seed=seed).all()
    assert rows and all(r.item_id is not None and r.instance_json is None for r in rows)


def test_placement_is_deterministic():
    _set_floor_loot(1.0)
    seed = 777003
    for s in (seed,):
        DungeonLoot.query.filter_by(seed=s).delete()
    db.session.commit()
    cfg = LootConfig(avg_party_level=5, width=80, height=80, seed=seed)
    generate_loot_for_seed(cfg, _tiles())
    first = sorted((r.x, r.y, _json.loads(r.instance_json)["uid"]) for r in DungeonLoot.query.filter_by(seed=seed).all())
    # Wipe and regenerate with the same seed
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    generate_loot_for_seed(cfg, _tiles())
    second = sorted((r.x, r.y, _json.loads(r.instance_json)["uid"]) for r in DungeonLoot.query.filter_by(seed=seed).all())
    assert first == second
```

Check the real `LootConfig` field names before running (it is a dataclass with
`avg_party_level`, `width`, `height`, `seed`, and defaults `desired_chests`,
`spread_factor`). Adjust the constructor kwargs if the field set differs.

- [ ] **Step 2: Run, confirm FAIL**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_floor_loot_procedural.py -v`
Expected: FAIL — placements are all catalog (instance_json is None) because the roll isn't implemented.

- [ ] **Step 3: Implement in `app/loot/generator.py`**

(a) Add `GameConfig` to the model imports near the top:
```python
from app.models.models import GameConfig, Item
```

(b) Add a config loader and a weighted-rarity helper above `generate_loot_for_seed`:
```python
_DEFAULT_FLOOR_LOOT = {
    "procedural_gear_chance": 0.25,
    "rarity_weights": {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1},
}


def _floor_loot_config() -> dict:
    """Read floor-loot tuning from GameConfig['floor_loot'] with safe fallback."""
    raw = GameConfig.get("floor_loot")
    if not raw:
        return dict(_DEFAULT_FLOOR_LOOT)
    try:
        cfg = json.loads(raw)
    except Exception:
        return dict(_DEFAULT_FLOOR_LOOT)
    merged = dict(_DEFAULT_FLOOR_LOOT)
    merged.update(cfg or {})
    return merged


def _roll_floor_rarity(rng: random.Random, weights: dict) -> str:
    """Weighted rarity pick restricted to known rarities; falls back to common."""
    pairs = [(r, int(w)) for r, w in (weights or {}).items() if r in RARITIES and int(w) > 0]
    if not pairs:
        return "common"
    total = sum(w for _, w in pairs)
    roll = rng.randint(1, total)
    upto = 0
    for r, w in pairs:
        upto += w
        if roll <= upto:
            return r
    return pairs[-1][0]
```
Note: `json` must be importable in this module — add `import json` to the top-level imports if it is not already present.

(c) In `generate_loot_for_seed`, load the config once (after `rng` is created):
```python
    floor_cfg = _floor_loot_config()
    gear_chance = float(floor_cfg.get("procedural_gear_chance", 0.0) or 0.0)
    rarity_weights = floor_cfg.get("rarity_weights", {})
```

(d) Replace the final placement loop so each tile rolls for procedural gear. The current loop is:
```python
    created = 0
    for (x, y, z), item in zip(chosen_tiles, chosen_items):
        if DungeonLoot.query.filter_by(seed=cfg.seed, x=x, y=y, z=z).first():
            continue
        db.session.add(DungeonLoot(seed=cfg.seed, x=x, y=y, z=z, item_id=item.id))
        created += 1
    if created:
        db.session.commit()
    return created
```
Change it to:
```python
    created = 0
    for (x, y, z), item in zip(chosen_tiles, chosen_items):
        if DungeonLoot.query.filter_by(seed=cfg.seed, x=x, y=y, z=z).first():
            continue
        if rng.random() < gear_chance:
            rarity = _roll_floor_rarity(rng, rarity_weights)
            level = rng.randint(lo, hi)
            inst = generate_item(level, rarity=rarity, rng=rng)
            db.session.add(
                DungeonLoot(seed=cfg.seed, x=x, y=y, z=z, item_id=None, instance_json=json.dumps(inst))
            )
        else:
            db.session.add(DungeonLoot(seed=cfg.seed, x=x, y=y, z=z, item_id=item.id))
        created += 1
    if created:
        db.session.commit()
    return created
```
`lo, hi` are already in scope (from `_level_window(cfg.avg_party_level)` near the top of the function). Keep `chosen_items` selection as-is — catalog items are still used on the miss branch.

- [ ] **Step 4: Run, confirm PASS**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_floor_loot_procedural.py -v`
Expected: PASS. Also run the existing loot suite to confirm no regression:
`TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_loot_generation.py -v`
Expected: PASS (those tests don't set `floor_loot`, so the default 0.25 chance applies; they assert counts/idempotence, not catalog-vs-instance, so they should still pass — if any asserts every row has an `item_id`, set `floor_loot` chance to 0.0 in that test's setup and note it).

- [ ] **Step 5: Commit**

```bash
git add app/loot/generator.py tests/test_floor_loot_procedural.py
git commit -m "feat(loot): place procedural gear on the floor by config chance"
```

---

## Task 3: Claim — pick up a floor gear instance

**Files:**
- Modify: `app/routes/loot_api.py`
- Test: `tests/test_floor_loot_procedural.py` (append)

**Background:** `claim_loot` currently resolves `target_char`, then does
`item = db.session.get(Item, row.item_id)` and an encumbrance-checked `add_item(inv, item.slug, 1)`. For an instance node we instead append the parsed instance dict to the bag. The inventory utils are instance-aware: `load_inventory` preserves `{uid,...}` dicts and `compute_weight`/`can_add_item` handle them (instance weight defaults to 1.0).

- [ ] **Step 1: Append failing test**

```python
# tests/test_floor_loot_procedural.py (append)
import uuid

from app.models.dungeon_instance import DungeonInstance
from tests.factories import create_character, create_user


def test_claim_instance_node_appends_gear_to_bag(client):
    user = create_user("floot_" + uuid.uuid4().hex[:8])
    char = create_character(user, name="Picker", items=[])
    seed = 777100
    DungeonLoot.query.filter_by(seed=seed).delete()
    db.session.commit()
    inst = {"uid": "floorgear1", "base": "dagger", "slot": "weapon", "name": "Floor Dagger", "rarity": "rare", "value": 120}
    row = DungeonLoot(seed=seed, x=3, y=3, z=0, item_id=None, instance_json=_json.dumps(inst))
    db.session.add(row)
    di = DungeonInstance(user_id=user.id, seed=seed, pos_x=0, pos_y=0, pos_z=0)
    db.session.add(di)
    db.session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id
        sess["dungeon_instance_id"] = di.id

    resp = client.post(f"/api/dungeon/loot/claim/{row.id}", json={"character_id": char.id})
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(char)
    bag = _json.loads(char.items)
    assert any(isinstance(o, dict) and o.get("uid") == "floorgear1" for o in bag)
    db.session.refresh(row)
    assert row.claimed is True
```

The claim flow requires the session to carry `dungeon_instance_id` whose `seed`
matches the loot row, plus a user id; the test sets these. The `party` session key
is absent, so claim uses the "first owned character" / explicit `character_id` path —
confirm by reading `claim_loot`, and if a party-membership check blocks the explicit
character, set `sess["party"]` to include the character's name.

- [ ] **Step 2: Run, confirm FAIL**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_floor_loot_procedural.py::test_claim_instance_node_appends_gear_to_bag -v`
Expected: FAIL — current code does `db.session.get(Item, row.item_id)` with `item_id is None`, so `item` is None and the gear is never added (response item is null / bag empty).

- [ ] **Step 3: Implement the instance branch in `claim_loot`**

In `app/routes/loot_api.py`, after `row.mark_claimed()` and before the catalog
`item = db.session.get(Item, row.item_id)` handling, add an instance branch. Locate:
```python
    # Mark claimed & assign
    row.mark_claimed()
    item = db.session.get(Item, row.item_id)
    enc_state = None
    if target_char and item:
        ...
```
Replace that whole block (down to the final `db.session.commit()` / return) with logic that handles instances first. Concretely, insert this BEFORE the existing `item = db.session.get(Item, row.item_id)` line:

```python
    # Procedural gear instance node: append the instance dict to the bag.
    if row.instance_json:
        import json as _json

        instance = _json.loads(row.instance_json)
        enc_state = None
        if target_char:
            inv = load_inventory(target_char.items)
            base_stats = {}
            try:
                base_stats = _json.loads(target_char.stats or "{}")
            except Exception:
                base_stats = {}
            str_score = int(base_stats.get("str", 10))
            # Encumbrance: predict adding one instance. compute_weight (used by
            # encumbrance_state) is instance-aware and reads the instance's own
            # "weight" (default 1.0), so we evaluate the prospective bag directly.
            from app.inventory.utils import encumbrance_state

            prospective_inv = inv + [instance]
            enc_state = encumbrance_state(str_score, prospective_inv)
            if enc_state.get("status") == "blocked":
                row.claimed = False
                db.session.flush()
                return jsonify({"error": "encumbered", "message": "Cannot carry more; over hard capacity limit", "encumbrance": enc_state}), 400
            inv.append(instance)
            target_char.items = dump_inventory(inv)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "db error"}), 500
        return jsonify(
            {
                "claimed": True,
                "item": {"uid": instance.get("uid"), "name": instance.get("name"), "rarity": instance.get("rarity")},
                "character_id": (target_char.id if target_char else None),
                "encumbrance": enc_state,
            }
        )

    item = db.session.get(Item, row.item_id)
```

Note: `encumbrance_state(str_score, inv)` returns a dict with a `"status"` key whose
values are `"normal" | "encumbered" | "blocked"` (verified in `app/inventory/utils.py`).
The catalog branch uses `can_add_item(...)` (which looks up `Item.weight` by slug and
so does not apply to instances); for instances we evaluate the prospective bag with
`encumbrance_state` directly, since `compute_weight` already reads an instance's own
`weight`. Behavior matches the catalog branch: blocked → unclaim + 400; else append +
commit.

- [ ] **Step 4: Run, confirm PASS**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_floor_loot_procedural.py -v`
Expected: PASS (all floor-loot tests). Then regression:
`TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_loot_generation.py tests/test_loot_instances.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/loot_api.py tests/test_floor_loot_procedural.py
git commit -m "feat(loot): claim floor gear instances into the bag"
```

---

## Task 4: Alembic migration

**Files:**
- Create: `migrations/versions/<rev>_floor_loot_instance.py`

The current Alembic head is `f1a2b3c4d5e6` (the hoard migration). Hand-write a
migration (do NOT autogenerate — the dev DB may be in a `create_all` state).

- [ ] **Step 1: Read a recent migration** (`migrations/versions/f1a2b3c4d5e6_add_hoard_table.py`) to match header/style.

- [ ] **Step 2: Create `migrations/versions/a1b2c3d4e5f6_floor_loot_instance.py`** (pick a unique rev id; set `down_revision = "f1a2b3c4d5e6"`):

```python
"""floor loot procedural instance

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("dungeon_loot", sa.Column("instance_json", sa.Text(), nullable=True))
    op.alter_column("dungeon_loot", "item_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("dungeon_loot", "item_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("dungeon_loot", "instance_json")
```
Match the exact header/variable style of the existing migration files.

- [ ] **Step 3: Verify it is the new single head**

```bash
.venv/bin/python -m alembic heads 2>&1 | head
```
Expected: your new revision id reported as head. (If alembic can't run because the dev DB is unmigrated, instead confirm the file parses with `ast.parse` and that no other migration uses your rev id as `down_revision`.)

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/
git commit -m "chore(db): migration for dungeon_loot instance_json + nullable item_id"
```

---

## Task 5: Full verification

- [ ] **Step 1: Fresh schema + run new and adjacent suites**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -c "import os; os.environ['DATABASE_URL']=os.environ['TEST_DATABASE_URL']; from app import create_app, db; app=create_app()
with app.app_context():
    db.drop_all(); db.create_all()"
.venv/bin/python -m pytest tests/test_floor_loot_procedural.py tests/test_loot_generation.py tests/test_loot_instances.py tests/test_inventory_encumbrance.py -q
```
Expected: all PASS.

- [ ] **Step 2: Broader sanity (exclude the known-flaky combat-persistence race)**

```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: green except the two pre-existing shared-session contamination failures in `tests/test_encounter_config.py` (documented; not from this work). Note anything new.

---

## Notes for the implementer

- **Determinism is the contract:** every random decision (gear-vs-catalog roll, rarity,
  level, and `generate_item`'s internal rolls) must use the function's seeded `rng`.
  Do not introduce `random.random()` or unseeded randomness.
- **One-of invariant:** a placed node sets exactly one of `item_id` / `instance_json`.
- **Encumbrance for instances:** reuse the real `app/inventory/utils.py` API; confirm
  the blocked signal rather than assuming a key name.
- **Existing loot tests:** if any assert that every generated row has an `item_id`,
  they will break under the default 0.25 chance — set `floor_loot` chance to 0.0 in
  that test's setup (and note it) rather than weakening the new behavior.
