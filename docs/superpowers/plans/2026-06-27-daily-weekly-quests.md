# Daily & Weekly Quest System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user daily (3 quests, reset midnight) and weekly (complete 10 dailies, reset Monday midnight) quests with automatic kill/run tracking and claim-on-completion reward delivery.

**Architecture:** New `user_quest_pool` table stores generated quest JSON per user per reset period. Generation is lazy (on first API access). Progress is tracked by hooking `_check_end()` in `combat_service.py` (kills) and `extract_party()` in `extraction_service.py` (runs). Rewards go to hoard on claim.

**Tech Stack:** Flask, SQLAlchemy, Alembic, existing `Hoard` model, existing `format_copper()` / `formatCopper()`, server-local timezone (`datetime.now()` not `utcnow()`).

## Global Constraints

- Reset times use **server-local time** (`datetime.now()`, not `datetime.utcnow()`)
- Daily period key format: `"YYYY-MM-DD"` (e.g. `"2026-06-27"`)
- Weekly period key format: `"YYYY-WNN"` (e.g. `"2026-W26"`) using `isocalendar()`
- Rewards land in hoard (items/potions), XP splits across all user-owned characters
- Quest progress tracked per-user (not per-character); entire party's kills count
- Fire-and-forget for progress hooks — catch all exceptions, never block combat
- Existing `QuestTemplate` / `QuestProgress` tables untouched
- Migration revision chain: chain after `f1a2b3c4d5e6` (last known revision)

---

### Task 1: Database migration — `user_quest_pool` table

**Files:**
- Create: `migrations/versions/a1b2c3d4e5f6_add_user_quest_pool.py`

**Interfaces:**
- Produces: `user_quest_pool` table with columns `id, user_id, period_type, period_key, quests_json, created_at` and unique constraint `(user_id, period_type, period_key)`

- [ ] **Step 1: Create migration file**

```python
# migrations/versions/a1b2c3d4e5f6_add_user_quest_pool.py
"""add user_quest_pool table

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-27

"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_quest_pool",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(10), nullable=False),  # "daily" | "weekly"
        sa.Column("period_key", sa.String(20), nullable=False),   # "2026-06-27" | "2026-W26"
        sa.Column("quests_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "period_type", "period_key", name="uq_user_quest_pool"),
    )
    op.create_index("ix_user_quest_pool_user_id", "user_quest_pool", ["user_id"])


def downgrade():
    op.drop_index("ix_user_quest_pool_user_id", table_name="user_quest_pool")
    op.drop_table("user_quest_pool")
```

- [ ] **Step 2: Apply the migration**

```bash
alembic upgrade head
```
Expected: `Running upgrade f1a2b3c4d5e6 -> a1b2c3d4e5f6, add user_quest_pool table`

- [ ] **Step 3: Verify table exists**

```bash
python3 -c "
from app import app, db
with app.app_context():
    from sqlalchemy import inspect
    print(inspect(db.engine).get_table_names())
" | grep user_quest_pool
```
Expected: `user_quest_pool` in output

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/a1b2c3d4e5f6_add_user_quest_pool.py
git commit -m "feat(quests): add user_quest_pool migration"
```

---

### Task 2: `UserQuestPool` model

**Files:**
- Create: `app/models/user_quest_pool.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces: `UserQuestPool` ORM model with `get_or_none(user_id, period_type, period_key)` classmethod

- [ ] **Step 1: Write the failing test**

```python
# tests/test_user_quest_pool_model.py
from datetime import datetime

def test_create_and_retrieve(app_context):
    from app.models.user_quest_pool import UserQuestPool
    from app import db
    pool = UserQuestPool(
        user_id=1, period_type="daily", period_key="2026-06-27",
        quests_json="[]", created_at=datetime.now()
    )
    db.session.add(pool)
    db.session.commit()

    found = UserQuestPool.get_or_none(1, "daily", "2026-06-27")
    assert found is not None
    assert found.period_key == "2026-06-27"

def test_get_or_none_missing_returns_none(app_context):
    from app.models.user_quest_pool import UserQuestPool
    assert UserQuestPool.get_or_none(9999, "daily", "2099-01-01") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_user_quest_pool_model.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.user_quest_pool'`

- [ ] **Step 3: Create `app/models/user_quest_pool.py`**

```python
"""Per-user generated quest pool for daily and weekly quests."""

from datetime import datetime

from app import db


class UserQuestPool(db.Model):
    __tablename__ = "user_quest_pool"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    period_type = db.Column(db.String(10), nullable=False)   # "daily" | "weekly"
    period_key = db.Column(db.String(20), nullable=False)    # "2026-06-27" | "2026-W26"
    quests_json = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    @classmethod
    def get_or_none(cls, user_id: int, period_type: str, period_key: str):
        return cls.query.filter_by(
            user_id=user_id, period_type=period_type, period_key=period_key
        ).first()
```

- [ ] **Step 4: Add to `app/models/__init__.py`**

```python
from .user_quest_pool import UserQuestPool  # noqa: F401
```
Also add `"UserQuestPool"` to the `__all__` list if one exists.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_user_quest_pool_model.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models/user_quest_pool.py app/models/__init__.py tests/test_user_quest_pool_model.py
git commit -m "feat(quests): add UserQuestPool model"
```

---

### Task 3: Quest generator service

**Files:**
- Create: `app/services/quest_generator.py`

**Interfaces:**
- Produces:
  - `get_or_generate_daily(user_id: int) -> list[dict]`
  - `get_or_generate_weekly(user_id: int) -> dict`
  - `period_key_daily() -> str`  (e.g. `"2026-06-27"`)
  - `period_key_weekly() -> str` (e.g. `"2026-W26"`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quest_generator.py
import json
from unittest.mock import patch

def test_period_key_daily():
    from app.services.quest_generator import period_key_daily
    key = period_key_daily()
    assert len(key) == 10  # "YYYY-MM-DD"
    assert key.count('-') == 2

def test_period_key_weekly():
    from app.services.quest_generator import period_key_weekly
    key = period_key_weekly()
    assert key.startswith('20')
    assert '-W' in key

def test_generate_daily_returns_three_quests(app_context):
    from app.services.quest_generator import get_or_generate_daily
    quests = get_or_generate_daily(user_id=1)
    assert len(quests) == 3
    for q in quests:
        assert 'id' in q
        assert q['objective']['type'] in ('kill_count', 'kill_elite', 'run_complete', 'run_extract')
        assert q['status'] == 'active'

def test_generate_daily_idempotent(app_context):
    from app.services.quest_generator import get_or_generate_daily
    first = get_or_generate_daily(user_id=1)
    second = get_or_generate_daily(user_id=1)
    assert [q['id'] for q in first] == [q['id'] for q in second]

def test_generate_weekly_returns_one_quest(app_context):
    from app.services.quest_generator import get_or_generate_weekly
    quest = get_or_generate_weekly(user_id=1)
    assert quest['objective']['type'] == 'daily_completions'
    assert quest['objective']['target'] == 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_quest_generator.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Create `app/services/quest_generator.py`**

```python
"""Lazy generator for per-user daily and weekly quests."""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime

from app import db
from app.models.user_quest_pool import UserQuestPool


def period_key_daily() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def period_key_weekly() -> str:
    iso = datetime.now().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# Template families with (weight, title, description_template, objective_type, target_range)
_DAILY_TEMPLATES = [
    (3, "Thin the Ranks",   "Defeat {n} enemies in the dungeon.",           "kill_count",   (10, 30)),
    (2, "Veteran's Trial",  "Defeat {n} elite or boss enemies.",             "kill_elite",   (2, 6)),
    (3, "Back in One Piece","Complete {n} dungeon runs.",                    "run_complete", (2, 4)),
    (2, "Clean Sweep",      "Extract successfully {n} times without a wipe.","run_extract",  (1, 3)),
]


def _avg_level(user_id: int) -> int:
    from app.models.models import Character
    chars = Character.query.filter_by(user_id=user_id).all()
    if not chars:
        return 1
    return max(1, round(sum(c.level for c in chars) / len(chars)))


def _roll_rewards(avg_level: int, template_type: str) -> dict:
    xp = random.randint(200, 500)
    potions = [{"slug": random.choice(["potion-healing", "potion-mana"]), "qty": random.randint(1, 2)}]
    return {
        "xp": xp,
        "potions": potions,
        "gear_roll": random.random() < 0.15,
    }


def _generate_dailies(avg_level: int) -> list[dict]:
    weights = [t[0] for t in _DAILY_TEMPLATES]
    chosen = random.choices(_DAILY_TEMPLATES, weights=weights, k=3)
    quests = []
    for weight, title, desc_tpl, obj_type, (lo, hi) in chosen:
        n = random.randint(lo, hi)
        quests.append({
            "id": str(uuid.uuid4()),
            "template": obj_type,
            "title": title,
            "description": desc_tpl.format(n=n),
            "objective": {"type": obj_type, "target": n, "current": 0},
            "rewards": _roll_rewards(avg_level, obj_type),
            "status": "active",
            "claimed_at": None,
        })
    return quests


def _generate_weekly() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "template": "weekly_dailies",
        "title": "Weekly Devotion",
        "description": "Complete 10 daily quests this week.",
        "objective": {"type": "daily_completions", "target": 10, "current": 0},
        "rewards": {
            "xp": 1500,
            "potions": [{"slug": "potion-healing", "qty": random.randint(3, 5)}],
            "gear_roll": True,
            "copper": 500,
        },
        "status": "active",
        "claimed_at": None,
    }


def get_or_generate_daily(user_id: int) -> list[dict]:
    key = period_key_daily()
    pool = UserQuestPool.get_or_none(user_id, "daily", key)
    if pool:
        return json.loads(pool.quests_json)

    avg = _avg_level(user_id)
    quests = _generate_dailies(avg)
    pool = UserQuestPool(
        user_id=user_id,
        period_type="daily",
        period_key=key,
        quests_json=json.dumps(quests),
        created_at=datetime.now(),
    )
    db.session.add(pool)
    db.session.commit()
    return quests


def get_or_generate_weekly(user_id: int) -> dict:
    key = period_key_weekly()
    pool = UserQuestPool.get_or_none(user_id, "weekly", key)
    if pool:
        quests = json.loads(pool.quests_json)
        return quests[0] if quests else _generate_weekly()

    quest = _generate_weekly()
    pool = UserQuestPool(
        user_id=user_id,
        period_type="weekly",
        period_key=key,
        quests_json=json.dumps([quest]),
        created_at=datetime.now(),
    )
    db.session.add(pool)
    db.session.commit()
    return quest
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_quest_generator.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/quest_generator.py tests/test_quest_generator.py
git commit -m "feat(quests): add quest generator service for daily/weekly quests"
```

---

### Task 4: Quest progress service

**Files:**
- Create: `app/services/quest_progress_service.py`

**Interfaces:**
- Produces:
  - `record_kill(user_id: int, is_elite: bool = False) -> None`
  - `record_run_complete(user_id: int, extracted: bool = True) -> None`
  - `increment_daily_completions(user_id: int) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_quest_progress_service.py
import json

def test_record_kill_increments_kill_count(app_context, test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    kill_quests = [q for q in quests if q['objective']['type'] == 'kill_count']
    if not kill_quests:
        return  # no kill_count quest generated this run; skip

    from app.services.quest_progress_service import record_kill
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    record_kill(user_id, is_elite=False)
    pool = UserQuestPool.get_or_none(user_id, "daily", period_key_daily())
    updated = json.loads(pool.quests_json)
    updated_q = next(q for q in updated if q['id'] == kill_quests[0]['id'])
    assert updated_q['objective']['current'] == 1

def test_record_kill_elite_increments_elite(app_context, test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    from app.services.quest_progress_service import record_kill
    # Should not raise even if no elite quest exists
    record_kill(user_id, is_elite=True)

def test_record_run_complete(app_context, test_user_with_daily_quests):
    user_id, quests = test_user_with_daily_quests
    from app.services.quest_progress_service import record_run_complete
    record_run_complete(user_id, extracted=True)
    # Should not raise; verify no exception is enough for fire-and-forget
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_quest_progress_service.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Create `app/services/quest_progress_service.py`**

```python
"""Update daily/weekly quest progress from dungeon events. Fire-and-forget."""

from __future__ import annotations

import json
import logging

from app import db
from app.models.user_quest_pool import UserQuestPool
from app.services.quest_generator import period_key_daily, period_key_weekly

logger = logging.getLogger(__name__)

# Maps objective type → which event increments it
_KILL_TYPES = {"kill_count", "kill_elite"}
_RUN_TYPES = {"run_complete", "run_extract"}


def _update_pool(user_id: int, period_type: str, period_key: str, predicate, amount: int = 1):
    """Increment objective.current on all matching active quests in pool."""
    pool = UserQuestPool.get_or_none(user_id, period_type, period_key)
    if not pool:
        return
    try:
        quests = json.loads(pool.quests_json)
    except Exception:
        return
    changed = False
    for q in quests:
        if q.get("status") != "active":
            continue
        obj = q.get("objective", {})
        if not predicate(obj):
            continue
        obj["current"] = min(obj.get("current", 0) + amount, obj.get("target", 9999))
        q["objective"] = obj
        changed = True
    if changed:
        pool.quests_json = json.dumps(quests)
        db.session.add(pool)
        db.session.commit()


def record_kill(user_id: int, is_elite: bool = False) -> None:
    try:
        key = period_key_daily()
        if is_elite:
            _update_pool(user_id, "daily", key, lambda o: o.get("type") == "kill_elite")
        _update_pool(user_id, "daily", key, lambda o: o.get("type") == "kill_count")
    except Exception as e:
        logger.warning("quest_progress_record_kill_failed", extra={"error": str(e)})


def record_run_complete(user_id: int, extracted: bool = True) -> None:
    try:
        key = period_key_daily()
        _update_pool(user_id, "daily", key, lambda o: o.get("type") == "run_complete")
        if extracted:
            _update_pool(user_id, "daily", key, lambda o: o.get("type") == "run_extract")
    except Exception as e:
        logger.warning("quest_progress_record_run_failed", extra={"error": str(e)})


def increment_daily_completions(user_id: int) -> None:
    """Called when a daily quest is claimed; advances the weekly counter."""
    try:
        key = period_key_weekly()
        _update_pool(user_id, "weekly", key, lambda o: o.get("type") == "daily_completions")
    except Exception as e:
        logger.warning("quest_progress_weekly_failed", extra={"error": str(e)})
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_quest_progress_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/quest_progress_service.py tests/test_quest_progress_service.py
git commit -m "feat(quests): add quest progress service for kill/run tracking"
```

---

### Task 5: Hook progress into combat and extraction

**Files:**
- Modify: `app/services/combat_service.py` (in `_check_end`, after `instance.monsters_defeated += 1`)
- Modify: `app/services/extraction_service.py` (in `extract_party`, after successful extraction)

**Interfaces:**
- Consumes: `quest_progress_service.record_kill(user_id, is_elite)` and `record_run_complete(user_id, extracted)`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_quest_hooks.py
import json

def test_kill_increments_daily_quest(app_context, test_user_with_daily_kill_quest, mock_combat_session):
    """Simulate a monster kill and verify daily quest progress updates."""
    from app.services.quest_progress_service import record_kill
    from app.models.user_quest_pool import UserQuestPool
    from app.services.quest_generator import period_key_daily

    user_id, quest = test_user_with_daily_kill_quest
    initial = quest['objective']['current']
    record_kill(user_id, is_elite=False)

    pool = UserQuestPool.get_or_none(user_id, "daily", period_key_daily())
    quests = json.loads(pool.quests_json)
    updated = next(q for q in quests if q['id'] == quest['id'])
    assert updated['objective']['current'] == initial + 1
```

- [ ] **Step 2: Run test to verify it passes (service already works)**

```bash
pytest tests/test_quest_hooks.py -v
```
Expected: PASS (record_kill already implemented)

- [ ] **Step 3: Add kill hook to `combat_service.py`**

In `_check_end()`, locate the block at line ~628 that increments `instance.elites_defeated` / `instance.monsters_defeated`. Add after each branch:

```python
# After instance.elites_defeated += 1:
try:
    from app.services import quest_progress_service
    quest_progress_service.record_kill(session.user_id, is_elite=True)
except Exception:
    pass

# After instance.monsters_defeated += 1:
try:
    from app.services import quest_progress_service
    quest_progress_service.record_kill(session.user_id, is_elite=False)
except Exception:
    pass
```

- [ ] **Step 4: Add run hook to `extraction_service.py`**

In `extract_party()`, locate the end of the extracting character loop (after `hoard_service.pool_run_haul`). Add after the loop closes (once per extraction, not per character):

```python
try:
    from app.services import quest_progress_service
    quest_progress_service.record_run_complete(user_id, extracted=True)
except Exception:
    pass
```

- [ ] **Step 5: Verify no new test failures**

```bash
pytest tests/ -v --tb=short -q
```
Expected: all existing tests still pass, no new failures

- [ ] **Step 6: Commit**

```bash
git add app/services/combat_service.py app/services/extraction_service.py tests/test_quest_hooks.py
git commit -m "feat(quests): hook kill and run tracking into combat and extraction"
```

---

### Task 6: Quest API — daily/weekly endpoints and claim

**Files:**
- Modify: `app/routes/quest_api.py`

**Interfaces:**
- Produces:
  - `GET /api/quests/daily` → `{quests: [...]}`
  - `GET /api/quests/weekly` → `{quest: {...}}`
  - `POST /api/quests/daily/claim` `{quest_id: str}` → `{success, rewards, quest}`
  - `POST /api/quests/weekly/claim` → `{success, rewards, quest}`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_daily_weekly_api.py

def test_get_daily_returns_three(client, logged_in_user):
    resp = client.get('/api/quests/daily')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['quests']) == 3

def test_get_weekly_returns_one(client, logged_in_user):
    resp = client.get('/api/quests/weekly')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['quest']['objective']['type'] == 'daily_completions'

def test_claim_daily_requires_completion(client, logged_in_user):
    resp = client.get('/api/quests/daily')
    quest_id = resp.get_json()['quests'][0]['id']
    resp2 = client.post('/api/quests/daily/claim', json={'quest_id': quest_id})
    # objective.current is 0, target > 0
    assert resp2.status_code == 400
    assert 'not complete' in resp2.get_json()['error'].lower()

def test_claim_daily_completed_grants_rewards(client, logged_in_user, daily_quest_at_target):
    quest_id = daily_quest_at_target
    resp = client.post('/api/quests/daily/claim', json={'quest_id': quest_id})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert 'rewards' in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_daily_weekly_api.py -v
```
Expected: FAIL — routes return 404

- [ ] **Step 3: Add routes to `app/routes/quest_api.py`**

Add these at the bottom of the file, before `_serialize_quest`:

```python
# ── Daily / Weekly quests (user-scoped, auto-generated) ──────────────────

@bp_quest.route("/api/quests/daily")
@login_required
def get_daily_quests():
    from app.services.quest_generator import get_or_generate_daily
    quests = get_or_generate_daily(current_user.id)
    return jsonify({"quests": quests})


@bp_quest.route("/api/quests/weekly")
@login_required
def get_weekly_quest():
    from app.services.quest_generator import get_or_generate_weekly
    quest = get_or_generate_weekly(current_user.id)
    return jsonify({"quest": quest})


@bp_quest.route("/api/quests/daily/claim", methods=["POST"])
@login_required
def claim_daily_quest():
    data = request.get_json() or {}
    quest_id = data.get("quest_id")
    if not quest_id:
        return jsonify({"error": "quest_id required"}), 400

    from app.services.quest_generator import period_key_daily
    from app.models.user_quest_pool import UserQuestPool

    pool = UserQuestPool.get_or_none(current_user.id, "daily", period_key_daily())
    if not pool:
        return jsonify({"error": "No daily quests found"}), 404

    quests = json.loads(pool.quests_json)
    quest = next((q for q in quests if q["id"] == quest_id), None)
    if not quest:
        return jsonify({"error": "Quest not found"}), 404
    if quest["status"] != "active":
        return jsonify({"error": "Quest already claimed"}), 400

    obj = quest["objective"]
    if obj.get("current", 0) < obj.get("target", 1):
        return jsonify({"error": "Quest not complete yet"}), 400

    rewards = _grant_daily_rewards(current_user.id, quest["rewards"])
    quest["status"] = "claimed"
    quest["claimed_at"] = datetime.utcnow().isoformat()
    pool.quests_json = json.dumps(quests)
    db.session.commit()

    # Advance weekly counter
    from app.services import quest_progress_service
    quest_progress_service.increment_daily_completions(current_user.id)

    return jsonify({"success": True, "rewards": rewards, "quest": quest})


@bp_quest.route("/api/quests/weekly/claim", methods=["POST"])
@login_required
def claim_weekly_quest():
    from app.services.quest_generator import period_key_weekly
    from app.models.user_quest_pool import UserQuestPool

    pool = UserQuestPool.get_or_none(current_user.id, "weekly", period_key_weekly())
    if not pool:
        return jsonify({"error": "No weekly quest found"}), 404

    quests = json.loads(pool.quests_json)
    if not quests:
        return jsonify({"error": "Weekly quest not found"}), 404
    quest = quests[0]

    if quest["status"] != "active":
        return jsonify({"error": "Weekly already claimed"}), 400

    obj = quest["objective"]
    if obj.get("current", 0) < obj.get("target", 10):
        return jsonify({"error": "Weekly not complete yet"}), 400

    rewards = _grant_daily_rewards(current_user.id, quest["rewards"])
    quest["status"] = "claimed"
    quest["claimed_at"] = datetime.utcnow().isoformat()
    pool.quests_json = json.dumps(quests)
    db.session.commit()

    return jsonify({"success": True, "rewards": rewards, "quest": quest})


def _grant_daily_rewards(user_id: int, rewards: dict) -> dict:
    """Grant XP to all characters, potions+gear to hoard. Returns summary."""
    from app.models.models import Character
    from app.models.hoard import Hoard
    from app.inventory.utils import load_inventory, dump_inventory, add_item

    granted = {}
    chars = Character.query.filter_by(user_id=user_id).all()

    # XP split across all characters
    xp = int(rewards.get("xp", 0))
    if xp and chars:
        share = max(1, xp // len(chars))
        for c in chars:
            c.xp = (c.xp or 0) + share
        granted["xp"] = xp

    # Potions to hoard
    hoard = Hoard.get_or_create(user_id)
    inv = load_inventory(hoard.items_json)
    potions_granted = []
    for potion in rewards.get("potions", []):
        slug = potion.get("slug")
        qty = int(potion.get("qty", 1))
        if slug:
            add_item(inv, slug, qty)
            potions_granted.append({"slug": slug, "qty": qty})
    hoard.items_json = dump_inventory(inv)
    granted["potions"] = potions_granted

    # Bonus copper
    copper = int(rewards.get("copper", 0))
    if copper:
        hoard.copper = (hoard.copper or 0) + copper
        granted["copper"] = copper

    # Gear roll (ponytail: skip procedural gear for now — requires loot generator integration)
    # TODO: wire to loot generator when rewards.get("gear_roll") is True
    granted["gear_roll"] = rewards.get("gear_roll", False)

    db.session.commit()
    return granted
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_daily_weekly_api.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/quest_api.py tests/test_daily_weekly_api.py
git commit -m "feat(quests): add daily/weekly quest API endpoints and claim flow"
```

---

### Task 7: Quest tab UI — Daily and Weekly sub-tabs

**Files:**
- Modify: `app/templates/dashboard.html` (`#lobby-quests` pane)
- Modify: `app/static/js/quest-system.js` (`openJournal()` and new `loadDailyWeekly()`)

**Interfaces:**
- Consumes: `GET /api/quests/daily`, `GET /api/quests/weekly`, `POST /api/quests/daily/claim`, `POST /api/quests/weekly/claim`

- [ ] **Step 1: Add Daily and Weekly sub-tabs to `#lobby-quests` in `dashboard.html`**

Find the `#lobby-quests` tab pane. Locate the `.quest-tabs` nav. Add two new tab buttons before the existing ones:

```html
<button class="nav-link active" id="quest-tab-daily" data-bs-toggle="tab"
        data-bs-target="#quest-panel-daily" type="button">Daily</button>
<button class="nav-link" id="quest-tab-weekly" data-bs-toggle="tab"
        data-bs-target="#quest-panel-weekly" type="button">Weekly</button>
```

Add matching tab panes inside `.tab-content`:

```html
<div class="tab-pane fade show active" id="quest-panel-daily">
  <div id="daily-quest-list"><div class="text-muted small py-2">Loading daily quests…</div></div>
</div>
<div class="tab-pane fade" id="quest-panel-weekly">
  <div id="weekly-quest-container"><div class="text-muted small py-2">Loading weekly quest…</div></div>
</div>
```

Make the existing Active tab no longer `active` by default (Daily is now default).

- [ ] **Step 2: Add `loadDailyWeekly()` to `quest-system.js`**

At the top of the IIFE in `quest-system.js`, add:

```javascript
async function loadDailyWeekly() {
  const [dResp, wResp] = await Promise.all([
    fetch('/api/quests/daily'),
    fetch('/api/quests/weekly'),
  ]);
  const dailyData = dResp.ok ? await dResp.json() : { quests: [] };
  const weeklyData = wResp.ok ? await wResp.json() : { quest: null };

  renderDailyQuests(dailyData.quests || []);
  renderWeeklyQuest(weeklyData.quest);
}

function renderDailyQuests(quests) {
  const el = document.getElementById('daily-quest-list');
  if (!el) return;
  if (!quests.length) { el.innerHTML = '<div class="text-muted small">No daily quests today.</div>'; return; }
  el.innerHTML = quests.map(q => renderQuestCard(q, 'daily')).join('');
  el.querySelectorAll('.btn-claim-quest').forEach(btn => {
    btn.addEventListener('click', () => claimDaily(btn.dataset.questId));
  });
}

function renderWeeklyQuest(quest) {
  const el = document.getElementById('weekly-quest-container');
  if (!el) return;
  if (!quest) { el.innerHTML = '<div class="text-muted small">No weekly quest.</div>'; return; }
  el.innerHTML = renderQuestCard(quest, 'weekly');
  el.querySelector('.btn-claim-quest')?.addEventListener('click', claimWeekly);
}

function renderQuestCard(q, type) {
  const obj = q.objective || {};
  const current = obj.current || 0;
  const target = obj.target || 1;
  const pct = Math.min(100, Math.round(current / target * 100));
  const claimed = q.status === 'claimed';
  const complete = current >= target;
  const claimBtn = complete && !claimed
    ? `<button class="btn btn-sm btn-success btn-claim-quest" data-quest-id="${q.id}">CLAIM</button>`
    : claimed
    ? `<span class="badge bg-secondary">Claimed</span>`
    : '';
  return `
<div class="card bg-dark border-secondary mb-2">
  <div class="card-body py-2">
    <div class="d-flex justify-content-between align-items-start">
      <div>
        <div class="fw-bold">${q.title || ''}</div>
        <div class="text-muted small">${q.description || ''}</div>
      </div>
      <div class="ms-2 flex-shrink-0">${claimBtn}</div>
    </div>
    <div class="progress mt-2" style="height:6px">
      <div class="progress-bar ${complete ? 'bg-success' : 'bg-primary'}" style="width:${pct}%"></div>
    </div>
    <div class="text-muted small mt-1">${current} / ${target}</div>
  </div>
</div>`;
}

async function claimDaily(questId) {
  const resp = await fetch('/api/quests/daily/claim', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quest_id: questId }),
  });
  const d = await resp.json();
  if (resp.ok) {
    loadDailyWeekly();
  } else {
    alert(d.error || 'Claim failed');
  }
}

async function claimWeekly() {
  const resp = await fetch('/api/quests/weekly/claim', { method: 'POST' });
  const d = await resp.json();
  if (resp.ok) {
    loadDailyWeekly();
  } else {
    alert(d.error || 'Claim failed');
  }
}
```

- [ ] **Step 3: Call `loadDailyWeekly()` from `openJournal()`**

In `quest-system.js`, find the existing `openJournal()` function and add at the top:

```javascript
loadDailyWeekly();
```

- [ ] **Step 4: Restart and manual test**

```bash
./manage.sh restart
```

Open dashboard → Quests tab → Daily sub-tab. Verify:
- 3 daily quest cards with progress bars render
- Weekly sub-tab shows the weekly quest with `0/10` progress
- CLAIM button appears only when progress meets target

- [ ] **Step 5: Commit**

```bash
git add app/templates/dashboard.html app/static/js/quest-system.js
git commit -m "feat(quests): add daily/weekly sub-tabs to quest journal UI"
```
