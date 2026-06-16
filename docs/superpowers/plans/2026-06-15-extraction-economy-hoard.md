# Extraction Economy & the Hoard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent per-user Hoard and wire the dormant extraction scaffold into combat so that a run's haul (bag + run-purse coin) pools into the Hoard on extraction, is lost on a party wipe, and town vendors transact against the Hoard.

**Architecture:** A new `Hoard` SQLAlchemy model (one row per user) stores secured gear (`items_json`, same canonical format as `Character.items`) and safe currency (`copper`). A `hoard_service` module provides pure helpers (deposit/withdraw/pool). `Character.gold` is reinterpreted as the at-risk run-purse. Combat death is persisted to `Character` and locks characters to the dungeon instance; extraction pools survivors' haul into the Hoard; a wipe permadeaths the party without pooling. Town trading (`trading_api`) is repointed from `Character.gold` to the Hoard.

**Tech Stack:** Flask, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, pytest, PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-06-15-extraction-economy-hoard-design.md`

**Test DB:** All `pytest` commands require `TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test`. The test schema is built by `db.create_all()` in `tests/conftest.py`, so a new model is picked up automatically once imported in `app/__init__.py`. Prefix every pytest command with that env var (or `export` it once per shell).

---

## File Structure

- **Create** `app/models/hoard.py` — the `Hoard` model + `get_or_create(user_id)`.
- **Create** `app/economy/hoard_service.py` — `deposit_items`, `deposit_copper`, `withdraw_to_character`, `pool_run_haul`.
- **Create** `app/routes/hoard_api.py` — `GET /api/hoard`, `POST /api/hoard/withdraw`, `POST /api/dungeon/loot-body`.
- **Create** `tests/test_hoard.py`, `tests/test_hoard_api.py`, `tests/test_extraction_economy.py`.
- **Modify** `app/__init__.py` — import the `Hoard` model and register `bp_hoard`.
- **Modify** `app/services/extraction_service.py` — pool haul on extract.
- **Modify** `app/services/combat_service.py` — persist death + lock; wipe = permadeath.
- **Modify** `app/routes/trading_api.py` — repoint buy/sell to the Hoard.
- **Modify** `tests/test_trading_economy.py` — update for hoard-based trading.
- **Create** an Alembic migration for the `hoard` table.

---

## Task 1: Hoard model

**Files:**
- Create: `app/models/hoard.py`
- Test: `tests/test_hoard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hoard.py
from app import db
from app.models.hoard import Hoard
from tests.factories import create_user


def test_get_or_create_is_idempotent():
    user = create_user("hoarder_a")
    h1 = Hoard.get_or_create(user.id)
    db.session.commit()
    h2 = Hoard.get_or_create(user.id)
    assert h1.id == h2.id
    assert h1.copper == 0
    assert h1.items_json == "[]"


def test_hoard_one_row_per_user():
    user = create_user("hoarder_b")
    Hoard.get_or_create(user.id)
    db.session.commit()
    Hoard.get_or_create(user.id)
    db.session.commit()
    assert Hoard.query.filter_by(user_id=user.id).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_hoard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.hoard'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/models/hoard.py
"""Per-user Hoard: persistent secured gear + currency (account-level vault)."""

from __future__ import annotations

from app import db


class Hoard(db.Model):
    """One row per user. Survives character permadeath.

    items_json uses the canonical inventory format from app/inventory/utils.py:
    a JSON list mixing {"slug","qty"} stacks and procedural gear instance dicts
    (with a "uid"). copper is the safe currency (smallest unit; see Spec 1).
    """

    __tablename__ = "hoard"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False, index=True)
    items_json = db.Column(db.Text, nullable=False, default="[]")
    copper = db.Column(db.Integer, nullable=False, default=0)

    @staticmethod
    def get_or_create(user_id: int) -> "Hoard":
        """Return the user's hoard, creating (and adding to the session) if absent."""
        hoard = Hoard.query.filter_by(user_id=user_id).first()
        if hoard is None:
            hoard = Hoard(user_id=user_id, items_json="[]", copper=0)
            db.session.add(hoard)
            db.session.flush()
        return hoard
```

- [ ] **Step 4: Register the model so the test schema includes it**

Modify `app/__init__.py` — add an import alongside the other model imports (search for an existing line like `from app.models.models import ...`; add after it):

```python
from app.models.hoard import Hoard  # noqa: E402,F401  # ensure table is registered
```

- [ ] **Step 5: Run test to verify it passes**

Run: `TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test .venv/bin/python -m pytest tests/test_hoard.py -v`
Expected: PASS (2 passed). `conftest`'s `db.create_all()` creates the new `hoard` table.

- [ ] **Step 6: Commit**

```bash
git add app/models/hoard.py app/__init__.py tests/test_hoard.py
git commit -m "feat(hoard): per-user Hoard model with get_or_create"
```

---

## Task 2: Hoard service helpers

**Files:**
- Create: `app/economy/hoard_service.py`
- Test: `tests/test_hoard.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hoard.py`:

```python
import json

from app.economy import hoard_service
from app.models.models import Character
from tests.factories import create_character


def test_deposit_items_merges_stacks_and_appends_instances():
    user = create_user("hoarder_c")
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 2}])
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 3}])
    hoard_service.deposit_items(hoard, [{"uid": "g1", "name": "Sword", "value": 100}])
    items = json.loads(hoard.items_json)
    stack = next(i for i in items if i.get("slug") == "potion_heal_l1")
    assert stack["qty"] == 5
    assert any(i.get("uid") == "g1" for i in items)


def test_deposit_copper():
    user = create_user("hoarder_d")
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 250)
    hoard_service.deposit_copper(hoard, 50)
    assert hoard.copper == 300


def test_withdraw_instance_to_character():
    user = create_user("hoarder_e")
    char = create_character(user, name="Mule", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"uid": "g9", "name": "Axe", "value": 200}])
    ok = hoard_service.withdraw_to_character(hoard, char, uid="g9")
    assert ok is True
    assert json.loads(hoard.items_json) == []
    assert any(i.get("uid") == "g9" for i in json.loads(char.items))


def test_pool_run_haul_moves_bag_and_purse_then_zeroes():
    user = create_user("hoarder_f")
    char = create_character(user, name="Runner", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char.gold = 500  # run-purse (copper)
    hoard = Hoard.get_or_create(user.id)
    hoard_service.pool_run_haul(hoard, char)
    assert hoard.copper == 500
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    assert char.gold == 0
    assert json.loads(char.items) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.economy.hoard_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/economy/hoard_service.py
"""Operations that move value between a character's at-risk run state and the Hoard.

Reuses the canonical inventory format and helpers from app.inventory.utils so the
hoard, character bags, and trading all speak the same shape:
  - stacks:    {"slug": str, "qty": int}
  - instances: {"uid": str, ...}  (procedural gear)
"""

from __future__ import annotations

import json
from typing import List

from app import db
from app.inventory.utils import (
    add_item,
    find_instance,
    load_inventory,
    remove_instance,
    remove_one,
)
from app.models.hoard import Hoard
from app.models.models import Character


def _load(raw: str | None) -> List[dict]:
    return load_inventory(raw)


def deposit_items(hoard: Hoard, entries: List[dict]) -> None:
    """Merge a list of canonical entries (stacks and/or instances) into the hoard."""
    items = _load(hoard.items_json)
    for entry in entries or []:
        if entry.get("uid"):
            items.append(entry)
        elif entry.get("slug"):
            add_item(items, entry["slug"], int(entry.get("qty", 1)))
    hoard.items_json = json.dumps(items)


def deposit_copper(hoard: Hoard, amount: int) -> None:
    hoard.copper = (hoard.copper or 0) + max(0, int(amount))


def withdraw_to_character(hoard: Hoard, character: Character, *, slug: str | None = None, uid: str | None = None) -> bool:
    """Move one stack-unit (by slug) or one instance (by uid) from hoard to a bag.

    Returns False if the item is not in the hoard.
    """
    hoard_items = _load(hoard.items_json)
    bag = _load(character.items)
    if uid:
        inst = find_instance(hoard_items, uid)
        if not inst:
            return False
        remove_instance(hoard_items, uid)
        bag.append(inst)
    elif slug:
        if not remove_one(hoard_items, slug):
            return False
        add_item(bag, slug, 1)
    else:
        return False
    hoard.items_json = json.dumps(hoard_items)
    character.items = json.dumps(bag)
    return True


def pool_run_haul(hoard: Hoard, character: Character) -> None:
    """Move a character's entire bag + run-purse into the hoard, then zero them."""
    bag = _load(character.items)
    deposit_items(hoard, bag)
    deposit_copper(hoard, character.gold or 0)
    character.items = "[]"
    character.gold = 0
```

- [ ] **Step 4: Add the package init if missing**

The `app/economy/__init__.py` already exists (from Spec 1). No action unless the import fails.

- [ ] **Step 5: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard.py -v`
Expected: PASS (6 passed total).

- [ ] **Step 6: Commit**

```bash
git add app/economy/hoard_service.py tests/test_hoard.py
git commit -m "feat(hoard): deposit/withdraw/pool service helpers"
```

---

## Task 3: Hoard API (view + withdraw)

**Files:**
- Create: `app/routes/hoard_api.py`
- Modify: `app/__init__.py` (register blueprint)
- Test: `tests/test_hoard_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hoard_api.py
import json

from app import db
from app.economy import hoard_service
from app.models.hoard import Hoard


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["user_id"] = user.id


def test_get_hoard_returns_items_and_display(client):
    from tests.factories import create_user

    user = create_user("hapi_a")
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 12345)
    db.session.commit()
    _login(client, user)
    resp = client.get("/api/hoard")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["copper"] == 12345
    assert data["copper_display"] == "1g 23s 45c"


def test_withdraw_instance_to_character(client):
    from tests.factories import create_character, create_user

    user = create_user("hapi_b")
    char = create_character(user, name="Mule", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_items(hoard, [{"uid": "wx", "name": "Bow", "value": 90}])
    db.session.commit()
    _login(client, user)
    resp = client.post("/api/hoard/withdraw", json={"character_id": char.id, "uid": "wx"})
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(char)
    assert any(i.get("uid") == "wx" for i in json.loads(char.items))
```

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard_api.py -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Write minimal implementation**

```python
# app/routes/hoard_api.py
"""Hoard API: view the per-user vault and withdraw items to a character."""

import json

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.economy import hoard_service
from app.economy.currency import format_copper
from app.models.hoard import Hoard
from app.models.models import Character

bp_hoard = Blueprint("hoard_api", __name__)


@bp_hoard.route("/api/hoard", methods=["GET"])
@login_required
def get_hoard():
    hoard = Hoard.get_or_create(current_user.id)
    db.session.commit()
    return jsonify(
        {
            "items": json.loads(hoard.items_json or "[]"),
            "copper": hoard.copper or 0,
            "copper_display": format_copper(hoard.copper or 0),
        }
    )


@bp_hoard.route("/api/hoard/withdraw", methods=["POST"])
@login_required
def withdraw():
    data = request.get_json() or {}
    character_id = data.get("character_id")
    slug = data.get("slug")
    uid = data.get("uid")
    if not character_id or not (slug or uid):
        return jsonify({"error": "Missing required fields"}), 400

    char = db.session.get(Character, character_id)
    if not char or char.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404

    hoard = Hoard.get_or_create(current_user.id)
    ok = hoard_service.withdraw_to_character(hoard, char, slug=slug, uid=uid)
    if not ok:
        return jsonify({"error": "Item not in hoard"}), 400
    db.session.commit()
    return jsonify({"success": True})
```

- [ ] **Step 4: Register the blueprint**

Modify `app/__init__.py`: add the import near the other route imports (after the `bp_extraction` import line) and register it with the other `app.register_blueprint(...)` calls (after `app.register_blueprint(bp_extraction)`):

```python
from app.routes.hoard_api import bp_hoard  # noqa: E402  # isort: skip
```
```python
app.register_blueprint(bp_hoard)
```

- [ ] **Step 5: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard_api.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routes/hoard_api.py app/__init__.py tests/test_hoard_api.py
git commit -m "feat(hoard): GET /api/hoard and POST /api/hoard/withdraw"
```

---

## Task 4: Pool the run haul into the Hoard on extraction

**Files:**
- Modify: `app/services/extraction_service.py` (inside `extract_party`)
- Test: `tests/test_extraction_economy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extraction_economy.py
import json

from app import db
from app.models.dungeon_instance import DungeonInstance
from app.models.hoard import Hoard
from app.services import extraction_service
from tests.factories import create_character, create_instance, create_user


def _instance_for(user):
    inst = create_instance(user, seed=4242)
    inst.extraction_available = True  # no early-extraction penalty
    db.session.commit()
    return inst


def test_extract_pools_bag_and_purse_into_hoard():
    user = create_user("extr_a")
    inst = _instance_for(user)
    char = create_character(user, name="A", items=[{"slug": "potion_heal_l1", "qty": 2}])
    char.gold = 300
    char.locked_dungeon_id = inst.id
    db.session.commit()

    ok, msg, result = extraction_service.extract_party(inst, [char.id], user.id)
    assert ok, msg
    hoard = Hoard.query.filter_by(user_id=user.id).first()
    assert hoard.copper == 300
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    db.session.refresh(char)
    assert char.gold == 0
    assert json.loads(char.items) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_extraction_economy.py::test_extract_pools_bag_and_purse_into_hoard -v`
Expected: FAIL — `hoard` is None (extract doesn't pool yet).

- [ ] **Step 3: Implement — pool haul for extracting characters**

In `app/services/extraction_service.py`, add imports at the top (after the existing imports):

```python
from app.economy import hoard_service
from app.models.hoard import Hoard
```

Then in `extract_party`, inside the `for char in extracting_chars:` loop, AFTER the existing revive block and BEFORE the final `db.session.commit()`, add pooling. Replace the existing loop body's end so it reads:

```python
    # Apply penalties to extracting characters
    hoard = Hoard.get_or_create(user_id)
    for char in extracting_chars:
        # Apply XP penalty
        if penalties["xp_multiplier"] < 1.0:
            char.xp = int(char.xp * penalties["xp_multiplier"])

        # Unlock character from dungeon
        char.locked_in_dungeon = False
        char.locked_dungeon_id = None

        # Revive if dead (successfully extracted)
        if char.is_dead:
            char.is_dead = False
            try:
                stats = json.loads(char.stats) if isinstance(char.stats, str) else char.stats
                hp_max = stats.get("hp_max", stats.get("HP", 100))
                stats["hp"] = hp_max
                stats["HP"] = hp_max
                char.stats = json.dumps(stats)
            except Exception:
                pass

        # Pool this character's run haul (bag + run-purse) into the hoard
        hoard_service.pool_run_haul(hoard, char)
```

(Leave the rest of the function — left-behind permadeath handling, commit, result — unchanged.)

- [ ] **Step 4: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_extraction_economy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/extraction_service.py tests/test_extraction_economy.py
git commit -m "feat(extraction): pool extracting characters' haul into the hoard"
```

---

## Task 5: Persist death and lock characters during combat

**Files:**
- Modify: `app/services/combat_service.py` (party-defeat path near line 670; plus a helper)
- Test: `tests/test_extraction_economy.py` (append)

**Background:** Combat currently detects party defeat (`alive == []`) and marks the
session complete, but never persists `is_dead`/lock to the `Character` rows. We add a
helper that maps party members at hp<=0 to their characters and calls
`extraction_service.handle_character_death`, resolving the dungeon instance from the
user's most recent `DungeonInstance` (same approach combat already uses for snapshots).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_extraction_economy.py`:

```python
from app.models.models import CombatSession
from app.services import combat_service


def test_party_wipe_marks_characters_dead_and_permadeath():
    user = create_user("extr_b")
    inst = create_instance(user, seed=909)
    char = create_character(user, name="Doomed", items=[{"slug": "potion_heal_l1", "qty": 1}])
    char.gold = 99
    char.locked_dungeon_id = None
    db.session.commit()

    monster = {"slug": "orc", "name": "Orc", "hp": 30, "damage": 2, "speed": 5}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    # Force the whole party to 0 HP
    for m in party["members"]:
        m["hp"] = 0
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    combat_service.resolve_party_defeat_if_any(session)

    db.session.refresh(char)
    assert char.is_dead is True
    assert char.permadeath is True


def test_downed_member_is_marked_dead_not_permadeath():
    user = create_user("extr_c")
    inst = create_instance(user, seed=910)
    char = create_character(user, name="Downed", items=[])
    db.session.commit()

    monster = {"slug": "rat", "name": "Rat", "hp": 1, "damage": 0, "speed": 1}
    session = combat_service.start_session(user.id, monster)
    party = json.loads(session.party_snapshot_json)
    party["members"][0]["hp"] = 0  # this member is downed, party not necessarily wiped
    session.party_snapshot_json = json.dumps(party)
    db.session.commit()

    combat_service.sync_member_death_states(session)

    db.session.refresh(char)
    assert char.is_dead is True
    assert char.permadeath is False  # recoverable until extraction/wipe
```

> Note: `resolve_party_defeat_if_any` and `sync_member_death_states` are the new
> helpers introduced in Step 3. If the
> combat module already finalizes defeat inside a larger private function, this helper
> wraps the same logic so it is unit-testable.

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_extraction_economy.py::test_party_wipe_marks_characters_dead_and_permadeath -v`
Expected: FAIL — `AttributeError: module 'app.services.combat_service' has no attribute 'resolve_party_defeat_if_any'`

- [ ] **Step 3: Implement the helper and call it from the defeat path**

In `app/services/combat_service.py`, add imports near the top (with the other `from app...` imports):

```python
from app.models.dungeon_instance import DungeonInstance
from app.services import extraction_service
```

Add this function above `_emit_session` (near line 681):

```python
def _current_instance_for_user(user_id: int):
    """Resolve the user's active dungeon instance (most recent), or None."""
    return (
        DungeonInstance.query.filter_by(user_id=user_id)
        .order_by(DungeonInstance.id.desc())
        .first()
    )


def sync_member_death_states(session) -> None:
    """Persist per-member downed state to Character rows after a resolution.

    Any member at hp<=0 becomes is_dead + locked to the current instance (downed,
    recoverable: revived if extracted, permadeath if left behind). Does NOT set
    permadeath here — that is decided at extraction or on a wipe.
    """
    party = json.loads(session.party_snapshot_json or "{}") or {}
    members = party.get("members", [])
    if not members:
        return
    instance = _current_instance_for_user(session.user_id)
    char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
    changed = False
    for m in members:
        cid = m.get("char_id") or m.get("id")
        char = char_rows.get(cid)
        if not char:
            continue
        if m.get("hp", 0) <= 0 and not char.is_dead:
            if instance is not None:
                extraction_service.handle_character_death(char, instance)
            else:
                char.is_dead = True
                char.death_count = (char.death_count or 0) + 1
            changed = True
    if changed:
        db.session.commit()


def resolve_party_defeat_if_any(session) -> bool:
    """If every party member is at 0 HP, permadeath the run.

    Marks each member's Character as dead + permadeath (a wipe loses the run: the
    haul is simply never pooled into the hoard). Returns True if a wipe occurred.
    """
    party = json.loads(session.party_snapshot_json or "{}") or {}
    members = party.get("members", [])
    alive = [m for m in members if m.get("hp", 0) > 0]
    if members and not alive:
        instance = _current_instance_for_user(session.user_id)
        char_rows = {c.id: c for c in Character.query.filter_by(user_id=session.user_id).all()}
        for m in members:
            cid = m.get("char_id") or m.get("id")
            char = char_rows.get(cid)
            if not char:
                continue
            if instance is not None:
                extraction_service.handle_character_death(char, instance)
            else:
                char.is_dead = True
                char.death_count = (char.death_count or 0) + 1
            char.permadeath = True
        db.session.commit()
        return True
    return False
```

Then, in the existing party-defeat path (the `if not alive:` block near line 673), add a call right after `session.status = "complete"`:

```python
    if not alive:
        session.status = "complete"
        session.rewards_json = json.dumps({})
        _append_log(session, "Party defeated.", code=COMBAT_COMPLETE)
        resolve_party_defeat_if_any(session)
        _persist_party_resources(session)
        set_combat_state(False)
```

Also, in the **victory/normal completion** block just above the defeat path (the block
that ends with `_persist_party_resources(session)` / `set_combat_state(False)` / `return`
near line 667), add a per-member death sync right before `_persist_party_resources(session)`
so a partially-downed party records its casualties:

```python
        sync_member_death_states(session)
        _persist_party_resources(session)
        set_combat_state(False)
        return
```

- [ ] **Step 4: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_extraction_economy.py -v`
Expected: PASS.

- [ ] **Step 5: Run the combat suite to check for regressions**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_combat_smoke.py tests/test_combat_actions.py -v`
Expected: PASS. (Note: `tests/test_combat_persistence.py` is known-flaky due to a pre-existing combat-engine race — see its commit note — so judge it by isolated runs, not this suite.)

- [ ] **Step 6: Commit**

```bash
git add app/services/combat_service.py tests/test_extraction_economy.py
git commit -m "feat(combat): persist party-wipe death + permadeath (run lost)"
```

---

## Task 6: Loot the body (transfer a downed ally's haul to a survivor)

**Files:**
- Modify: `app/routes/hoard_api.py` (add the endpoint here — it is run-state economy)
- Test: `tests/test_hoard_api.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_hoard_api.py`:

```python
def test_loot_body_transfers_bag_to_survivor(client):
    from tests.factories import create_character, create_user

    user = create_user("loot_a")
    downed = create_character(user, name="Fallen", items=[{"slug": "potion_heal_l1", "qty": 2}])
    downed.is_dead = True
    survivor = create_character(user, name="Living", items=[])
    db.session.commit()
    _login(client, user)

    resp = client.post(
        "/api/dungeon/loot-body",
        json={"downed_id": downed.id, "survivor_id": survivor.id},
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(survivor)
    db.session.refresh(downed)
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(survivor.items))
    assert json.loads(downed.items) == []


def test_loot_body_requires_downed_character(client):
    from tests.factories import create_character, create_user

    user = create_user("loot_b")
    alive = create_character(user, name="Healthy", items=[{"slug": "potion_heal_l1", "qty": 1}])
    survivor = create_character(user, name="Other", items=[])
    db.session.commit()
    _login(client, user)
    resp = client.post(
        "/api/dungeon/loot-body",
        json={"downed_id": alive.id, "survivor_id": survivor.id},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard_api.py -k loot_body -v`
Expected: FAIL — 404 (route missing).

- [ ] **Step 3: Implement the endpoint**

Append to `app/routes/hoard_api.py` (and extend the existing imports at the top to include the inventory helpers):

```python
from app.inventory.utils import load_inventory  # add to the import block at top
```

```python
@bp_hoard.route("/api/dungeon/loot-body", methods=["POST"])
@login_required
def loot_body():
    """Transfer a downed ally's bag (and equipped gear) onto a surviving character.

    The downed character keeps is_dead; once looted they are typically left behind
    (permadeath happens at extraction). Only the owner's characters are eligible.
    """
    data = request.get_json() or {}
    downed_id = data.get("downed_id")
    survivor_id = data.get("survivor_id")
    if not downed_id or not survivor_id:
        return jsonify({"error": "Missing required fields"}), 400

    downed = db.session.get(Character, downed_id)
    survivor = db.session.get(Character, survivor_id)
    if not downed or not survivor or downed.user_id != current_user.id or survivor.user_id != current_user.id:
        return jsonify({"error": "Character not found"}), 404
    if not downed.is_dead:
        return jsonify({"error": "Character is not downed"}), 400

    bag = load_inventory(downed.items)
    survivor_bag = load_inventory(survivor.items)
    # Move the whole bag verbatim (stacks + instances).
    for entry in bag:
        survivor_bag.append(entry)
    survivor.items = json.dumps(survivor_bag)
    downed.items = "[]"
    db.session.commit()
    return jsonify({"success": True})
```

- [ ] **Step 4: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_hoard_api.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add app/routes/hoard_api.py tests/test_hoard_api.py
git commit -m "feat(run): loot a downed ally's bag onto a survivor"
```

---

## Task 7: Repoint town vendor trading to the Hoard

**Files:**
- Modify: `app/routes/trading_api.py` (`buy_item`, `sell_item`)
- Modify: `tests/test_trading_economy.py` (update expectations to use the hoard)

**Background:** Spec 1's buy/sell operate on `Character.gold` and `Character.items`.
In Spec 2 `Character.gold` is the at-risk run-purse, so town trades must use the
Hoard: buy deducts `Hoard.copper` and adds the item to `Hoard.items_json`; sell
removes from the hoard and credits `Hoard.copper`. Trades are identified by the
owning user (via `character_id` → `user_id`, preserving the existing request shape).

- [ ] **Step 1: Update the trading tests to expect hoard-based behavior**

Replace the body of `tests/test_trading_economy.py`'s `hero` fixture and the buy/sell
assertions so funds come from the hoard. Concretely:

- In the `hero` fixture, after creating the character, seed the hoard instead of
  `char.gold`:

```python
@pytest.fixture
def hero(test_app):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    user = create_user("trader_" + "x")
    char = create_character(user, name="Trader", items=[])
    hoard = Hoard.get_or_create(user.id)
    hoard_service.deposit_copper(hoard, 1000)  # hoard copper
    db.session.commit()
    return char
```

- In `test_buy_deducts_copper_and_adds_item`, assert the hoard balance and that the
  item lands in the hoard:

```python
def test_buy_deducts_copper_and_adds_item(client, merchant, hero):
    from app.models.hoard import Hoard

    resp = client.post(
        "/api/trade/buy",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 2},
    )
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    assert data["total_cost"] == 200
    assert data["new_balance"] == 800
    assert data["new_balance_display"] == "8s"
    hoard = Hoard.query.filter_by(user_id=hero.user_id).first()
    assert hoard.copper == 800
    assert any(i.get("slug") == "potion_heal_l1" for i in json.loads(hoard.items_json))
    stock = MerchantStock.query.filter_by(merchant_id=merchant.id, item_slug="potion_heal_l1").first()
    assert stock.current_stock == 3
```

- In `test_sell_catalog_item_by_slug` and `test_sell_procedural_instance_by_uid`,
  seed the item into the hoard (not `char.items`) and assert hoard balances:

```python
def test_sell_catalog_item_by_slug(client, merchant, hero):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    hoard = Hoard.get_or_create(hero.user_id)
    hoard_service.deposit_items(hoard, [{"slug": "potion_heal_l1", "qty": 1}])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "item_slug": "potion_heal_l1", "quantity": 1},
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["total_value"] == 50
    hoard = Hoard.query.filter_by(user_id=hero.user_id).first()
    assert all(i.get("slug") != "potion_heal_l1" for i in json.loads(hoard.items_json))


def test_sell_procedural_instance_by_uid(client, merchant, hero):
    from app.economy import hoard_service
    from app.models.hoard import Hoard

    hoard = Hoard.get_or_create(hero.user_id)
    hoard_service.deposit_items(hoard, [{"uid": "gear123", "name": "Brutal Shortsword", "slot": "weapon", "value": 400}])
    db.session.commit()
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "gear123"},
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["total_value"] == 200
```

- Delete `test_buy_does_not_wipe_gear_instances` (it tested character-bag behavior
  that no longer applies to town trading) and the catalog/`uid` "not in inventory"
  test's reliance on `char.items`; replace the latter with a hoard-empty case:

```python
def test_sell_unknown_returns_400(client, merchant, hero):
    resp = client.post(
        "/api/trade/sell",
        json={"character_id": hero.id, "merchant_slug": "test-shop", "uid": "nope"},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_trading_economy.py -v`
Expected: FAIL (endpoints still use `Character.gold`).

- [ ] **Step 3: Implement — repoint buy/sell to the hoard**

In `app/routes/trading_api.py`, add imports:

```python
from app.economy import hoard_service
from app.models.hoard import Hoard
```

In `buy_item`, replace the character-funds/inventory section. After loading the
`character` (kept for ownership/user resolution), use the hoard:

```python
    hoard = Hoard.get_or_create(character.user_id)

    # affordability
    if (hoard.copper or 0) < total_cost:
        return jsonify({"error": "Insufficient funds"}), 400

    # ... stock check unchanged ...

    try:
        hoard.copper -= total_cost
        hoard_service.deposit_items(hoard, [{"slug": item_slug, "qty": quantity}])
        if stock_entry:
            stock_entry.current_stock -= quantity
        transaction = TradeTransaction(
            character_id=character.id,
            merchant_id=merchant.id,
            transaction_type="buy",
            item_slug=item_slug,
            quantity=quantity,
            price_per_item=buy_price,
            total_gold=total_cost,
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "item": item_slug,
                "quantity": quantity,
                "total_cost": total_cost,
                "total_cost_display": format_copper(total_cost),
                "new_balance": hoard.copper,
                "new_balance_display": format_copper(hoard.copper),
            }
        )
    except Exception as e:
        db.session.rollback()
        print(f"[trading] Buy transaction failed: {e}")
        return jsonify({"error": "Transaction failed"}), 500
```

In `sell_item`, operate on the hoard's items and copper. Replace the inventory load
and the per-kind removal so they target the hoard:

```python
    hoard = Hoard.get_or_create(character.user_id)
    inventory = load_inventory(hoard.items_json)
    # ... existing branch logic, but operating on `inventory` (hoard items) ...
    # On success, instead of character.gold/character.items:
    hoard.items_json = json.dumps(inventory)
    hoard.copper += total_value
    # response: replace new_gold/new_gold_display with:
    #   "new_balance": hoard.copper, "new_balance_display": format_copper(hoard.copper)
```

Keep the dual catalog/`uid` selling logic from Spec 1; only the storage target
changes from `character` to `hoard`. Stock updates for catalog sales remain.

- [ ] **Step 4: Run to verify pass**

Run: `TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_trading_economy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routes/trading_api.py tests/test_trading_economy.py
git commit -m "refactor(trading): town vendors transact against the hoard"
```

---

## Task 8: Alembic migration for the hoard table

**Files:**
- Create: `migrations/versions/<rev>_add_hoard_table.py` (generated)

- [ ] **Step 1: Generate the migration**

Run (against the dev DB):
```bash
DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure \
  .venv/bin/python -m flask --app app db migrate -m "add hoard table"
```
If the project uses a different migrate entrypoint, check `migrations/` and `README` /
`docs/TESTING.md`; mirror the command used for prior migrations (e.g. the
`95ff19b9fe00` extraction migration).

- [ ] **Step 2: Review the generated migration**

Open the new file under `migrations/versions/`. Confirm it `create_table("hoard", ...)`
with `id`, `user_id` (unique, FK to `user.id`), `items_json` (Text, not null,
server_default `"[]"` or handled in model), `copper` (Integer, not null, default 0).
Remove any spurious autogenerated drops of unrelated tables.

- [ ] **Step 3: Apply and verify**

```bash
DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure \
  .venv/bin/python -m flask --app app db upgrade
```
Expected: no error; `hoard` table exists.

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/
git commit -m "chore(db): migration for hoard table"
```

---

## Task 9: Full-suite verification

- [ ] **Step 1: Reset the test schema and run the new + adjacent suites**

```bash
export TEST_DATABASE_URL=postgresql://adventure:changeme@localhost:5433/adventure_test
.venv/bin/python -c "import os; os.environ['DATABASE_URL']=os.environ['TEST_DATABASE_URL']; from app import create_app, db; \
  app=create_app(); ctx=app.app_context(); ctx.push(); db.drop_all(); db.create_all(); print('fresh')"
.venv/bin/python -m pytest tests/test_hoard.py tests/test_hoard_api.py tests/test_extraction_economy.py \
  tests/test_trading_economy.py tests/test_currency.py tests/test_inventory_encumbrance.py tests/test_extraction.py -v
```
Expected: all PASS.

- [ ] **Step 2: Sanity-check the broader suite (excluding the known-flaky combat-persistence race)**

```bash
.venv/bin/python -m pytest tests/ -q --deselect tests/test_combat_persistence.py
```
Expected: green except any pre-existing unrelated failures (note them, don't fix here).

- [ ] **Step 3: Final commit if any cleanup was needed**

```bash
git add -A && git commit -m "test(hoard): full-suite verification for extraction economy" || echo "nothing to commit"
```

---

## Notes for the implementer

- **Run-purse:** `Character.gold` is now the at-risk run-purse (copper units). Anywhere
  coins are *awarded during a run* should add to `Character.gold`; vendors never touch it.
- **Equipped gear persists** on the character (loadout). Spec 2 does not pool
  `Character.gear` on extract — only the bag (`items`) and purse (`gold`).
- **Wipe loses the run** by simply never pooling: permadeath the party; the haul stays on
  inaccessible (permadead) characters. No explicit "delete items" is required.
- **Known flaky:** `tests/test_combat_persistence.py` fails intermittently due to a
  pre-existing combat-engine background-turn race (documented in its commit). Do not
  treat its flakiness as a regression from this work.
